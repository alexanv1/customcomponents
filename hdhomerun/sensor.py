"""
Simple sensor platform for HDHomeRun devices
"""

from datetime import timedelta

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.util import slugify

from . import DOMAIN, HDHomeRunDevice

SCAN_INTERVAL = timedelta(seconds=30)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up of the HDHomeRun device."""

    device = hass.data[DOMAIN]

    sensors = [HDHomeRunInfoSensor(device)]
    for tuner_index in range(device.number_of_tuners):
        sensors += [HDHomeRunTunerSensor(device, tuner_index)]

    async_add_entities(sensors)


class HDHomeRunSensor(SensorEntity):

    def __init__(self, device : HDHomeRunDevice):
        self._device = device

    @property
    def device_info(self):
        return self._device.device_info

    @property
    def name(self):
        return f'HDHomeRun Prime {self.entity_description.name}'

    @property
    def unique_id(self):
        return f'{slugify(self.name)}_{self.entity_description.key}'

    @property
    def should_poll(self):
        return True

class HDHomeRunInfoSensor(HDHomeRunSensor):

    entity_description = SensorEntityDescription(
        key="info",
        name="Info",
    )

    def update(self):
        self._device.update()

    @property
    def native_value(self) -> str:
        return ''

    @property
    def extra_state_attributes(self):

        upgrade_available = None
        if "UpgradeAvailable" in self._device.device_data:
            upgrade_available = self._device.device_data["UpgradeAvailable"]

        return {
            "FirmwareName": self._device.device_data["FirmwareName"],
            "FirmwareVersion": self._device.device_data["FirmwareVersion"],
            "DeviceID": self._device.device_data["DeviceID"],
            "DeviceAuth": self._device.device_data["DeviceAuth"],
            "UpgradeAvailable": upgrade_available,
            "BaseURL": self._device.device_data["BaseURL"],
            "LineupURL": self._device.device_data["LineupURL"],
            "ConditionalAccess": self._device.device_data["ConditionalAccess"] if ("ConditionalAccess" in self._device.device_data) else "",
        }
    
    @property
    def icon(self):
        return "mdi:television"

class HDHomeRunTunerSensor(HDHomeRunSensor):

    def __init__(self, device : HDHomeRunDevice, tuner_index : int):
        super().__init__(device)

        self._tuner_index = tuner_index
        self.entity_description = SensorEntityDescription(
            key=f"tuner_{self._tuner_index + 1}_status",
            name=f"Tuner {self._tuner_index + 1} Status",
        )

    @property
    def native_value(self) -> str:
        tuner_status = self._device.get_tuner_status(self._tuner_index)
        if "VctNumber" in tuner_status:
            return f"Channel {tuner_status['VctNumber']}: {tuner_status['VctName']}"
        else:
            return 'Off'

    @property
    def extra_state_attributes(self):

        tuner_status = self._device.get_tuner_status(self._tuner_index)
        if "VctNumber" in tuner_status:
            return {
                "VctNumber": tuner_status["VctNumber"],
                "VctName": tuner_status["VctName"],
                "Frequency": tuner_status["Frequency"],
                "SignalStrengthPercent": tuner_status["SignalStrengthPercent"],
                "SymbolQualityPercent": tuner_status["SymbolQualityPercent"],
                "TargetIP": tuner_status["TargetIP"],
            }
        else:
            return None

    @property
    def icon(self):
        return "mdi:tune"