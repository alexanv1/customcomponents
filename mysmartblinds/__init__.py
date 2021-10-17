"""
Support for MySmartBlinds Smart Bridge

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/cover.mysmartblinds_bridge
"""

import asyncio
import logging

from . import smartblinds

from collections import defaultdict
from contextlib import contextmanager
from datetime import timedelta, datetime
from requests.exceptions import HTTPError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (CONF_PASSWORD, CONF_USERNAME)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import track_point_in_utc_time, track_time_interval
from homeassistant.util import utcnow

from functools import wraps

_LOGGER = logging.getLogger(__name__)

CONF_INCLUDE_ROOMS = 'include_rooms'

POSITION_BATCHING_DELAY_SEC = 0.25
POLLING_INTERVAL_MINUTES = 5

DOMAIN = 'mysmartblinds'

BRIDGE_KEY = 'bridge'
BLINDS_KEY = 'blinds'
ROOMS_KEY = 'rooms'

PLATFORMS = ["cover", "sensor"]

async def async_setup(hass, config):
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SmartFeed from a config entry."""
    
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    # Get the devices
    bridge, blinds, rooms = await hass.async_add_executor_job(create_bridge_and_get_blinds, hass, username, password)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][BRIDGE_KEY] = bridge
    hass.data[DOMAIN][BLINDS_KEY] = blinds
    hass.data[DOMAIN][ROOMS_KEY] = rooms

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True

def create_bridge_and_get_blinds(hass, username, password):
    bridge = MySmartBlindsBridge(hass, username, password)

    blinds, rooms = bridge.get_blinds_and_rooms()

    for blind in blinds:
        _LOGGER.info("Found %s blind", blind)

    return bridge, blinds, rooms

def timed(func):
    @contextmanager
    def timing():
        start_ts = datetime.now()
        yield
        elapsed = datetime.now() - start_ts
        _LOGGER.debug('{}() took {:.2f} seconds'.format(func.__name__, elapsed.total_seconds()))

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not asyncio.iscoroutinefunction(func):
            with timing():
                return func(*args, **kwargs)
        else:
            async def async_wrapper():
                with timing():
                    return await func(*args, **kwargs)

            return async_wrapper()

    return wrapper

def get_device_info(blind):
    return {
        "name": blind.name,
        "identifiers": {(DOMAIN, blind.encoded_mac)},
        "model": "MySmartBlinds Windows Blind",
        "manufacturer": "MySmartBlinds",
    }

class MySmartBlindsBridge:
    def __init__(self, hass, username, password):
        self._hass = hass
        self._sbclient = smartblinds.SmartBlindsClient(username=username, password=password)
        self._blinds = []
        self._rooms = []
        self._blind_states = {}
        self._blinds_by_mac = {}
        self._pending_blind_positions = {}
        self._cancel_pending_blind_position_timer = None
        self.entities = []

        track_time_interval(hass, self._update_periodic, timedelta(minutes=POLLING_INTERVAL_MINUTES))
        track_point_in_utc_time(hass, self._update_periodic, utcnow() + timedelta(seconds=10))

    @timed
    def get_blinds_and_rooms(self):
        try:

            self._sbclient.login()
            self._blinds, self._rooms = self._sbclient.get_blinds_and_rooms()
            self._blinds_by_mac.clear()
            for blind in self._blinds:
                self._blinds_by_mac[blind.encoded_mac] = blind

            # Filter out duplicates
            return self._blinds_by_mac.values(), self._rooms

        except Exception:

            _LOGGER.error("Error logging in or listing devices %s", exc_info=True)
            raise

    def get_blind_state(self, blind):

        if blind.encoded_mac in self._blind_states:
            return self._blind_states[blind.encoded_mac]
        else:
            return None

    def set_blind_position(self, blind, position):
        
        self._pending_blind_positions[blind.encoded_mac] = position
        
        if self._cancel_pending_blind_position_timer is not None:
            self._cancel_pending_blind_position_timer()

        self._cancel_pending_blind_position_timer = track_point_in_utc_time(self._hass,
                                                                            self._set_blind_positions,
                                                                            utcnow() + timedelta(seconds=POSITION_BATCHING_DELAY_SEC))

    @timed
    def update_blind_states(self):
        try:

            self._blind_states = self._sbclient.get_blinds_state(self._blinds)
            _LOGGER.info("Blind states: %s", self._blind_states)

        except HTTPError as http_error:
            
            if http_error.response.status_code == 401:
                self._sbclient.login()
                self.update_blind_states()
            else:
                raise

    @timed
    def _set_blind_positions(self, time=None):
        self._cancel_pending_blind_position_timer = None
        
        positions_blinds = defaultdict(list)
        for blind, position in self._pending_blind_positions.items():
            positions_blinds[position].append(blind)

        self._pending_blind_positions.clear()

        try:

            for position, blind_macs in positions_blinds.items():
                _LOGGER.info("Moving %s to %d", ', '.join(blind_macs), position)

                blinds = [self._blinds_by_mac[blind] for blind in blind_macs]
                new_blind_states = self._sbclient.set_blinds_position(blinds, position)
                self._blind_states.update(new_blind_states)

            _LOGGER.info("Blind states: %s", self._blind_states)

            for entity in self.entities:
                entity.schedule_update_ha_state(force_refresh=True)
                
        except HTTPError as http_error:

            if http_error.response.status_code == 401:
                self._sbclient.login()
                return self._set_blind_positions()
            else:
                raise

    @timed
    def _update_periodic(self, time=None):
        try:

            self.update_blind_states()
            for entity in self.entities:
                entity.schedule_update_ha_state(force_refresh=True)

        except Exception:
            _LOGGER.error("Error updating periodic state", exc_info=True)
