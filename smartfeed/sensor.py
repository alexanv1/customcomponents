"""
Switch platform to control PetSafe SmartFeed devices
"""
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.components.sensor import (
    DEVICE_CLASS_BATTERY,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import PERCENTAGE

from . import DOMAIN, get_device_info

SCAN_INTERVAL = timedelta(seconds=30)

async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up SmartFeed sensor entities."""

    for feederDevice in hass.data[DOMAIN]:
        async_add_entities([SmartFeedBatterySensor(feederDevice)])

class SmartFeedBatterySensor(SensorEntity):

    entity_description = SensorEntityDescription(
        key="backup_battery",
        name="Battery Backup",
        device_class=DEVICE_CLASS_BATTERY,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    )

    def __init__(self, feeder):
        self._feeder = feeder

    @property
    def device_info(self):
        return get_device_info(self._feeder)

    @property
    def name(self):
        return f'{self._feeder.friendly_name} Feeder {self.entity_description.name}'

    @property
    def unique_id(self):
        return f'{self._feeder.api_name}_{self.entity_description.key}'

    @property
    def available(self):
        return self._feeder.available

    @property
    def native_value(self):
        return self._feeder.battery_level_int

    @property
    def should_poll(self):
        return True

    def update(self):
        # Data updates are handled via the switch platform
        return