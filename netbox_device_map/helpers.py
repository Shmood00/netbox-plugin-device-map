from packaging import version
from packaging.version import Version

from dcim.models import Device
from wireless.models import WirelessLink
from django.db.models import QuerySet, Q
from ipam.models import VLAN
from django.conf import settings
from netbox.settings import VERSION

from .settings import plugin_settings

def sanitize_version(ver):
    return ver.split("-")[0]

LOCATION_CF_NAME = plugin_settings['device_geolocation_cf']




NETBOX_VERSION = sanitize_version(settings.RELEASE.full_version)
LatLon = tuple[float, float]


def get_device_location(device: Device) -> LatLon | None:
    """Extract device geolocation from special custom field"""

    """print(device.latitude)

    if location_cf := device.custom_field_data.get(LOCATION_CF_NAME):
        return tuple(map(float, location_cf.replace(' ', '').split(',', maxsplit=1)))"""
    
    if device.latitude and device.longitude:
        return (device.latitude, device.longitude)


def get_connected_wireless_devices(device: Device, vlan: VLAN = None) -> QuerySet[Device]:

    included_interfaces = device.interfaces.all()

    if vlan is not None:
        included_interfaces = included_interfaces.filter(Q(untagged_vlan=vlan) | Q(tagged_vlans=vlan))
    

    return Device.objects.filter(
        Q(interfaces__wireless_link__interface_b__in=included_interfaces) | 
        Q(interfaces__wireless_link__interface_a__in=included_interfaces)
    ).exclude(pk=device.id)


def get_connected_devices(device: Device, vlan: VLAN = None) -> QuerySet[Device]:
    """Get list of connected devices to the specified device.
    If the vlan is specified, return only devices connected to the interfaces of the specified device
    containing the specified VLAN"""
    included_interfaces = device.interfaces.all()

    
    
    if vlan is not None:
        included_interfaces = included_interfaces.filter(Q(untagged_vlan=vlan) | Q(tagged_vlans=vlan))

    
    
    if Version(NETBOX_VERSION) < version.parse('3.3.0'):
        
        return Device.objects.filter(interfaces___link_peer_id__in=included_interfaces)
    else:
        """ We want to check wireless connections for my instance """
        
        #test = WirelessLink.objects.filter(Q(_interface_a_device_id = device.id))[0]
        

        return Device.objects.filter(
            interfaces__cable__terminations__interface__in=device.interfaces.all()
        ).exclude(pk=device.id)


def are_devices_connected(device_a: Device, device_b: Device) -> bool:
    """Determines whether devices are connected to each other by a direct connection"""
    if Version(NETBOX_VERSION) < version.parse('3.3.0'):
        queryset = Device.objects.filter(interfaces___link_peer_id__in=device_a.interfaces.all(), id=device_b.id)
    else:
        queryset = Device.objects.filter(
            interfaces__cable__terminations__interface__in=device_a.interfaces.all(), id=device_b.id)
    return bool(queryset.values('pk'))
