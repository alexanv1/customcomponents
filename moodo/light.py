"""
Simple platform to control Moodo Aroma Diffuser devices (exposed as lights to enable fan speed control via brightness)
"""

import logging
import json
import voluptuous as vol
import requests
import socketio
from datetime import timedelta


from homeassistant.components.light import (LightEntity, PLATFORM_SCHEMA, ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS)
from homeassistant.const import (CONF_NAME, CONF_HOST, CONF_ID, CONF_SWITCHES, CONF_FRIENDLY_NAME)
from homeassistant.helpers.service import extract_entity_ids
import homeassistant.helpers.config_validation as cv

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)

CONF_API_TOKEN = 'api_token'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_TOKEN): cv.string,
})

API_BASE_URL = "https://rest.moodo.co/api/boxes"
API_TOKEN = None
HEADERS = None

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up of the Moodo devices."""

    global HEADERS
    global API_TOKEN

    API_TOKEN = config.get(CONF_API_TOKEN)
    HEADERS = {"token": API_TOKEN, "accept":"application/json"}

    # Get the Moodo boxes
    _LOGGER.debug("Sending GET to {} with headers={}".format(API_BASE_URL, HEADERS))
    resp = requests.get(API_BASE_URL, headers=HEADERS)
    if resp.status_code != 200:
        # Something went wrong
        raise Exception('GET {} failed with status {}, error: {}'.format(API_BASE_URL, resp.status_code, resp.json()["error"]))

    # Enumerate Moodo boxes and create a device for each one
    for moodo_json in resp.json()['boxes']:
        moodo = MoodoDevice(hass, moodo_json['device_key'], moodo_json['id'], moodo_json['name'])
        add_devices([moodo])

class MoodoDevice(LightEntity):
    
    def __init__(self, hass, device_key, device_id, device_name):
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

        self.update_via_REST()
        self.listen_for_websocket_events()

    async def async_added_to_hass(self):
        self._added_to_hass = True

    def listen_for_websocket_events(self):
        self._socketio = socketio.Client()

        # Register socket.io event handlers
        _LOGGER.debug(f'{self._device_name}: Registering for websocket events...')
        self._socketio.on('connect', self.socketio_connect_handler)
        self._socketio.on('disconnect', self.socketio_disconnect_handler)
        self._socketio.on('log', self.socketio_log_handler)
        self._socketio.on('ws_event', self.socketio_event_handler)

        try:
            # Open the socket.io connection
            self._socketio.connect('https://ws.moodo.co:9090')
        except Exception as exception:
            # TODO: log
            _LOGGER.error(f'Failed to connect socket.io for {self._device_name}, will retry. Exception: {exception}')
            self._socketio = None

    def socketio_connect_handler(self):
        _LOGGER.info(f'Socket.io connected for {self._device_name}')

        if self._socketio is not None:
            # Authenticate since we're now connected
            self._socketio.emit('authenticate', API_TOKEN, False)

    def socketio_disconnect_handler(self):
        _LOGGER.info(f'Socket.io disconnected for {self._device_name}')
        self._socketio = None

    def socketio_log_handler(self, message):
        _LOGGER.info(f'Socket.io log message received for {self._device_name}, message: {message}')

        if (message.startswith("Authenticated")) and self._socketio is not None:
            self._socketio.emit('subscribe', self._device_id)

    def socketio_event_handler(self, event):
        _LOGGER.info(f'Socket.io event received for {self._device_name}, event: {event}')

        if event["type"] == "box_config":
            self.update_state(event["data"])

    def set_state(self, state, fan_volume):

        fan_speed = 0
        if state == True:
            fan_speed = 25

        # Turn ON or OFF
        json = {
                    "device_key": self._device_key,
                    "fan_volume": fan_volume * 100 / 255,           # Limit to 0..100
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
        resp = requests.post(API_BASE_URL, json=json, headers=HEADERS)
        if resp.status_code != 200:
            # Something went wrong
            raise Exception('POST {} (payload={}) for {} failed with status {}, error {}'.format(API_BASE_URL, json, self._device_name, resp.status_code, resp.json()))

        self._fan_volume = fan_volume
        self._state = state

    def turn_on(self, **kwargs):

        fan_volume = self._fan_volume
        if ATTR_BRIGHTNESS in kwargs:
            fan_volume = kwargs[ATTR_BRIGHTNESS]

        self.set_state(True, fan_volume)

    def turn_off(self, **kwargs):
        self.set_state(False, self._fan_volume)

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

        self._fan_volume = self._data["fan_volume"] * 255 / 100      # 0..255

        if self._added_to_hass:
            # Tell HASS to update
            _LOGGER.debug(f'{self._device_name}: Calling schedule_update_ha_state()')
            self.schedule_update_ha_state()

    def update_via_REST(self):
        
        # Retry 3 times
        MAX_RETRIES = 3
        for x in range(MAX_RETRIES):
            resp = None
            try:
                _LOGGER.debug("Sending GET to {} with headers={}".format(self._API_BOX_URL, HEADERS))
                resp = requests.get(self._API_BOX_URL, headers=HEADERS)
                if resp.status_code != 200:
                    # Something went wrong
                    raise Exception('GET {} failed with status {}, error: {}'.format(self._API_BOX_URL, resp.status_code, resp.json()["error"]))

                break
            except Exception as err:
                if x == (MAX_RETRIES - 1):
                    _LOGGER.error('GET {} failed with exception {}'.format(self._API_BOX_URL, err))
                    return      # Just return out, state will be left as what it was previously

                _LOGGER.warning('GET {} failed with exception {}. Will retry'.format(self._API_BOX_URL, err))

        self.update_state(resp.json()["box"])

    def update(self):

        UPDATE_COUNTER_VALUE_TO_UPDATE_VIA_REST = 10

        self._update_counter += 1

        # Check if we have a socket.io connection and try to reconnect if we don't
        if self._socketio is None:
            self.listen_for_websocket_events()

            # Refresh via REST since we may have missed updates when websocket wasn't connected
            _LOGGER.debug(f'{self._device_name}: Will update via REST since websocket is not connected')
            self.update_via_REST()
        elif self._update_counter == UPDATE_COUNTER_VALUE_TO_UPDATE_VIA_REST:
            # Update via REST since we reached the counter threshold
            _LOGGER.debug(f'{self._device_name}: Will update via REST since we reached the update counter threshold')
            self.update_via_REST()
            self._update_counter = 0

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
    def brightness(self):
        # Return fan volume as brightness
        return self._fan_volume

    @property
    def supported_features(self):
        return SUPPORT_BRIGHTNESS
