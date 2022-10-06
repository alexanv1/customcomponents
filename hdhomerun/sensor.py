"""
Simple sensor platform for HDHomeRun devices
"""

import requests
from datetime import timedelta

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.util import slugify

from . import DOMAIN, CONF_HOSTNAME

SCAN_INTERVAL = timedelta(seconds=30)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up of the HDHomeRun device."""

    global HEADERS
    global API_TOKEN

    hostname = config_entry.data[CONF_HOSTNAME]
    device = HDHomeRunDevice(hostname)

    # Get device info
    await hass.async_add_executor_job(device.update)

    sensors = [HDHomeRunInfoSensor(device)]
    for tuner_index in range(device.number_of_tuners):
        sensors += [HDHomeRunTunerSensor(device, tuner_index)]

    async_add_entities(sensors)       

class HDHomeRunDevice:

    def __init__(self, hostname : str):
        self._hostname = hostname
        self._device_data = {}
        self._tuner_status = []

    @property
    def device_uri(self):
        return f"http://{self._hostname}/discover.json"

    @property
    def status_uri(self):
        return f"http://{self._hostname}/status.json"

    @property
    def device_data(self):
        return self._device_data

    @property
    def number_of_tuners(self):
        return self._device_data["TunerCount"]

    @property
    def hostname(self):
        return self._hostname

    def send_request(self, uri : str) -> str:
        resp = requests.get(uri)
        if resp.status_code != 200:
            # Something went wrong
            raise Exception('GET {} failed with status {}, error: {}'.format(uri, resp.status_code, resp.json()["error"]))

        return resp.json()

    def update(self):
        self._device_data = self.send_request(self.device_uri)
        self._tuner_status = self.send_request(self.status_uri)

    def get_tuner_status(self, tuner_index : int):
        # Parse the tuner data for the given index
        return [x for x in self._tuner_status if x["Resource"] == f"tuner{tuner_index}"][0]

class HDHomeRunSensor(SensorEntity):

    def __init__(self, device : HDHomeRunDevice):
        self._device = device

    @property
    def device_info(self):
        return {
            "name": self._device.device_data['FriendlyName'],
            "identifiers": {(DOMAIN, slugify(self._device.hostname))},
            "model": self._device.device_data['ModelNumber'],
            "manufacturer": "Silicon Dust",
        }

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
            "ConditionalAccess": self._device.device_data["ConditionalAccess"],
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

    def update(self):
        self._device.update()

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