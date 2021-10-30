"""
Switch platform to control PetSafe SmartFeed devices
"""
from datetime import datetime, timedelta
from dateutil import tz

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
        async_add_entities([SmartFeedBatterySensor(feederDevice), SmartFeedLastFeedingSensor(feederDevice)], update_before_add = True)


class SmartFeedSensor(SensorEntity):

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
    def should_poll(self):
        return True

    def update(self):
        # Data updates are handled via the switch platform
        return

class SmartFeedBatterySensor(SmartFeedSensor):

    entity_description = SensorEntityDescription(
        key="backup_battery",
        name="Battery Backup",
        device_class=DEVICE_CLASS_BATTERY,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    )

    @property
    def native_value(self):
        return self._feeder.battery_level_int

class SmartFeedLastFeedingSensor(SmartFeedSensor):

    entity_description = SensorEntityDescription(
        key="last_feeding",
        name="Last Feeding",
        state_class=STATE_CLASS_MEASUREMENT,
    )

    def __init__(self, feeder):
        super().__init__(feeder)

        self._last_feeding = None
        self._update_counter = None

    @property
    def icon(self):
        return 'mdi:message-text'

    @property
    def native_value(self):
        
        if self._last_feeding is None:
            return None

        last_feeding_utc = datetime.strptime(self._last_feeding['created_at'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=tz.tzutc())
        last_feeding_local = last_feeding_utc.astimezone(None)
        
        last_feeding_local_string = last_feeding_local.strftime('%x %H:%M')
        last_feeding_amount = self._last_feeding['payload']['amount']

        return f'Last fed: {last_feeding_local_string}, Amount: {last_feeding_amount / 8} cups'

    def update(self):
        if self._update_counter is None or self._update_counter == 20:
            self._update_counter = 0
            self._last_feeding = self._feeder.get_last_feeding()
        else:
            self._update_counter += 1