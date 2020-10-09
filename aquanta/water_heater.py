"""
Simple platform to control Aquanta Water Heater
"""

import logging
import json
import voluptuous as vol
import requests
from datetime import datetime, timedelta, timezone

from homeassistant.helpers.temperature import display_temp

from homeassistant.components.water_heater import (
    PLATFORM_SCHEMA,
    SUPPORT_OPERATION_MODE,
    SUPPORT_AWAY_MODE,
    WaterHeaterEntity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    PRECISION_WHOLE,
    CONF_PASSWORD,
    CONF_USERNAME,
    TEMP_CELSIUS,
    STATE_OFF,
    STATE_ON,
)
import homeassistant.helpers.config_validation as cv

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)

SUPPORT_FLAGS_HEATER = SUPPORT_AWAY_MODE | SUPPORT_OPERATION_MODE

API_BASE_URL = "https://portal.aquanta.io/portal"
API_LOGIN_URL = f"{API_BASE_URL}/login"
API_GET_URL = f"{API_BASE_URL}/get"
API_SET_LOCATION_URL = f"{API_BASE_URL}/set/selected_location?locationId="
API_SETTINGS_URL = f"{API_BASE_URL}/get/settings"

API_AWAY_MODE_ON = f"{API_BASE_URL}/set/schedule/away"
API_AWAY_MODE_OFF = f"{API_BASE_URL}/set/schedule/away/off"

API_BOOST_MODE_ON = f"{API_BASE_URL}/set/schedule/boost"
API_BOOST_MODE_OFF = f"{API_BASE_URL}/set/schedule/boost/off"

OPERATION_MODE_NORMAL = 'Normal'
OPERATION_MODE_BOOST = 'Boost'

ATTR_AWAY_MODE = "away_mode"
ATTR_OPERATION_MODE = "operation_mode"
ATTR_OPERATION_LIST = "operation_list"
ATTR_CURRENT_TEMPERATURE = "current_temperature"
ATTR_AVAILABLE_PERCENT = "available_percentage"
ATTR_PERFORMANCE_MODE = "performance_mode"
ATTR_AQUANTA_INTELLIGENCE_ACIVE = "aquanta_intelligence_active"

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Aquanta water heaters."""

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    add_entities([AquantaWaterHeater(username, password)])


class AquantaWaterHeater(WaterHeaterEntity):
    """Representation of an Aquanta water heater."""

    def __init__(self, username, password):
        """Initialize the water heater."""
        self._username = username
        self._password = password

        self._login_time = None

        self._session = None
        self._location = None

        self._data = {}
        self._settings = {}

        self.login()

        self.update()

    def login(self):
        self._session = requests.Session()

        _LOGGER.info(f'Logging in to Aquanta.')

        login_data = dict(email=self._username, password=self._password, returnSecureToken=True)
        verifyPasswordResponse = self._session.post("https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key=AIzaSyBHWHB8Org9BWCH-YFzis-8oEbMaKmI2Tw", data=login_data)
        _LOGGER.info(f'Received VerifyPassword response, status = {verifyPasswordResponse.status_code}, json = {verifyPasswordResponse.json()}')

        idToken = dict(idToken = verifyPasswordResponse.json()["idToken"])
        loginResponse = self._session.post(f"{API_BASE_URL}/login", data=idToken)
        _LOGGER.info(f'Received login response, status = {loginResponse.status_code}, json = {loginResponse.json()}')

        if loginResponse.status_code != 200:
            _LOGGER.error(f'Login Failed, status = {loginResponse.status_code}')
        else:
            self._login_time = datetime.now()
            self.set_location()
    
    def check_login(self):
        if datetime.now() - self._login_time > timedelta(minutes = 30):
            # Login again after 30 minutes
            self.login()

    def check_response(self, response):
        if response.status_code != 200:
            _LOGGER.error(f'Operation failed, status = {loginResponse.status_code}')

    def set_location(self):
        response = self._session.get(API_GET_URL)
        locations = response.json()["locations"]
        self._location = next(iter(locations))
        response = self._session.put(f"{API_SET_LOCATION_URL}{self._location}")
        _LOGGER.info(f'Set location to {self._location}, status = {response.status_code}')

        self.check_response(response)

    def get_schedule_dictionary(self):
        start = datetime.now(timezone.utc).astimezone()
        end = start + timedelta(days = 30)
        timeFormat = "%Y-%m-%dT%T-07:00"
        return dict(start=start.strftime(timeFormat), stop=end.strftime(timeFormat), mode='now')

    @property
    def state(self):
        """Return the current state."""
        if (self.is_away_mode_on):
            return "Away"

        return self.current_operation

    @property
    def capability_attributes(self):
        """Return capability attributes."""
        return {
            ATTR_OPERATION_LIST: self.operation_list,
        }

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_WHOLE

    @property
    def state_attributes(self):
        """Return the optional state attributes."""
        data = {
            ATTR_CURRENT_TEMPERATURE: display_temp(self.hass, self.current_temperature, self.temperature_unit, self.precision),
            ATTR_OPERATION_MODE: self.current_operation,
            ATTR_AWAY_MODE: STATE_ON if self.is_away_mode_on else STATE_OFF,
            ATTR_AVAILABLE_PERCENT: round(self._data["hw_avail_fraction"] * 100),
            ATTR_PERFORMANCE_MODE: self._data["efficiencySelection"],
            ATTR_AQUANTA_INTELLIGENCE_ACIVE: not self._settings["aquantaIntel"],
        }

        return data

    @property
    def current_operation(self):
        """
        Return current operation mode.
        """
        if self._data["boostRunning"]:
            return OPERATION_MODE_BOOST

        return OPERATION_MODE_NORMAL

    @property
    def operation_list(self):
        """List of available operation modes."""
        return [OPERATION_MODE_NORMAL, OPERATION_MODE_BOOST]

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS_HEATER

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._data["tempValue"]

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return self._data["awayRunning"]

    @property
    def name(self):
        """Return the name of the water heater."""
        return f'{self._settings["userDescription"]} Water Heater'

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        self.check_login()

        if operation_mode == OPERATION_MODE_BOOST:
            if self.is_away_mode_on:
                # Turn off away mode first
                self.turn_away_mode_off()

            response = self._session.put(API_BOOST_MODE_ON, data=self.get_schedule_dictionary())
            _LOGGER.info(f'Boost mode turned on. Received {API_AWAY_MODE_ON} response, status = {response.status_code}')
        else:
            response = self._session.put(API_BOOST_MODE_OFF)
            _LOGGER.info(f'Boost mode turned off. Received {API_BOOST_MODE_OFF} response, status = {response.status_code}')

        self.check_response(response)

    async def async_set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        await self.hass.async_add_executor_job(self.set_operation_mode, operation_mode)

    def turn_away_mode_on(self):
        """Turn away mode on."""
        self.check_login()

        response = self._session.put(API_AWAY_MODE_ON, data=self.get_schedule_dictionary())
        _LOGGER.info(f'Away mode turned on. Received {API_AWAY_MODE_ON} response, status = {response.status_code}')
        self.check_response(response)

        # Also turn off Boost
        self.set_operation_mode(OPERATION_MODE_NORMAL)

    async def async_turn_away_mode_on(self):
        """Turn away mode on."""
        await self.hass.async_add_executor_job(self.turn_away_mode_on)

    def turn_away_mode_off(self):
        """Turn away mode off."""
        self.check_login()

        response = self._session.put(API_AWAY_MODE_OFF)
        _LOGGER.info(f'Away mode turned off. Received {API_AWAY_MODE_OFF} response, status = {response.status_code}')
        self.check_response(response)

    async def async_turn_away_mode_off(self):
        """Turn away mode off."""
        await self.hass.async_add_executor_job(self.turn_away_mode_off)

    def update(self):
        """Get the latest state."""
        self.check_login()
        
        response = self._session.get(API_GET_URL)
        _LOGGER.debug(f'Received {API_GET_URL} response, status = {response.status_code}, json = {response.json()}')
        self.check_response(response)
        self._data = response.json()

        response = self._session.get(API_SETTINGS_URL)
        _LOGGER.debug(f'Received {API_SETTINGS_URL} response, status = {response.status_code}, json = {response.json()}')
        self.check_response(response)
        self._settings = response.json()