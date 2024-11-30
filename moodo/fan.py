"""
Simple platform to control Moodo Aroma Diffuser devices
"""

import logging
import aiohttp
import asyncio
import socketio_v4 as socketio
from datetime import datetime
from datetime import timedelta
from typing import Any, Optional

from homeassistant.components.fan import (FanEntity, FanEntityFeature)

from . import DOMAIN, CONF_API_TOKEN

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)

API_BASE_URL = "https://rest.moodo.co/api/boxes"
API_TOKEN = None
HEADERS = None

SOCKETIO_LOCK = asyncio.Lock()

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up of the Moodo devices."""

    global HEADERS
    global API_TOKEN

    API_TOKEN = config_entry.data[CONF_API_TOKEN]
    HEADERS = {"token": API_TOKEN, "accept":"application/json", "user-agent":f"SomeUserAgent {datetime.utcnow()}"}

    # Get the Moodo boxes
    resp_json = await get_devices()

    # Enumerate Moodo boxes and create a device for each one
    for moodo_json in resp_json['boxes']:
        moodo = MoodoDevice(moodo_json['device_key'], moodo_json['id'], moodo_json['name'])
        async_add_entities([moodo], update_before_add=True)

async def get_devices():
    _LOGGER.debug("Sending GET to {} with headers={}".format(API_BASE_URL, HEADERS))

    async with aiohttp.ClientSession() as session:
        async with session.get(API_BASE_URL, headers = HEADERS) as resp:
            if resp.status != 200:
                # Something went wrong
                raise Exception('GET {} failed with status {}, error: {}'.format(API_BASE_URL, resp.status, await resp.text()))

            return await resp.json()

UPDATE_COUNTER_VALUE_TO_UPDATE_VIA_REST = 10

class MoodoDevice(FanEntity):
    
    def __init__(self, device_key, device_id, device_name):
        self._update_counter = 0
        self._added_to_hass = False
        self._device_key = device_key
        self._device_id = device_id
        self._device_name = device_name + " Aroma Diffuser"

        self._API_BOX_URL = API_BASE_URL + "/" + str(self._device_key)

        _LOGGER.info('Setting up {}, device_key={}'.format(self._device_name, self._device_key))

        self._data = {}
        self._available = False
        self._state = False
        self._fan_volume = 0

        self._socketio = None

    async def async_added_to_hass(self):
        self._added_to_hass = True

    async def listen_for_websocket_events(self):
        async with SOCKETIO_LOCK:
            self._socketio = socketio.AsyncClient()

            # Register socket.io event handlers
            _LOGGER.debug(f'{self._device_name}: Registering for websocket events...')
            self._socketio.on('connect', self.socketio_connect_handler)
            self._socketio.on('disconnect', self.socketio_disconnect_handler)
            self._socketio.on('log', self.socketio_log_handler)
            self._socketio.on('ws_event', self.socketio_event_handler)

            try:
                # Open the socket.io connection
                await self._socketio.connect('https://ws.moodo.co:9090')
            except Exception as exception:
                _LOGGER.error(f'Failed to connect socket.io for {self._device_name}, will retry. Exception: {exception}')
                self._socketio = None

    async def socketio_connect_handler(self):
        _LOGGER.info(f'Socket.io connected for {self._device_name}')

        if self._socketio is not None:
            # Authenticate since we're now connected
            await self._socketio.emit('authenticate', API_TOKEN, False)

    async def socketio_disconnect_handler(self):
        _LOGGER.info(f'Socket.io disconnected for {self._device_name}')
        self._socketio = None

    async def socketio_log_handler(self, message):
        _LOGGER.info(f'Socket.io log message received for {self._device_name}, message: {message}')

        if (message.startswith("Authenticated")) and self._socketio is not None:
            await self._socketio.emit('subscribe', self._device_id)

    def socketio_event_handler(self, event):
        _LOGGER.info(f'Socket.io event received for {self._device_name}, event: {event}')

        if event["type"] == "box_config":
            self.update_state(event["data"])

    async def async_set_state(self, state, fan_volume):

        fan_speed = 0
        if state == True:
            fan_speed = 25

        # Turn ON or OFF
        json = {
                    "device_key": self._device_key,
                    "fan_volume": fan_volume,
                    "box_status": 1,
                    "settings_slot0":
                    {
                        "fan_speed": fan_speed,
                        "fan_active": state
                    },
                    "settings_slot1":
                    {
                        "fan_speed": fan_speed,
                        "fan_active": state
                    },
                    "settings_slot2":
                    {
                        "fan_speed": fan_speed,
                        "fan_active": state
                    },
                    "settings_slot3":
                    {
                        "fan_speed": fan_speed,
                        "fan_active": state
                    }
                }

        _LOGGER.debug("Sending POST to {} with headers={} json={}".format(API_BASE_URL, HEADERS, json))
        async with aiohttp.ClientSession() as session:
            async with session.post(API_BASE_URL, json=json, headers = HEADERS) as resp:
                if resp.status != 200:
                    # Something went wrong
                    raise Exception('POST {} (payload={}) for {} failed with status {}, error {}'.format(API_BASE_URL, json, self._device_name, resp.status, await resp.text()))

        self._fan_volume = fan_volume
        self._state = state

    async def async_turn_on(
        self,
        speed: Optional[str] = None,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None, 
        **kwargs: Any
    ) -> None:

        fan_volume = self._fan_volume
        if percentage is not None:
            fan_volume = percentage
        
        if fan_volume == 0:
            fan_volume = 75

        await self.async_set_state(True, fan_volume)

    async def async_turn_off(self, **kwargs):
        await self.async_set_state(False, 0)

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self.async_turn_off()
        else:
            await self.async_set_state(True, percentage)

    def update_state(self, data):
        self._data = data
        self._available = self._data["is_online"]

        # We consider the Moodo to be on if any fan is active
        # Note, box.box_status reports 1 even if no fans are active (i.e. Moodo treats this case as 'on' state but we don't)
        self._state = False
        if self._data["box_status"] == 1:
            for settings in self._data["settings"]:
                if settings["fan_active"] == True:
                    self._state = True
                    break

        self._fan_volume = self._data["fan_volume"]

        if self._added_to_hass:
            # Tell HASS to update
            _LOGGER.debug(f'{self._device_name}: Calling schedule_update_ha_state()')
            self.schedule_update_ha_state()

    async def update_via_REST(self):
        
        # Retry 3 times
        MAX_RETRIES = 3

        async with aiohttp.ClientSession() as session:
        
            for x in range(MAX_RETRIES):
                try:
                    _LOGGER.debug("Sending GET to {} with headers={}".format(self._API_BOX_URL, HEADERS))
                    async with session.get(self._API_BOX_URL, headers = HEADERS) as resp:
                        
                        if resp.status != 200:
                            # Something went wrong
                            raise Exception('GET {} failed with status {}, error: {}'.format(self._API_BOX_URL, resp.status, await resp.text()))

                        resp_json = await resp.json()
                        self.update_state(resp_json["box"])
                        return

                except Exception as err:
                    
                    if x == (MAX_RETRIES - 1):
                        _LOGGER.error('GET {} failed with exception {}'.format(self._API_BOX_URL, err))
                        return      # Just return out, state will be left as what it was previously

                    _LOGGER.warning('GET {} failed with exception {}. Will retry'.format(self._API_BOX_URL, err))

    async def async_update(self):

        self._update_counter += 1

        # Check if we have a socket.io connection and try to reconnect if we don't
        if self._socketio is None:
            await self.listen_for_websocket_events()

            # Refresh via REST since we may have missed updates when websocket wasn't connected
            _LOGGER.debug(f'{self._device_name}: Will update via REST since websocket was not connected')
            await self.update_via_REST()
        elif self._update_counter == UPDATE_COUNTER_VALUE_TO_UPDATE_VIA_REST:
            # Update via REST since we reached the counter threshold
            _LOGGER.debug(f'{self._device_name}: Will update via REST since we reached the update counter threshold')
            await self.update_via_REST()
            self._update_counter = 0

    @property
    def device_info(self):
        return {
            "name": self.name,
            "identifiers": {(DOMAIN, self.unique_id)},
            "model": "Moodo Smart Aroma Diffuser",
            "manufacturer": "Moodo",
        }

    @property
    def should_poll(self):
        return True

    @property
    def name(self):
        return self._device_name

    @property
    def unique_id(self):
        return self._device_id

    @property
    def available(self):
        return self._available

    @property
    def is_on(self):
        return self._state

    @property
    def extra_state_attributes(self):
        attributes = self._data.copy()
        attributes["Slot 1"] = self._data["settings"][0]
        attributes["Slot 2"] = self._data["settings"][1]
        attributes["Slot 3"] = self._data["settings"][2]
        attributes["Slot 4"] = self._data["settings"][3]
        attributes.pop("settings")
        return attributes

    @property
    def percentage(self):
        """Return the current speed."""
        return self._fan_volume

    @property
    def supported_features(self):
        return FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_OFF | FanEntityFeature.TURN_ON

    @property
    def icon(self):
        return 'mdi:flower'
