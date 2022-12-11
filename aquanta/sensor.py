from datetime import timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)

from homeassistant.const import PERCENTAGE, PRECISION_WHOLE, UnitOfTemperature

from . import DOMAIN, AquantaWaterHeater

SCAN_INTERVAL = timedelta(seconds=30)

async def async_setup_entry(hass, config_entry, async_add_entities):
    
    for device in hass.data[DOMAIN]:
        entities = [
                AquantaWaterHeaterTemperatureSensor(device),
                AquantaWaterHeaderAvailablePercentageSensor(device)
            ]

        async_add_entities(entities)

class AquantaWaterHeaterSensor(SensorEntity):

    def __init__(self, device: AquantaWaterHeater):
        self._device = device
        
    @property
    def device_info(self):
        return self._device.device_info

    @property
    def should_poll(self):
        return True

class AquantaWaterHeaterTemperatureSensor(AquantaWaterHeaterSensor):

    entity_description = SensorEntityDescription(
        key = "current_temperature",
        device_class = SensorDeviceClass.TEMPERATURE,
        state_class = SensorStateClass.MEASUREMENT,
        native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT,
    )

    def __init__(self, device):
        super().__init__(device)

    @property
    def name(self):
        return f"{self._device.name} Current Temperature"

    @property
    def unique_id(self):
        return f"{self._device.unique_id}_current_temperature"

    @property
    def precision(self):
        return PRECISION_WHOLE

    @property
    def native_value(self):
        return self._device.current_temperature

class AquantaWaterHeaderAvailablePercentageSensor(AquantaWaterHeaterSensor):

    entity_description = SensorEntityDescription(
        key = "hot_water_available",
        state_class = SensorStateClass.MEASUREMENT,
        native_unit_of_measurement = PERCENTAGE,
    )

    def __init__(self, device):
        super().__init__(device)

    @property
    def name(self):
        return f"{self._device.name} Hot Water Available"

    @property
    def unique_id(self):
        return f"{self._device.unique_id}_hot_water_available"

    @property
    def native_value(self):
        return self._device.hot_water_available

    @property
    def icon(self):
        return "mdi:percent"