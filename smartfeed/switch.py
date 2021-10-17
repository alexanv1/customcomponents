"""
Switch platform to control PetSafe SmartFeed devices
"""
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.components.switch import SwitchEntity

from . import DOMAIN, get_device_info

SCAN_INTERVAL = timedelta(seconds=30)

async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up SmartFeed switch entities."""

    for feederDevice in hass.data[DOMAIN]:
        async_add_entities([SmartFeedSwitch(hass, feederDevice)])

class SmartFeedSwitch(SwitchEntity):
    
    def __init__(self, hass, feeder):
        self._feeder = feeder
        self._hass = hass

    def turn_on(self, **kwargs):
        self._feeder.paused = False
        self._feeder.update_data()

    def turn_off(self, **kwargs):
        self._feeder.paused = True
        self._feeder.update_data()

    def update(self):
        self._feeder.update_data()

    @property
    def device_info(self):
        return get_device_info(self._feeder)

    @property
    def should_poll(self):
        return True

    @property
    def name(self):
        return f'{self._feeder.friendly_name} Feeder'

    @property
    def unique_id(self):
        return self._feeder.api_name

    @property
    def available(self):
        return self._feeder.available

    @property
    def is_on(self):
        return self._feeder.paused == False

    @property
    def extra_state_attributes(self):
        data = self._feeder.data_json
        attributes = {}
        attributes["battery_level_description"] = self._feeder.battery_level
        attributes["battery_level"] = self._feeder.battery_level_int
        attributes["is_food_low"] = data["is_food_low"]
        attributes["connection_status"] = data["connection_status"]
        attributes["connection_status_timestamp"] = data["connection_status_timestamp"]
        
        schedules = {}
        for schedule in data["schedules"]:
            schedules[schedule["time"]] = f'{float(schedule["amount"]) / 8} cups'

        attributes["schedule"] = schedules
        attributes["settings"] = data["settings"]

        return attributes

    @property
    def icon(self):
        if self._feeder.data_json["settings"]["pet_type"] == 'cat':
            return 'mdi:cat'
        return 'mdi:dog'