"""
Support for AutoPi device tracking.
"""
from datetime import timedelta

from homeassistant.components.device_tracker import SOURCE_TYPE_GPS
from homeassistant.components.device_tracker.config_entry import TrackerEntity

from . import DOMAIN, AutoPiDevice

SCAN_INTERVAL = timedelta(seconds=10)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up of the AutoPi devices."""

    # Enumerate AutoPi devices and create a device tracker entity for each one
    for autoPIDevice in hass.data[DOMAIN]:
        async_add_entities([AutoPiDeviceTracker(autoPIDevice)])

class AutoPiDeviceTracker(TrackerEntity):
    """ AutoPi Device Tracker """

    def __init__(self, device : AutoPiDevice):
        self._device = device

    @property
    def should_poll(self):
        return True

    @property
    def name(self):
        return self._device.name

    @property
    def unique_id(self):
        return self._device.unique_id

    @property
    def icon(self):
        return "mdi:car"

    @property
    def source_type(self):
        return SOURCE_TYPE_GPS

    @property
    def latitude(self):
        return self._device.latitude

    @property
    def longitude(self):
        return self._device.longitude

    @property
    def extra_state_attributes(self):
        return self._device.attributes

    @property
    def device_info(self):
        return self._device.device_info

    def update(self):
        self._device.update()
