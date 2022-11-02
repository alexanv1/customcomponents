import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

CONF_HOSTNAME = 'hostname'

DOMAIN = 'hdhomerun'

PLATFORMS = ["sensor", "update"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HDHomeRun from a config entry."""

    hostname = entry.data[CONF_HOSTNAME]
    device = HDHomeRunDevice(hostname)

    # Get device info
    await hass.async_add_executor_job(device.update)
    hass.data[DOMAIN] = device

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


class HDHomeRunDevice:

    def __init__(self, hostname : str):
        self._hostname = hostname
        self._device_data = {}
        self._tuner_status = []

    @property
    def device_info(self):
        return {
            "configuration_url": f"http://{self.hostname}/",
            "name": self.device_data['FriendlyName'],
            "identifiers": {(DOMAIN, slugify(self.hostname))},
            "model": self.device_data['ModelNumber'],
            "manufacturer": "Silicon Dust",
        }

    @property
    def device_uri(self):
        return f"http://{self._hostname}/discover.json"

    @property
    def status_uri(self):
        return f"http://{self._hostname}/status.json"

    @property
    def firmware_upgrade_uri(self):
        return f"http://{self._hostname}/system.post?upgrade=install"

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

    def upgrade_firmware(self):
        resp = requests.post(self.firmware_upgrade_uri)
        if resp.status_code != 200:
            # Something went wrong
            raise Exception('POST {} failed with status {}, error: {}'.format(self.firmware_upgrade_uri, resp.status_code, resp.json()["error"]))

    def get_tuner_status(self, tuner_index : int):
        # Parse the tuner data for the given index
        return [x for x in self._tuner_status if x["Resource"] == f"tuner{tuner_index}"][0]