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

API_BASE_URL = "https://api.autopi.io"
API_LOGIN_URL = f"{API_BASE_URL}/auth/login/"
API_POSITION_URL = f"{API_BASE_URL}/logbook/most_recent_positions/"
API_STORAGE_READ_URL = f"{API_BASE_URL}/logbook/storage/read/?device_id="

ATTR_FUEL_LEVEL = "fuel_level"
ATTR_SPEED = "speed"
ATTR_RPM = "rpm"
ATTR_COOLANT_TEMPERATURE = "coolant_temperature"

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
    login_response_json = login_response.json()

    _LOGGER.info(f'Received login response, status = {login_response.status_code}, json = {login_response_json}')

    if login_response.status_code != 200:
        _LOGGER.error(f'Login Failed, status = {login_response.status_code}')
    else:
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
        self._attributes = []

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

        position_response_json = self._get_positions()

        for record in position_response_json:
            if record["unit_id"] == self._unit_id:
                _LOGGER.debug(f'Found position data for device with unit_id = {self._unit_id}')
                self._get_vehicle_data(record["positions"])
                break

    def _get_positions(self):
        """Update the latest position for all devices."""

        position_response = requests.get(API_POSITION_URL, headers = _HEADERS)
        position_response_json = position_response.json()
        _LOGGER.debug(f'Received {API_POSITION_URL} response, status = {position_response.status_code}, json = {position_response_json}')

        if position_response.status_code != 200:
            get_devices(self._username, self._password)

            # Get device positions again
            position_response = requests.get(API_POSITION_URL, headers = _HEADERS)
            position_response_json = position_response.json()
            _LOGGER.debug(f'Received {API_POSITION_URL} response, status = {position_response.status_code}, json = {position_response_json}')

        return position_response_json


    def _get_vehicle_data(self, positions: dict):
        """Update vehicle data."""

        self._location = positions[0]["location"]
        self._attributes = self._get_vehicle_attributes()
        _LOGGER.info(f"{self._vehicle_name} -  location: {self._location}, attributes {self._attributes}")

    def _get_vehicle_attributes(self):
        """Update vehicle attributes."""
        attributes = {}

        attribute_types =  {
            'obd.fuel_level.value': 'float',
            'obd.speed.value': 'float',
            'obd.rpm.value': 'float',
            'obd.coolant_temp.value': 'long'}
        hass_attribute_names = {
            'obd.fuel_level.value': ATTR_FUEL_LEVEL,
            'obd.speed.value': ATTR_SPEED,
            'obd.rpm.value': ATTR_RPM,
            'obd.coolant_temp.value': ATTR_COOLANT_TEMPERATURE}

        from_utc = "2020-01-01T00:00:00Z"

        for attribute, attribute_type in attribute_types.items():
            url = f'{API_STORAGE_READ_URL}{self._device_id}&field={attribute}&field_type={attribute_type}&aggregation=none&from_utc={from_utc}&size=1'

            response = requests.get(url, headers = _HEADERS)
            response_json = response.json()

            _LOGGER.debug(f'{self._vehicle_name} - received {url} response, status = {response.status_code}, json = {response_json}')
            if response.status_code == 200:
                attributes[hass_attribute_names[attribute]] = response_json[0]["value"]
            else:
                _LOGGER.info(f'{self._vehicle_name} - response status = {response.status_code}, settting {hass_attribute_names[attribute]} to 0')
                attributes[hass_attribute_names[attribute]] = 0

        return attributes