from datetime import timedelta

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    DEVICE_CLASS_TEMPERATURE,
    SensorEntity,
    SensorEntityDescription,
)

from homeassistant.const import (
    PERCENTAGE,
    SPEED_MILES_PER_HOUR,
    PRECISION_WHOLE,
    TEMP_CELSIUS,
)

from . import DOMAIN, AutoPiDevice

SCAN_INTERVAL = timedelta(seconds=15)

async def async_setup_entry(hass, config_entry, async_add_entities):
    
    for autoPIDevice in hass.data[DOMAIN]:
        entities = [
                AutoPISpeedSensor(autoPIDevice),
                AutoPIRPMSensor(autoPIDevice),
                AutoPIFuelSensor(autoPIDevice),
                AutoPICoolantTemperatureSensor(autoPIDevice)
            ]

        async_add_entities(entities)

class AutoPISensor(SensorEntity):

    def __init__(self, device: AutoPiDevice):
        self._device = device
        
    @property
    def device_info(self):
        return self._device.device_info

    @property
    def precision(self):
        return PRECISION_WHOLE

    @property
    def should_poll(self):
        return True

class AutoPISpeedSensor(AutoPISensor):

    entity_description = SensorEntityDescription(
        key = "speed",
        state_class = STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement = SPEED_MILES_PER_HOUR
    )

    def __init__(self, device):
        super().__init__(device)

    @property
    def name(self):
        return f"{self._device.name} Speed"

    @property
    def unique_id(self):
        return f"{self._device.unique_id}_speed_mph"

    @property
    def native_value(self):
        return int(self._device.speed)

    @property
    def icon(self):
        return 'mdi:speedometer'

class AutoPIRPMSensor(AutoPISensor):

    entity_description = SensorEntityDescription(
        key = "rpm",
        state_class = STATE_CLASS_MEASUREMENT
    )

    def __init__(self, device):
        super().__init__(device)

    @property
    def name(self):
        return f"{self._device.name} RPM"

    @property
    def unique_id(self):
        return f"{self._device.unique_id}_rpm"

    @property
    def native_value(self):
        return int(self._device.rpm)

    @property
    def icon(self):
        return 'mdi:gauge'

class AutoPIFuelSensor(AutoPISensor):

    entity_description = SensorEntityDescription(
        key = "fuel_level",
        state_class = STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement = PERCENTAGE
    )

    def __init__(self, device):
        super().__init__(device)

    @property
    def name(self):
        return f"{self._device.name} Fuel Level"

    @property
    def unique_id(self):
        return f"{self._device.unique_id}_fuel_level"

    @property
    def native_value(self):
        return int(self._device.fuel_level)

    @property
    def icon(self):
        return 'mdi:gas-station'

class AutoPICoolantTemperatureSensor(AutoPISensor):

    entity_description = SensorEntityDescription(
        key = "coolant_temperature",
        device_class = DEVICE_CLASS_TEMPERATURE,
        state_class = STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement = TEMP_CELSIUS,
    )

    def __init__(self, device):
        super().__init__(device)

    @property
    def name(self):
        return f"{self._device.name} Coolant Temperature"

    @property
    def unique_id(self):
        return f"{self._device.unique_id}_coolant_temperature"

    @property
    def native_value(self):
        return int(self._device.coolant_temperature)

    @property
    def icon(self):
        return 'mdi:thermometer'