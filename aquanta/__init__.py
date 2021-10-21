"""
Support for Aquanta Water Header
"""

import logging
import requests
from datetime import datetime, timedelta, timezone

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME
)

DOMAIN = 'aquanta'

PLATFORMS = ["water_heater", "sensor", "select"]

_LOGGER = logging.getLogger(__name__)

API_BASE_URL = "https://portal.aquanta.io/portal"
API_LOGIN_URL = f"{API_BASE_URL}/login"
API_GET_URL = f"{API_BASE_URL}/get"
API_SET_LOCATION_URL = f"{API_BASE_URL}/set/selected_location?locationId="
API_SETTINGS_URL = f"{API_BASE_URL}/get/settings"

API_SET_SETTINGS_URL = f"{API_BASE_URL}/set/advancedSettings"

API_AWAY_MODE_ON = f"{API_BASE_URL}/set/schedule/away"
API_AWAY_MODE_OFF = f"{API_BASE_URL}/set/schedule/away/off"

API_BOOST_MODE_ON = f"{API_BASE_URL}/set/schedule/boost"
API_BOOST_MODE_OFF = f"{API_BASE_URL}/set/schedule/boost/off"

OPERATION_MODE_NORMAL = 'Normal'
OPERATION_MODE_BOOST = 'Boost'

CONTROL_MODE_INTELLIGENCE = "Aquanta Intelligence"
CONTROL_MODE_TEMPERATURE = "Set Temperature"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    
    device = AquantaWaterHeater(username, password)
    await hass.async_add_executor_job(device.update)
    hass.data[DOMAIN] = device

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True
    

class AquantaWaterHeater():

    def __init__(self, username, password):
        self._username = username
        self._password = password

        self._login_time = None

        self._session = None
        self._location = None

        self._data = {}
        self._settings = {}

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
        if self._session is None or (datetime.now() - self._login_time > timedelta(minutes = 30)):
            # Login again after 30 minutes
            self.login()

    def check_response(self, response):
        if response.status_code != 200:
            _LOGGER.error(f'Operation failed, status = {response.status_code}')

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
    def device_info(self):
        return {
            "name": f'{self._settings["userDescription"]} Water Heater',
            "identifiers": {(DOMAIN, f'{self._location}_water_heater')},
            "model": "Aquanta Smart Water Heater Controller",
            "manufacturer": "Aquanta",
        }

    @property
    def name(self):
        return f'{self._settings["userDescription"]} Water Heater'

    @property
    def unique_id(self):
        return f'{self._location}_water_heater'

    @property
    def state(self):
        return self._data

    @property
    def settings(self):
        return self._settings

    @property
    def is_away_mode_on(self):
        return self.state["awayRunning"]

    @property
    def current_temperature(self):
        return round(self.state["tempValue"] * 1.8 + 32)

    @property
    def target_temperature(self):
        return round(float(self.settings["setPoint"]) * 1.8 + 32)

    @property
    def hot_water_available(self):
        return round(self.state["hw_avail_fraction"] * 100)

    @property
    def aquanta_intelligence_active(self):
        return not self.settings["aquantaIntel"]

    def set_operation_mode(self, operation_mode: str):
        self.check_login()

        if operation_mode == OPERATION_MODE_BOOST:
            if self.is_away_mode_on:
                # Turn off away mode first
                self.set_away_mode(False)

            response = self._session.put(API_BOOST_MODE_ON, data=self.get_schedule_dictionary())
            _LOGGER.info(f'Boost mode turned on. Received {API_AWAY_MODE_ON} response, status = {response.status_code}')
        else:
            response = self._session.put(API_BOOST_MODE_OFF)
            _LOGGER.info(f'Boost mode turned off. Received {API_BOOST_MODE_OFF} response, status = {response.status_code}')

        self.check_response(response)

        self.update()

    def set_target_temperature(self, target_temperature):
        self.check_login()

        json = {
                    "aquantaIntel": self.settings["aquantaIntel"],
                    "aquantaSystem": False,
                    "setPoint": (target_temperature - 32) / 1.8
                }

        response = self._session.put(API_SET_SETTINGS_URL, json=json)
        _LOGGER.info(f'Target temperature set to {target_temperature}. Received {API_SET_SETTINGS_URL} response, status = {response.status_code}')
        self.check_response(response)

        self.update()

    def set_aquanta_intelligence_active(self, active: bool):
        self.check_login()

        json = {
                    "aquantaIntel": not active,
                    "aquantaSystem": False,
                    "setPoint": float(self.settings["setPoint"])
                }

        _LOGGER.error(f'json = {json}')
        response = self._session.put(API_SET_SETTINGS_URL, json=json)
        _LOGGER.info(f'Aquanta Intelligence set to {active}. Received {API_SET_SETTINGS_URL} response, status = {response.status_code}')
        self.check_response(response)

        self.update()

    def set_away_mode(self, away_mode: bool):
        self.check_login()

        if away_mode:
            response = self._session.put(API_AWAY_MODE_ON, data=self.get_schedule_dictionary())
            _LOGGER.info(f'Away mode turned on. Received {API_AWAY_MODE_ON} response, status = {response.status_code}')
            self.check_response(response)

            # Also turn off Boost
            self.set_operation_mode(OPERATION_MODE_NORMAL)
        else:
            response = self._session.put(API_AWAY_MODE_OFF)
            _LOGGER.info(f'Away mode turned off. Received {API_AWAY_MODE_OFF} response, status = {response.status_code}')
            self.check_response(response)

        self.update()

    def update(self):
        try:
            self.check_login()
            
            response = self._session.get(API_GET_URL)
            _LOGGER.debug(f'Received {API_GET_URL} response, status = {response.status_code}, json = {response.json()}')
            self.check_response(response)
            self._data = response.json()

            response = self._session.get(API_SETTINGS_URL)
            _LOGGER.debug(f'Received {API_SETTINGS_URL} response, status = {response.status_code}, json = {response.json()}')
            self.check_response(response)
            self._settings = response.json()
        except:
            _LOGGER.error(f'Update error, will try to login and retry on the next update interval.', exc_info=True)
            self._session = None
