"""
Support for AutoPi
"""
import logging
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

DOMAIN = 'autopi'

PLATFORMS = ["device_tracker", "sensor"]

_LOGGER = logging.getLogger(__name__)

_HEADERS = {}

SKIP_ATTRIBUTE_UPDATE_MAX = 5

API_BASE_URL = "https://api.autopi.io"
API_LOGIN_URL = f"{API_BASE_URL}/auth/login/"
API_POSITION_URL = f"{API_BASE_URL}/logbook/most_recent_position/?device_id="
API_STORAGE_READ_URL = f"{API_BASE_URL}/logbook/storage/read/?device_id="

ATTR_FUEL_LEVEL = "fuel_level"
ATTR_SPEED = "speed"
ATTR_RPM = "rpm"
ATTR_COOLANT_TEMPERATURE = "coolant_temperature"
ATTR_BATTERY_LEVEL = "battery_level"
ATTR_BATTERY_VOLTAGE = "battery_voltage"

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up AutoPi from a config entry."""

    # Get AutoPi devices
    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]
    devices = await hass.async_add_executor_job(get_devices, username, password)

    autoPIDevices = []
    for device in devices:
        autoPIDevice = AutoPiDevice(username, password, device)
        await hass.async_add_executor_job(autoPIDevice.update)
        autoPIDevices += [autoPIDevice]

    hass.data[DOMAIN] = autoPIDevices
    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True

def get_devices(username, password):
    """LOgin to AutoPi and get devices"""
    global _HEADERS

    devices = {}

    _LOGGER.info(f'Logging in to AutoPi.')

    login_data = {"email": username, "password": password}
    login_response = requests.post(API_LOGIN_URL, data = login_data)

    if login_response.status_code != 200:
        _LOGGER.error(f'Login Failed, status = {login_response.status_code}, response = "{login_response.text}"')
        login_response.raise_for_status()
    else:
        login_response_json = login_response.json()
        _LOGGER.info(f'Received login response json = {login_response_json}')

        _HEADERS = {'Authorization': f'Bearer {login_response_json["token"]}' }
        devices = login_response_json["user"]["devices"]

    return devices

class AutoPiDevice():
    """ AutoPi Device Tracker """

    def __init__(self, username : str, password : str, device):
        self._username = username
        self._password = password

        self._unit_id = device["unit_id"]
        self._device_id = device["id"]
        self._vehicle_name = f'{device["vehicle"]["year"]} {device["vehicle"]["display"]}'

        self._location = []
        self._attributes = {}

        # Reduce the frequency of attribute updates to avoid slowing down position update and reduce the number of calls to AutoPI cloud API
        self._skip_attribute_update_counter = SKIP_ATTRIBUTE_UPDATE_MAX

    @property
    def name(self):
        return self._vehicle_name

    @property
    def unique_id(self):
        return slugify(self._vehicle_name)

    @property
    def latitude(self):
        return self._location["lat"]

    @property
    def longitude(self):
        return self._location["lon"]

    @property
    def attributes(self):
        return self._attributes

    @property
    def speed(self):
        return self._attributes[ATTR_SPEED]

    @property
    def rpm(self):
        return self._attributes[ATTR_RPM]

    @property
    def fuel_level(self):
        return self._attributes[ATTR_FUEL_LEVEL]

    @property
    def coolant_temperature(self):
        return self._attributes[ATTR_COOLANT_TEMPERATURE]

    @property
    def battery_level(self):
        return self._attributes[ATTR_BATTERY_LEVEL]

    @property
    def battery_voltage(self):
        return self._attributes[ATTR_BATTERY_VOLTAGE]

    @property
    def device_info(self):
        info = {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self._vehicle_name,
            "manufacturer": "AutoPi",
            "model": f"AutoPi Dongle",
        }
        _LOGGER.debug(f"Returning device info: {info}")
        return info

    def update(self):
        """Update the device info."""
        
        _LOGGER.debug(f"Updating AutoPi device: {self._vehicle_name}")
        self._get_vehicle_data()
                

    def _get_position(self):
        """Update the latest position for the device."""

        url = f'{API_POSITION_URL}{self._device_id}'

        position_response = requests.get(url, headers = _HEADERS)

        if position_response.status_code == 200:
            position_response_json = position_response.json()
            _LOGGER.debug(f'Received {url} response, json = {position_response_json}')
        else:
            _LOGGER.info(f'{self._vehicle_name} - getting position failed, will retry. Status = {position_response.status_code}, response = {position_response.text}')

            get_devices(self._username, self._password)

            # Get device positions again
            position_response = requests.get(url, headers = _HEADERS)
            if position_response.status_code == 200:
                position_response_json = position_response.json()
                _LOGGER.debug(f'Received {url} response, json = {position_response_json}')
            else:
                _LOGGER.error(f'{self._vehicle_name} - getting position failed. Status = {position_response.status_code}, response = {position_response.text}')
                position_response.raise_for_status()

        return position_response_json

    def _get_vehicle_data(self):
        """Update vehicle data."""

        position = self._get_position()
        _LOGGER.debug(f'Found position data for device with unit_id = {self._unit_id}')
        self._location = position["location"]

        if self._skip_attribute_update_counter == SKIP_ATTRIBUTE_UPDATE_MAX:
            self._skip_attribute_update_counter = 0
            self._get_vehicle_attributes()
            _LOGGER.info(f"{self._vehicle_name} - location: {self._location}, attributes {self._attributes}")
        else:
            self._skip_attribute_update_counter += 1
            _LOGGER.info(f"{self._vehicle_name} - location: {self._location}, skipping attribute update, skip_attribute_update_counter={self._skip_attribute_update_counter}")

    def _get_vehicle_attributes(self):
        """Update vehicle attributes."""

        attribute_types =  {
            'obd.fuel_level.value': 'float',
            'obd.speed.value': 'float',
            'obd.rpm.value': 'float',
            'obd.coolant_temp.value': 'long',
            'obd.bat.voltage': 'float',
            'obd.bat.level': 'long'}
        hass_attribute_names = {
            'obd.fuel_level.value': ATTR_FUEL_LEVEL,
            'obd.speed.value': ATTR_SPEED,
            'obd.rpm.value': ATTR_RPM,
            'obd.coolant_temp.value': ATTR_COOLANT_TEMPERATURE,
            'obd.bat.voltage': ATTR_BATTERY_VOLTAGE,
            'obd.bat.level': ATTR_BATTERY_LEVEL}

        from_utc = "2020-01-01T00:00:00Z"

        for attribute, attribute_type in attribute_types.items():
            url = f'{API_STORAGE_READ_URL}{self._device_id}&field={attribute}&field_type={attribute_type}&aggregation=none&from_utc={from_utc}&size=1'

            response = requests.get(url, headers = _HEADERS)

            if response.status_code == 200:
                response_json = response.json()
                _LOGGER.debug(f'{self._vehicle_name} - received {url} response, json = {response_json}')

                hass_attribute_name = hass_attribute_names[attribute]
                if hass_attribute_name == ATTR_SPEED:
                    # Convert to MPH
                    self._attributes[hass_attribute_name] = response_json[0]["value"] / 1.61
                else:
                    self._attributes[hass_attribute_name] = response_json[0]["value"]
            else:
                _LOGGER.error(f'{self._vehicle_name} - getting attributes failed. Response status = {response.status_code}, response = {response.text}')