"""
Switch platform to control PetSafe SmartFeed devices
"""
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers import entity_platform

import voluptuous as vol

from . import DOMAIN, get_device_info

SCAN_INTERVAL = timedelta(seconds=30)

SERVICE_REPEAT_LAST_FEEDING = "repeat_last_feeding"
SERVICE_FEED = "feed"

ATTR_AMOUNT = "amount"

SERVICE_FEED_SCHEMA = {
    vol.Required(ATTR_AMOUNT): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=36)
    ),
}

async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up SmartFeed switch entities."""

    for feederDevice in hass.data[DOMAIN]:
        async_add_entities([SmartFeedSwitch(feederDevice)])

    platform = entity_platform.async_get_current_platform()

    # This will call SmartFeedSwitch.feed(amount=VALUE)
    platform.async_register_entity_service(
        SERVICE_REPEAT_LAST_FEEDING, {}, SmartFeedSwitch.repeat_last_feeding.__name__
    )

    # This will call SmartFeedSwitch.repeat_last_feeding()
    platform.async_register_entity_service(
        SERVICE_FEED, SERVICE_FEED_SCHEMA, SmartFeedSwitch.feed.__name__
    )

class SmartFeedSwitch(SwitchEntity):
    
    def __init__(self, feeder):
        self._feeder = feeder

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
    
    def repeat_last_feeding(self):
        self._feeder.repeat_feed()

    def feed(self, amount : int):
        self._feeder.feed(amount = amount)