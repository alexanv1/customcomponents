from datetime import timedelta

from homeassistant.components.select import (
    SelectEntity,
)

from . import DOMAIN, CONTROL_MODE_INTELLIGENCE, CONTROL_MODE_TEMPERATURE, AquantaWaterHeater

SCAN_INTERVAL = timedelta(seconds=30)

async def async_setup_entry(hass, config_entry, async_add_entities):
    for device in hass.data[DOMAIN]:
        async_add_entities([AquantaWaterHeaterControlModeSelect(device), AquantaWaterHeaterPerformanceModeSelect(device)])

class AquantaWaterHeaterControlModeSelect(SelectEntity):

    def __init__(self, device: AquantaWaterHeater):
        self._device = device

    @property
    def should_poll(self):
        return True

    @property
    def device_info(self):
        return self._device.device_info

    @property
    def name(self):
        return f"{self._device.name} Control Mode"

    @property
    def unique_id(self):
        return f"{self._device.unique_id}_control_mode"

    @property
    def options(self):
        return [CONTROL_MODE_INTELLIGENCE, CONTROL_MODE_TEMPERATURE]

    @property
    def current_option(self):
        return CONTROL_MODE_INTELLIGENCE if self._device.aquanta_intelligence_active else CONTROL_MODE_TEMPERATURE

    def select_option(self, option: str):
        self._device.set_aquanta_intelligence_active(option == CONTROL_MODE_INTELLIGENCE)

class AquantaWaterHeaterPerformanceModeSelect(SelectEntity):

    def __init__(self, device: AquantaWaterHeater):
        self._device = device

    @property
    def should_poll(self):
        return True

    @property
    def device_info(self):
        return self._device.device_info

    @property
    def name(self):
        return f"{self._device.name} Performance Mode"

    @property
    def unique_id(self):
        return f"{self._device.unique_id}_performance_mode"

    @property
    def options(self):
        if self._device.aquanta_intelligence_active:
            return ["Less Efficient", "Efficient", "Most Efficient"]
        else:
            return []

    @property
    def current_option(self):
        return self._device.performance_mode if self._device.aquanta_intelligence_active else None

    def select_option(self, option: str):
        self._device.set_performance_mode(option)