import re

from dcim.models import Device, Interface, DeviceRole
from django.http import JsonResponse
from django.shortcuts import render
from django.views.generic import View
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Q

from . import forms
from .forms import DeviceMapFilterForm
from .geographical_map import configure_leaflet_map
from .helpers import get_device_location, get_connected_devices, get_connected_wireless_devices
from .settings import plugin_settings


INTEGER_REGEXP = re.compile(r'\d+')


class MapView(PermissionRequiredMixin, View):
    permission_required = ('ipam.view_vlan', 'dcim.view_device', 'dcim.view_devicerole', 'dcim.view_cable')
    template_name = 'netbox_device_map/main.html'
    form = forms.DeviceMapFilterForm
    #form_class = DeviceMapFilterForm

    def get(self, request):
        """Device map view"""
        
        form = self.form(request.GET)
        #form = self.form_class(request.GET, request=request)
        
        if form.is_valid():
            interfaces = Interface.objects.all()
            vlan = form.cleaned_data['vlan']

            #print(form.fields["device_roles"].queryset)

            #form.cleaned_data["device_roles"] = form.fields["device_roles"].queryset

            #get devices based on the vlans
            interfaces = interfaces.filter(Q(untagged_vlan=vlan) | Q(tagged_vlans=vlan))
            devices = Device.objects.filter(interfaces__in=interfaces).distinct()

            device_roles = DeviceRole.objects.filter(devices__in=devices).distinct()

            # Get devices based on the roles
            if device_roles.exists():
                devices = devices.filter(role__in=device_roles)
                

            #get connected devices, if any
            for device in devices:
                connected_devices_qs = get_connected_devices(device, vlan)
                connected_wireless_devices = get_connected_wireless_devices(device=device, vlan=vlan)

                if connected_devices_qs.exists() or connected_wireless_devices.exists():
                    conn_data = True
                else:
                    conn_data = False

            geolocated_devices = {d: coords for d in devices if (coords := get_device_location(d))}
            non_geolocated_devices = set(devices) - set(geolocated_devices.keys())


            map_data = configure_leaflet_map("geomap", geolocated_devices, conn_data)
            map_data['vlan'] = vlan.id
            return render(request, self.template_name, context=dict(
                filter_form=form, map_data=map_data, non_geolocated_devices=non_geolocated_devices
            ))

        return render(
            request, self.template_name,
            context=dict(filter_form=self.form(initial=request.GET))
        )
    


class ConnectedCpeAjaxView(PermissionRequiredMixin, View):
    permission_required = ('dcim.view_device', 'dcim.view_cable')
    form = forms.ConnectedCpeForm

    def get(self, request, **kwargs):
        """List of CPE devices connected to the specified node device"""
        try:
            device = Device.objects.get(pk=kwargs.get('pk'))
            
        except Device.DoesNotExist:
            return JsonResponse({'status': False, 'error': 'Device not found'}, status=404)
        form = self.form(request.GET)
        
        if form.is_valid():
            data = form.cleaned_data
            
            #connected_devices_qs = get_connected_devices(device, vlan=data['vlan'])\
            #    .filter(device_role__name=plugin_settings['cpe_device_role']).order_by()
            wireless_connections = get_connected_wireless_devices(device, vlan=data['vlan'])

            
            connected_devices_qs = get_connected_devices(device, vlan=data['vlan'])
            
            
            connected_devices = [dict(id=d.id, name=d.name, url=d.get_absolute_url(), comments=d.comments)
                                 for d in connected_devices_qs]
            
            wireless_devices = [dict(id=d.id, name=d.name, url=d.get_absolute_url(), comments=d.comments) for d in wireless_connections]
            # Sorting list of CPE devices by the sequence of integers contained in the comments
            #connected_devices.sort(key=lambda d: tuple(int(n) for n in INTEGER_REGEXP.findall(d['comments'])))
            

            return JsonResponse(dict(status=True, cpe_devices=connected_devices, wl_connected=wireless_devices,
                                     device_type=f'{device.device_type.manufacturer.name} {device.device_type.model}'))
        else:
            return JsonResponse({'status': False, 'error': 'Form fields filled out incorrectly',
                                 'form_errors': form.errors}, status=404)
