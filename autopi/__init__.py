"""
Support for AutoPi
"""
import logging
import aiohttp
import asyncio

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
API_DEVICES_URL = f"{API_BASE_URL}/dongle/devices/"
API_POSITION_URL = f"{API_BASE_URL}/logbook/v2/most_recent_position/?device_id="
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
    devices = await get_devices(username, password)

    autoPIDevices = []
    tasks = []
    for device in devices:
        autoPIDevice = AutoPiDevice(username, password, device)
        tasks.append(asyncio.ensure_future(autoPIDevice.update()))
        autoPIDevices += [autoPIDevice]

    await asyncio.gather(*tasks)

    hass.data[DOMAIN] = autoPIDevices
    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True

async def get_devices(username, password):
    """LOgin to AutoPi and get devices"""
    global _HEADERS

    _LOGGER.info(f'Logging in to AutoPi.')
    login_data = {"email": username, "password": password}

    async with aiohttp.ClientSession() as session:
        async with session.post(API_LOGIN_URL, data = login_data) as login_response:

            if login_response.status != 200:
                _LOGGER.error(f'Login Failed, status = {login_response.status}, response = "{await login_response.text()}"')
                login_response.raise_for_status()
            else:
                login_response_json = await login_response.json()
                _LOGGER.info(f'Received login response json = {login_response_json}')

                _HEADERS = {'Authorization': f'Bearer {login_response_json["token"]}' }

        async with session.get(API_DEVICES_URL, headers = _HEADERS) as devices_response:

            if devices_response.status != 200:
                _LOGGER.error(f'Getting Devices Failed, status = {devices_response.status}, response = "{await devices_response.text()}"')
                devices_response.raise_for_status()
            else:
                devices_response_json = await devices_response.json()
                _LOGGER.info(f'Received get devices response json = {devices_response_json}')
                return devices_response_json["results"]

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

    async def update(self):
        """Update the device info."""
        
        _LOGGER.debug(f"Updating AutoPi device: {self._vehicle_name}")
        tasks = []
        async with aiohttp.ClientSession() as session:
            tasks.append(asyncio.ensure_future(self._get_position(session, True)))
    
            skip_attribute_update = False

            if self._skip_attribute_update_counter == SKIP_ATTRIBUTE_UPDATE_MAX:
                self._skip_attribute_update_counter = 0
                self._get_vehicle_attributes(session, tasks)
            else:
                self._skip_attribute_update_counter += 1
                skip_attribute_update = True

            await asyncio.gather(*tasks)

            if skip_attribute_update == True:
                _LOGGER.info(f"{self._vehicle_name} - location: {self._location}, skipping attribute update, skip_attribute_update_counter={self._skip_attribute_update_counter}")
            else:
                _LOGGER.info(f"{self._vehicle_name} - location: {self._location}, attributes {self._attributes}")
                

    async def _get_position(self, session: aiohttp.ClientSession(), retry: bool):
        """Update the latest position for the device."""

        url = f'{API_POSITION_URL}{self._device_id}'

        async with session.get(url, headers = _HEADERS) as position_response:

            if position_response.status == 200:
                position_response_json = await position_response.json()
                _LOGGER.debug(f'Received {url} response, json = {position_response_json}')
                self._location = position_response_json["location"]

            elif retry == True:
                _LOGGER.info(f'{self._vehicle_name} - getting position failed, will retry. Status = {position_response.status}, response = {await position_response.text()}')

                await get_devices(self._username, self._password)
                await self._get_position(session, False)

            else:
                _LOGGER.error(f'{self._vehicle_name} - getting position failed. Status = {position_response.status}, response = {await position_response.text()}')
                position_response.raise_for_status()

    def _get_vehicle_attributes(self, session: aiohttp.ClientSession, tasks: list):
        """Update vehicle attributes."""

        attribute_types =  {
            'obd.fuel_level.value': 'float',
            'obd.speed.value': 'float',
            'obd.rpm.value': 'float',
            'obd.coolant_temp.value': 'long',
            'obd.bat.voltage': 'float',
            'obd.bat.level': 'long'}

        for attribute, attribute_type in attribute_types.items():
            tasks.append(asyncio.ensure_future(self._get_vehicle_attribute(session, attribute, attribute_type)))

    async def _get_vehicle_attribute(self, session: aiohttp.ClientSession, attribute: str, attribute_type: str):
        """Update a single attribute."""

        from_utc = "2020-01-01T00:00:00Z"
        url = f'{API_STORAGE_READ_URL}{self._device_id}&field={attribute}&field_type={attribute_type}&aggregation=none&from_utc={from_utc}&size=1'

        hass_attribute_names = {
            'obd.fuel_level.value': ATTR_FUEL_LEVEL,
            'obd.speed.value': ATTR_SPEED,
            'obd.rpm.value': ATTR_RPM,
            'obd.coolant_temp.value': ATTR_COOLANT_TEMPERATURE,
            'obd.bat.voltage': ATTR_BATTERY_VOLTAGE,
            'obd.bat.level': ATTR_BATTERY_LEVEL}

        async with session.get(url, headers = _HEADERS) as response:

            if response.status == 200:
                response_json = await response.json()
                _LOGGER.debug(f'{self._vehicle_name} - received {url} response, json = {response_json}')

                hass_attribute_name = hass_attribute_names[attribute]
                attribute_value = response_json[0]["value"]

                if hass_attribute_name == ATTR_SPEED:
                    # Convert to MPH
                    self._attributes[ATTR_SPEED] = attribute_value / 1.61
                elif hass_attribute_name == ATTR_FUEL_LEVEL:
                    # Keep previous fuel level value if newly reported value is 0 (which is what the API sometimes returns when the engine is off)
                    if int(attribute_value) != 0 or ATTR_FUEL_LEVEL not in self._attributes.keys():
                        self._attributes[ATTR_FUEL_LEVEL] = attribute_value
                else:
                    self._attributes[hass_attribute_name] = attribute_value
            else:
                _LOGGER.error(f'{self._vehicle_name} - getting attributes failed. Response status = {response.status}, response = {await response.text()}')