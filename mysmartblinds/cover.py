import logging

from homeassistant.const import (ATTR_BATTERY_LEVEL)
from homeassistant.components.cover import (
    CoverEntity,
    ATTR_POSITION,
    SUPPORT_SET_POSITION,
    SUPPORT_OPEN,
    SUPPORT_CLOSE,
    DEVICE_CLASS_BLIND
)
from homeassistant.components.group.cover import CoverGroup
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import generate_entity_id

from . import DOMAIN, BRIDGE_KEY, BLINDS_KEY, ROOMS_KEY, CONF_INCLUDE_ROOMS, get_device_info

_LOGGER = logging.getLogger(__name__)

ATTR_RSSI_LEVEL = 'rssi_level'

async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up MySmartBlinds cover entities."""

    bridge = hass.data[DOMAIN][BRIDGE_KEY]
    blinds = hass.data[DOMAIN][BLINDS_KEY]
    rooms = hass.data[DOMAIN][ROOMS_KEY]

    include_rooms = config_entry.data[CONF_INCLUDE_ROOMS]

    entities = []
    for blind in blinds:
        entities += [MySmartBlindCover(bridge, blind, generate_entity_id('cover.{}', blind.name, hass=hass))]

    if include_rooms:
        entities += [CoverGroup(
            room.name,
            list(map(
                lambda entity: entity.entity_id,
                filter(lambda entity: entity._blind.room_id == room.uuid, entities))))
            for room in rooms]

    bridge.entities += entities
    async_add_entities(entities)

class MySmartBlindCover(CoverEntity):
    """A single MySmartBlinds cover, accessed through the Smart Bridge."""

    def __init__(self, bridge, blind, entity_id=None):
        self._bridge = bridge
        self._blind = blind
        self._position = 0
        self._available = True
        self._battery_level = 0
        self._rssi = 0

        self.entity_id = entity_id

    @property
    def device_info(self):
        return get_device_info(self._blind)

    @property
    def name(self):
        return self._blind.name

    @property
    def device_class(self):
        return DEVICE_CLASS_BLIND

    @property
    def unique_id(self):
        return f'mysmartblinds_{self._blind.encoded_mac}'

    @property
    def supported_features(self):
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION

    @property
    def available(self):
        return self._available

    @property
    def is_closed(self):
        if self._position is None:
            return None

        return self._position >= 190 or self._position <= 10

    @property
    def current_cover_position(self):
        """Return current position of cover. None is unknown, 0 is closed, 100 is fully open."""
        if self._position is None:
            return None

        if self._position > 100:
            return 200 - self._position

        # round down
        if self._position <= 5:
            return 0

        # round up
        if self._position >= 95:
            return 100

        return self._position

    @property
    def extra_state_attributes(self):
        attr = {
            ATTR_BATTERY_LEVEL: self._battery_level,
            ATTR_RSSI_LEVEL: self._rssi,
        }
        return attr

    @property
    def should_poll(self):
        return False

    def close_cover(self, **kwargs):
        self._set_position(0)

    def open_cover(self, **kwargs):
        self._set_position(100)

    def set_cover_position(self, **kwargs):
        self._set_position(kwargs[ATTR_POSITION])

    def update(self):
        
        state = self._bridge.get_blind_state(self._blind)
        
        if state is not None:

            _LOGGER.info("Updated %s: %s", self.name, state)

            if state.position is not -1:
                self._position = state.position

            self._rssi = state.rssi
            self._battery_level = min(max(state.battery_level, 0), 100)
            self._available = True
        else:
            self._available = False

    def _set_position(self, position):
        self._position = position
        self._bridge.set_blind_position(self._blind, position)
        self.schedule_update_ha_state()
