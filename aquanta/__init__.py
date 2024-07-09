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

API_EFFICIENCY_SELECTION = f"{API_BASE_URL}/set/efficiencySelection"

API_AWAY_MODE_ON = f"{API_BASE_URL}/set/schedule/away"
API_AWAY_MODE_OFF = f"{API_BASE_URL}/set/schedule/away/off"

API_BOOST_MODE_ON = f"{API_BASE_URL}/set/schedule/boost"
API_BOOST_MODE_OFF = f"{API_BASE_URL}/set/schedule/boost/off"

OPERATION_MODE_NORMAL = 'Normal'
OPERATION_MODE_BOOST = 'Boost'
OPERATION_MODE_AWAY = 'Away'

CONTROL_MODE_INTELLIGENCE = "Aquanta Intelligence"
CONTROL_MODE_TEMPERATURE = "Set Temperature"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    session = await hass.async_add_executor_job(login, username, password)
    locations = await hass.async_add_executor_job(get_locations, session)

    devices = []
    for location in locations:
        device = AquantaWaterHeater(username, password, location)
        await hass.async_add_executor_job(device.update)
        devices += [device] 

    hass.data[DOMAIN] = devices
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def check_response(response: requests.Response):
    if response.status_code != 200:
        _LOGGER.error(f'Operation failed, status = {response.status_code}, response = {response.text}')
    response.raise_for_status()
          


def login(username: str, password: str):
    session = requests.Session()

    _LOGGER.info(f'Logging in to Aquanta.')

    login_data = dict(email=username, password=password, returnSecureToken=True)
    verifyPasswordResponse = session.post("https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key=AIzaSyBHWHB8Org9BWCH-YFzis-8oEbMaKmI2Tw", data=login_data)
    check_response(verifyPasswordResponse)
    _LOGGER.info(f'Received VerifyPassword response, status = {verifyPasswordResponse.status_code}, json = {verifyPasswordResponse.json()}')

    idToken = dict(idToken = verifyPasswordResponse.json()["idToken"])
    loginResponse = session.post(f"{API_BASE_URL}/login", data=idToken)
    check_response(loginResponse)
    _LOGGER.info(f'Received login response, status = {loginResponse.status_code}, json = {loginResponse.json()}')

    if loginResponse.status_code != 200:
        _LOGGER.error(f'Login Failed, status = {loginResponse.status_code}')

    return session


def get_locations(session):
    response = session.get(API_GET_URL)
    check_response(response)
        
    return response.json()["locations"]


class AquantaWaterHeater():

    def __init__(self, username, password, location):
        self._username = username
        self._password = password
        self._location = location

        self._login_time = None
        self._session = None

        self._data = {}
        self._settings = {}
    
    def check_login(self):
        if self._session is None or (datetime.now() - self._login_time > timedelta(minutes = 30)):
            # Login again after 30 minutes
            self._session = login(self._username, self._password)
            self._login_time = datetime.now()

            self.set_location()

    def set_location(self):
        response = self._session.put(f"{API_SET_LOCATION_URL}{self._location}")
        _LOGGER.info(f'Set location to {self._location}, status = {response.status_code}')

        check_response(response)

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

    @property
    def performance_mode(self):
        return self.state["efficiencySelection"]

    def set_performance_mode(self, performance_mode: str):
        self.check_login()

        if performance_mode is not None:
            json = {"efficiencySelection": performance_mode}

        response = self._session.put(API_EFFICIENCY_SELECTION, json=json)
        _LOGGER.info(f'Performance mode set to {performance_mode}. Received {API_SET_SETTINGS_URL} response, status = {response.status_code}')
        check_response(response)

        self.update()

    def set_operation_mode(self, operation_mode: str):
        self.check_login()

        if operation_mode == OPERATION_MODE_BOOST:
            self.set_away_mode(False)

            response = self._session.put(API_BOOST_MODE_ON, data=self.get_schedule_dictionary())
            _LOGGER.info(f'Boost mode turned on. Received {API_AWAY_MODE_ON} response, status = {response.status_code}')

        elif operation_mode == OPERATION_MODE_AWAY:
            response = self._session.put(API_BOOST_MODE_OFF)
            _LOGGER.info(f'Boost mode turned off. Received {API_BOOST_MODE_OFF} response, status = {response.status_code}')

            self.set_away_mode(True)
            
        else:
            response = self._session.put(API_BOOST_MODE_OFF)
            _LOGGER.info(f'Boost mode turned off. Received {API_BOOST_MODE_OFF} response, status = {response.status_code}')

            self.set_away_mode(False)

        check_response(response)

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
        check_response(response)

        self.update()

    def set_aquanta_intelligence_active(self, active: bool):
        self.check_login()

        json = {
                    "aquantaIntel": not active,
                    "aquantaSystem": False,
                    "setPoint": float(self.settings["setPoint"])
                }

        response = self._session.put(API_SET_SETTINGS_URL, json=json)
        _LOGGER.info(f'Aquanta Intelligence set to {active}. Received {API_SET_SETTINGS_URL} response, status = {response.status_code}')
        check_response(response)

        self.update()

    def set_away_mode(self, away_mode: bool):
        self.check_login()

        if away_mode:
            response = self._session.put(API_AWAY_MODE_ON, data=self.get_schedule_dictionary())
            _LOGGER.info(f'Away mode turned on. Received {API_AWAY_MODE_ON} response, status = {response.status_code}')
            check_response(response)
        else:
            response = self._session.put(API_AWAY_MODE_OFF)
            _LOGGER.info(f'Away mode turned off. Received {API_AWAY_MODE_OFF} response, status = {response.status_code}')
            check_response(response)

        self.update()

    def update(self):
        try:
            self.check_login()
            
            response = self._session.get(API_GET_URL)
            check_response(response)
            _LOGGER.debug(f'Received {API_GET_URL} response, status = {response.status_code}, json = {response.json()}')
            self._data = response.json()

            response = self._session.get(API_SETTINGS_URL)
            check_response(response)
            _LOGGER.debug(f'Received {API_SETTINGS_URL} response, status = {response.status_code}, json = {response.json()}')
            self._settings = response.json()
        except:
            _LOGGER.error(f'Update error, will try to login and retry on the next update interval.', exc_info=True)
            self._session = None
