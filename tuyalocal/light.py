"""
Simple platform to control **SOME** Tuya switch devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.tuya/
"""
import voluptuous as vol
from homeassistant.components.light import (
    LightEntity, PLATFORM_SCHEMA, ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_HS_COLOR, ATTR_TRANSITION,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP, SUPPORT_COLOR, SUPPORT_TRANSITION)
from homeassistant.const import (CONF_NAME, CONF_HOST, CONF_ID, CONF_SWITCHES, CONF_FRIENDLY_NAME)
from homeassistant.helpers.service import extract_entity_ids
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util
import time

CONF_DEVICE_ID = 'device_id'
CONF_LOCAL_KEY = 'local_key'
CONF_DEVICE_TYPE = 'device_type'

MAX_MIREDS = 500
MIN_MIREDS = 153

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_DEVICE_ID): cv.string,
    vol.Required(CONF_LOCAL_KEY): cv.string,
    vol.Optional(CONF_DEVICE_TYPE): cv.string,
})

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up of the Tuya switch."""
    from . import pytuya

    bulb_device = pytuya.BulbDevice(
            config.get(CONF_DEVICE_ID),
            config.get(CONF_HOST),
            config.get(CONF_LOCAL_KEY)
        )

    light = TuyaDevice(bulb_device, config.get(CONF_NAME), config.get(CONF_DEVICE_TYPE, 'dimmer'))

    add_devices([light])

class TuyaDevice(LightEntity):
    """Representation of a Tuya bulb or dimmer."""

    def __init__(self, device, name, devicetype):
        """Initialize the Tuya switch."""
        self._device = device
        self._name = name
        self._state = False
        self._devicetype = devicetype
        self._added_to_hass = False

        self._brightness = 0
        self._color = [0,0,0]
        self._colortemp = 0
        self._mode = 'white'

        # Subscribes to device updates
        self._device.subscribe(self.status_callback)

    async def async_added_to_hass(self):
        self._added_to_hass = True

    @property
    def should_poll(self):
        """We want polling since the listener thread sometimes exits and we need something that would trigger us to re-create it."""
        return True

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

        if self._devicetype == "bulb":
            attr["mode"] = self._mode

        return attr

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def hs_color(self):
        """Return the hs color values of this light."""
        # if the light is in 'white' mode, return white as the color
        if self._mode == "white":
            return color_util.color_RGB_to_hs(*[255, 255, 255])
        return color_util.color_RGB_to_hs(*self._color)

    @property
    def color_temp(self):
        """Return the color temperature of this light in mireds."""
        return self._colortemp

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._devicetype == "bulb":
            return SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_COLOR
        return SUPPORT_BRIGHTNESS

    def turn_on(self, **kwargs):
        """Turn Tuya bulb on."""

        brightness = self._brightness
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]

        # brightness needs to be between 25 and 255
        brightness = min(max(brightness, 25), 255)

        # Set color or color temperature
        if ATTR_HS_COLOR in kwargs:
            hs_color = kwargs.get(ATTR_HS_COLOR)
            rgb_color = color_util.color_hs_to_RGB(*hs_color)
            for i in range(3): self._device.set_colour(*rgb_color, brightness)
        elif ATTR_COLOR_TEMP in kwargs:
            colortemp = 255 - int((kwargs[ATTR_COLOR_TEMP] - MIN_MIREDS) * 255 / (MAX_MIREDS - MIN_MIREDS))
            for i in range(3): self._device.set_white(brightness, colortemp)
        else:
            if self._mode == 'colour':
                # Brightness changes need to be made via set_colour when the bulb is in colour mode
                for i in range(3): self._device.set_colour(*(self._color), brightness)
            else:
                # Set brightness
                for i in range(3): self._device.set_brightness(brightness)

    def turn_off(self, **kwargs):
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

        # '1' - device ON\OFF
        # '3' - brightness
        # RGB Bulb:
        #   '2' - mode (white or colour)
        #   '4' - color temperature
        #   '5' - color

        if '1' in status['dps']:
            self._state = status['dps']['1']

        if '2' in status['dps']:
            self._mode = status['dps']['2']
            
        if '3' in status['dps']:
            self._brightness = int(status['dps']['3'])

        if '4' in status['dps']:
            self._colortemp = MAX_MIREDS - int(status['dps']['4'] * (MAX_MIREDS - MIN_MIREDS) / 255)
        
        if '5' in status['dps']:
            stringColor = status['dps']['5']
            r = int(stringColor[0:2], 16) * 255 / self._brightness
            g = int(stringColor[2:4], 16) * 255 / self._brightness
            b = int(stringColor[4:6], 16) * 255 / self._brightness
            self._color = [r,g,b]

        if self._added_to_hass:
            # Tell HASS to update
            self.schedule_update_ha_state()
