"""
Simple platform to control **SOME** Tuya switch devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.tuya/
"""
import voluptuous as vol
from homeassistant.components.switch import SwitchEntity, PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, CONF_HOST, CONF_ID, CONF_SWITCHES, CONF_FRIENDLY_NAME)
from homeassistant.helpers.service import extract_entity_ids
import homeassistant.helpers.config_validation as cv
import time

CONF_DEVICE_ID = 'device_id'
CONF_LOCAL_KEY = 'local_key'
CONF_DEVICE_TYPE = 'device_type'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_DEVICE_ID): cv.string,
    vol.Required(CONF_LOCAL_KEY): cv.string,
    vol.Optional(CONF_DEVICE_TYPE): cv.string,
})

SWITCHES = []

def service_to_entities(hass, service):
    """Return the known devices that a service call mentions."""
    entity_ids = extract_entity_ids(hass, service)
    if entity_ids:
        entities = [entity for entity in SWITCHES
                    if entity.entity_id in entity_ids]
    else:
        entities = list(SWITCHES)

    return entities

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up of the Tuya switch."""
    from . import pytuya

    global SWITCHES

    switch_device = pytuya.OutletDevice(
            config.get(CONF_DEVICE_ID),
            config.get(CONF_HOST),
            config.get(CONF_LOCAL_KEY)
        )

    switch = TuyaDevice(switch_device, config.get(CONF_NAME), config.get(CONF_DEVICE_TYPE, 'switch'))

    add_devices([switch])
    SWITCHES.append(switch)

    def handle_set_diffuser_mist_mode(call):
        mode = call.data.get('mode', 'continuous')

        for diffuser in service_to_entities(hass, call):
            diffuser.set_diffuser_mist_mode(mode)

    hass.services.register('tuyalocal', 'set_diffuser_mist_mode', handle_set_diffuser_mist_mode)

class TuyaDevice(SwitchEntity):
    """Representation of a Tuya switch."""

    def __init__(self, device, name, devicetype):
        """Initialize the Tuya switch."""
        self._device = device
        self._name = name
        self._state = False
        self._devicetype = devicetype
        self._added_to_hass = False

        # Diffuser state
        self._mistmode = 'off'

        # Humidifier state
        self._foglevel = 'low'
        self._waterlow = False
        self._ledlights = True

        # Subscribes to device updates
        self._device.subscribe(self.status_callback)

    async def async_added_to_hass(self):
        self._added_to_hass = True

    @property
    def should_poll(self):
        """We want polling since the listener thread sometimes exits and we need something that would trigger us to re-create it."""
        return True

    @property
    def unique_id(self):
        return f'tuya_{self._device.device_id}'

    @property
    def name(self):
        """Get name of Tuya switch."""
        return self._name

    @property
    def is_on(self):
        """Check if Tuya switch is on."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}

        if self._devicetype == "diffuser":
            attr["mistmode"] = self._mistmode

        if self._devicetype == "humidifier":
            attr["foglevel"] = self._foglevel
            attr["led_lights"] = self._ledlights
            attr["water_low"] = self._waterlow

        return attr

    def turn_on(self, **kwargs):
        """Turn Tuya switch on."""
        for i in range(3): self._device.set_status(True)

    def turn_off(self, **kwargs):
        """Turn Tuya switch on."""
        for i in range(3): self._device.set_status(False)

    def update(self):
        """Retrieve latest state."""
        self._device.async_status()
        return True

    def status_callback(self):
        """Get state of Tuya device when callback is received."""

        status = self._device.status()
        if 'dps' not in status:
            return

        # '1'   - device ON\OFF
        # Diffuser:
            # '101' - Diffuser mist mode
            # '6'   - Humidifier fog level
            # '11'  - Humidifier led lights
        # Humidifier:
            # '101' - Humidifier water low

        if '1' in status['dps']:
            self._state = status['dps']['1']

        if self._devicetype == "diffuser":
            if '101' in status['dps']:
                mistmode = status['dps']['101']
                if mistmode == "1":
                    self._mistmode = 'continuous'
                elif mistmode == "2":
                    self._mistmode = 'intermittent'
                else:
                    self._mistmode = 'off'

        if self._devicetype == "humidifier":
            if '6' in status['dps']:
                foglevel = status['dps']['6']
                if foglevel == "0":
                    self._foglevel = 'off'
                elif foglevel == "1":
                    self._foglevel = 'low'
                elif foglevel == "2":
                    self._foglevel = 'medium'
                else:
                    self._foglevel = 'high'

            if '11' in status['dps']:
                self._ledlights = status['dps']['11']
                
            if '101' in status['dps']:
                self._waterlow = status['dps']['101']
        
        if self._added_to_hass:
            # Tell HASS to update
            self.schedule_update_ha_state()

    def set_diffuser_mist_mode(self, mode):
        """Update Diffuser mist mode settings."""
        self._device.set_diffuser_mist_mode(mode)
