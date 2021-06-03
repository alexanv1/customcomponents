"""
Simple platform to control Moodo Aroma Diffuser devices (exposed as lights to enable fan speed control via brightness)
"""

import logging
import json
import voluptuous as vol
from datetime import timedelta

from homeassistant.components.switch import (SwitchEntity, PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv

from .devices import get_feeders

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)

CONF_API_TOKEN = 'api_token'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_TOKEN): cv.string,
})

API_TOKEN = None

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up of the Moodo devices."""

    token = config.get(CONF_API_TOKEN)

    # Get the devices
    feeders = get_feeders(token)

    for feederDevice in feeders:
        add_devices([SmartFeedDevice(hass, feederDevice)])

class SmartFeedDevice(SwitchEntity):
    
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
            schedule_string = f'{schedule["time"]}: {float(schedule["amount"])} cups'
            schedules[schedule["time"]] = f'{float(schedule["amount"]) / 8} cups'

        attributes["schedule"] = schedules
        attributes["settings"] = data["settings"]

        return attributes

    @property
    def icon(self):
        if self._feeder.data_json["settings"]["pet_type"] == 'cat':
            return 'mdi:cat'
        return 'mdi:dog'