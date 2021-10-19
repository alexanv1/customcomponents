import logging

from homeassistant.components.sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import generate_entity_id

from . import DOMAIN, BRIDGE_KEY, BLINDS_KEY, get_device_info

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up MySmartBlinds sensor entities."""

    bridge = hass.data[DOMAIN][BRIDGE_KEY]
    blinds = hass.data[DOMAIN][BLINDS_KEY]

    entities = []
    for blind in blinds:
        entities += [
            MySmartBlindBatterySensor(bridge, blind, generate_entity_id('sensor.{}_battery', blind.name, hass=hass)),
            MySmartBlindRssiSensor(bridge, blind, generate_entity_id('sensor.{}_rssi', blind.name, hass=hass))
        ]

    bridge.entities += entities
    async_add_entities(entities)

class MySmartBlindSensor(SensorEntity):
    """A single MySmartBlinds sensor, accessed through the Smart Bridge."""

    def __init__(self, bridge, blind, entity_id=None):
        self._bridge = bridge
        self._blind = blind
        self._available = True

        self.entity_id = entity_id
        
    @property
    def device_info(self):
        return get_device_info(self._blind)

    @property
    def available(self):
        return self._available

    @property
    def should_poll(self):
        return False

class MySmartBlindBatterySensor(MySmartBlindSensor):
    """A single MySmartBlinds battery sensor, accessed through the Smart Bridge."""

    entity_description = SensorEntityDescription(
        key="battery",
        name="Battery",
        device_class=DEVICE_CLASS_BATTERY,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    )

    def __init__(self, bridge, blind, entity_id=None):
        super().__init__(bridge, blind, entity_id)
        self._battery_level = 0

    @property
    def name(self):
        return f"{self._blind.name} Battery"

    @property
    def unique_id(self):
        return f'mysmartblinds_{self._blind.encoded_mac}_battery'

    @property
    def native_value(self):
        return self._battery_level

    def update(self):

        state = self._bridge.get_blind_state(self._blind)
        
        if state is not None:
            if state.battery_level != 0:
                self._battery_level = min(max(state.battery_level, 0), 100)
            self._available = True
        else:
            self._available = False

class MySmartBlindRssiSensor(MySmartBlindSensor):
    """A single MySmartBlinds RSSI sensor, accessed through the Smart Bridge."""

    entity_description = SensorEntityDescription(
        key="rssi",
        name="RSSI",
        device_class=DEVICE_CLASS_SIGNAL_STRENGTH,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    )

    def __init__(self, bridge, blind, entity_id=None):
        super().__init__(bridge, blind, entity_id)
        self._rssi = 0

    @property
    def name(self):
        return f"{self._blind.name} RSSI"

    @property
    def unique_id(self):
        return f'mysmartblinds_{self._blind.encoded_mac}_rssi'

    @property
    def native_value(self):
        return self._rssi

    def update(self):

        state = self._bridge.get_blind_state(self._blind)
        
        if state is not None:
            self._rssi = state.rssi
            self._available = True
        else:
            self._available = False
