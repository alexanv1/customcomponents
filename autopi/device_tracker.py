"""
Support for PhoneTrackOC device tracking.
"""
import logging
from datetime import timedelta
import requests
import voluptuous as vol

from homeassistant.components.device_tracker import PLATFORM_SCHEMA, SOURCE_TYPE_GPS
from homeassistant.util import slugify
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.event import track_time_interval
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
    }
)

SCAN_INTERVAL = timedelta(seconds=15)

_HEADERS = {}

API_BASE_URL = "https://api.autopi.io"
API_LOGIN_URL = f"{API_BASE_URL}/auth/login/"
API_POSITION_URL = f"{API_BASE_URL}/logbook/most_recent_positions/"
API_STORAGE_READ_URL = f"{API_BASE_URL}/logbook/storage/read/?device_id="

ATTR_FUEL_LEVEL = "fuel_level"
ATTR_SPEED = "speed"
ATTR_RPM = "rpm"
ATTR_COOLANT_TEMPERATURE = "coolant_temperature"

# Login to AutoPi
def login(config):
    """LOgin to AutoPi"""
    global _HEADERS

    devices = {}

    _LOGGER.info(f'Logging in to AutoPi.')

    login_data = {"email": config[CONF_USERNAME], "password": config[CONF_PASSWORD]}
    login_response = requests.post(API_LOGIN_URL, data = login_data)
    login_response_json = login_response.json()

    _LOGGER.info(f'Received login response, status = {login_response.status_code}, json = {login_response_json}')

    if login_response.status_code != 200:
        _LOGGER.error(f'Login Failed, status = {login_response.status_code}')
    else:
        _HEADERS = {'Authorization': f'Bearer {login_response_json["token"]}' }
        devices = login_response_json["user"]["devices"]

    return devices

def setup_scanner(hass, config, see, discovery_info=None):
    """Setup AutoPi scanner."""

    devices = login(config)

    AutoPiDeviceTracker(hass, config, see, devices)

    return True

class AutoPiDeviceTracker(object):
    """
    AutoPi Device Tracker
    """
    def __init__(self, hass, config, see, devices):
        """Initialize the AutoPi tracking."""
        self._see = see
        self._devices = devices
        self._config = config

        track_time_interval(hass, self._update, SCAN_INTERVAL)

        self._update()

    def _update(self, now=None):
        """Update the device info."""
        
        _LOGGER.debug("Updating AutoPi devices")

        position_response_json = self._get_positions()

        for device in self._devices:
            unit_id = device["unit_id"]

            for record in position_response_json:
                if record["unit_id"] == unit_id:
                    _LOGGER.debug(f'Found position data for device with unit_id = {unit_id}')
                    self._get_vehicle_data(device, record["positions"])
                    break

        return True

    def _get_positions(self):
        """Update the latest position for all devices."""

        position_response = requests.get(API_POSITION_URL, headers = _HEADERS)
        position_response_json = position_response.json()
        _LOGGER.debug(f'Received {API_POSITION_URL} response, status = {position_response.status_code}, json = {position_response_json}')

        if position_response.status_code != 200:
            login(self._config)

            # Get device positions again
            position_response = requests.get(API_POSITION_URL, headers = _HEADERS)
            position_response_json = position_response.json()
            _LOGGER.debug(f'Received {API_POSITION_URL} response, status = {position_response.status_code}, json = {position_response_json}')

        return position_response_json


    def _get_vehicle_data(self, device: dict, positions: dict):
        """Update vehicle data."""

        device_id = device["id"]
        vehicle_name = f'{device["vehicle"]["year"]} {device["vehicle"]["display"]}'

        location = positions[0]["location"]

        attributes = self._get_vehicle_attributes(device_id, vehicle_name)
        _LOGGER.info(f"{vehicle_name} -  location: {location}, attributes {attributes}")

        self._see(
            dev_id = slugify(vehicle_name),
            source_type = SOURCE_TYPE_GPS,
            gps = (location["lat"], location["lon"]),
            attributes = attributes,
        )

    def _get_vehicle_attributes(self, device_id, vehicle_name):
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
            url = f'{API_STORAGE_READ_URL}{device_id}&field={attribute}&field_type={attribute_type}&aggregation=none&from_utc={from_utc}&size=1'

            response = requests.get(url, headers = _HEADERS)
            response_json = response.json()

            _LOGGER.debug(f'{vehicle_name} - received {url} response, status = {response.status_code}, json = {response_json}')
            if response.status_code == 200:
                attributes[hass_attribute_names[attribute]] = response_json[0]["value"]
            else:
                _LOGGER.info(f'{vehicle_name} - response status = {response.status_code}, settting {hass_attribute_names[attribute]} to 0')
                attributes[hass_attribute_names[attribute]] = 0

        return attributes
