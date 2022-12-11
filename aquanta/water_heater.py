from datetime import timedelta

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import (
    PRECISION_WHOLE,
    UnitOfTemperature,
    ATTR_TEMPERATURE,
)

from . import DOMAIN, OPERATION_MODE_NORMAL, OPERATION_MODE_BOOST, AquantaWaterHeater

SCAN_INTERVAL = timedelta(seconds=30)

ATTR_HOT_WATER_AVAILABLE_PERCENT = "hot_water_available"
ATTR_PERFORMANCE_MODE = "performance_mode"
ATTR_AQUANTA_INTELLIGENCE_ACIVE = "aquanta_intelligence_active"

async def async_setup_entry(hass, config_entry, async_add_entities):
    for device in hass.data[DOMAIN]:
        async_add_entities([AquantaWaterHeaterEntity(device)])


class AquantaWaterHeaterEntity(WaterHeaterEntity):

    def __init__(self, device: AquantaWaterHeater):
        self._device = device

    @property
    def device_info(self):
        return self._device.device_info

    @property
    def temperature_unit(self):
        return UnitOfTemperature.FAHRENHEIT

    @property
    def precision(self):
        return PRECISION_WHOLE

    @property
    def extra_state_attributes(self):
        return {
            ATTR_HOT_WATER_AVAILABLE_PERCENT: self._device.hot_water_available,
            ATTR_PERFORMANCE_MODE: self._device.performance_mode,
            ATTR_AQUANTA_INTELLIGENCE_ACIVE: self._device.aquanta_intelligence_active,
        }

    @property
    def current_operation(self):
        if self._device.state["boostRunning"]:
            return OPERATION_MODE_BOOST

        return OPERATION_MODE_NORMAL

    @property
    def operation_list(self):
        return [OPERATION_MODE_NORMAL, OPERATION_MODE_BOOST]

    @property
    def supported_features(self):
        features =  WaterHeaterEntityFeature.AWAY_MODE | WaterHeaterEntityFeature.OPERATION_MODE
        if (not self._device.aquanta_intelligence_active):
            features |= WaterHeaterEntityFeature.TARGET_TEMPERATURE

        return features

    @property
    def state(self):
        if (self.is_away_mode_on):
            return "Away"

        return self.current_operation

    @property
    def current_temperature(self):
        return self._device.current_temperature

    @property
    def target_temperature(self):
        if self._device.aquanta_intelligence_active:
            return None
            
        return self._device.target_temperature

    @property
    def min_temp(self):
        return 90

    @property
    def max_temp(self):
        return 140

    @property
    def is_away_mode_on(self):
        return self._device.is_away_mode_on

    @property
    def name(self):
        return self._device.name

    @property
    def unique_id(self):
        return self._device.unique_id

    @property
    def icon(self):
        return 'mdi:water-pump'

    def set_temperature(self, **kwargs):
        temperature = kwargs.get(ATTR_TEMPERATURE)
        self._device.set_target_temperature(temperature)

    def set_operation_mode(self, operation_mode):
        self._device.set_operation_mode(operation_mode)

    def turn_away_mode_on(self):
        self._device.set_away_mode(True)

    def turn_away_mode_off(self):
        self._device.set_away_mode(False)

    def update(self):
        self._device.update()