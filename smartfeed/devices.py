import json
import logging
from . import api

_LOGGER = logging.getLogger(__name__)

def get_feeders(api_token):
    """
    Sends a request to PetSafe's API for all feeders associated with account.

    :param api_token: the access token for the account
    :return: list of Feeders

    """
    api.get_idtoken(api_token)
    response = api.sf_get('feeders')
    response.raise_for_status()
    content = response.content.decode('UTF-8')

    response_content_json = json.loads(content)
    _LOGGER.debug(f"get_feeders: Retrieved feeder information: {response_content_json}")

    return [DeviceSmartFeed(feeder_data) for feeder_data in response_content_json]


class DeviceSmartFeed:
    def __init__(self, data):
        self._data = data

    def __str__(self):
        return self.to_json()

    def to_json(self):
        """
        All feeder data formatted as JSON.
        """
        return json.dumps(self._data, indent=2)

    def update_data(self):
        """
        Updates self._data to the feeder's current online state.

        """
        response = api.sf_get(self.api_path)
        response.raise_for_status()
        self._data = json.loads(response.content.decode('UTF-8'))

    def put_setting(self, setting, value, force_update=False):
        """
        Changes the value of a specified setting. Sends PUT to API.

        :param setting: the setting to change
        :param value: the new value of that setting
        :param force_update: if True, update ALL data after PUT. Defaults to False.

        """
        response = api.sf_put(self.api_path + '/settings/' + setting, data={
            'value': value
        })
        response.raise_for_status()

        if force_update:
            self.update_data()
        else:
            self._data['settings'][setting] = value

    def get_messages_since(self, days=7):
        """
        Requests all feeder messages.

        :param days: how many days to request back. Defaults to 7.
        :return: the APIs response in JSON.

        """
        response = api.sf_get(self.api_path + '/messages?days=' + str(days))
        response.raise_for_status()
        return json.loads(response.content.decode('UTF-8'))

    def get_last_feeding(self):
        """
        Finds the last feeding in the feeder's messages.

        :return: the feeding message, if found. Otherwise, None.

        """
        messages = self.get_messages_since(days=2)
        for message in messages:
            if message['message_type'] == 'FEED_DONE':
                return message
        return None

    def feed(self, amount=1, slow_feed=None, update_data=True):
        """
        Triggers the feeder to begin feeding.

        :param amount: the amount to feed in 1/8 increments.
        :param slow_feed: if True, will use slow feeding. If None, defaults to current settings.
        :param update_data: if True, will update the feeder's data after feeding. Defaults to True.

        """
        if slow_feed is None:
            slow_feed = self._data['settings']['slow_feed']
        response = api.sf_post(self.api_path + '/meals', data={
            'amount': amount,
            'slow_feed': slow_feed
        })
        response.raise_for_status()

        if update_data:
            self.update_data()

    def repeat_feed(self):
        """
        Repeats the last feeding.

        """
        last_feeding = self.get_last_feeding()
        self.feed(last_feeding['payload']['amount'])
        
    def prime(self):
        """
        Feeds 5/8 cups to prime the feeder.

        """
        self.feed(5, False)

    @property
    def api_name(self):
        """The feeder's thing_name from the API."""
        return self._data['thing_name']

    @property
    def api_path(self):
        """The feeder's path on the API."""
        return 'feeders/' + self.api_name

    @property
    def id(self):
        """The feeder's ID."""
        return self._data['id']

    @property
    def battery_voltage(self):
        """The feeder's calculated current battery voltage."""
        try:
            return round(int(self._data['battery_voltage']) / 32767 * 7.2, 3)
        except ValueError:
            return -1

    @property
    def battery_level(self):
        """The feeder's current battery level (high, medium, low, dead, not installed, unknown)."""
        if not self._data['is_batteries_installed']:
            return 'not installed'
        if self.battery_voltage > 5.9:
            return 'high'
        elif self.battery_voltage > 5.5:
            return 'medium'
        elif self.battery_voltage > 5:
            return 'low'
        elif self.battery_voltage >= 0:
            return 'dead'
        else:
            return 'unknown'

    @property
    def battery_level_int(self):
        """The feeder's current battery level as an integer."""
        if not self._data['is_batteries_installed']:
            return 0

        minVoltage = 22755
        maxVoltage = 29100

        # Respect max and min bounds
        voltage = max(min(int(self._data['battery_voltage']), maxVoltage), minVoltage)

        return round(100 * (voltage - minVoltage) / (maxVoltage - minVoltage))

    @property
    def available(self):
        """If true, the feeder is connected\available."""
        return self._data['connection_status'] == 2
        
    @property
    def paused(self):
        """If true, the feeder will not follow its scheduling."""
        return self._data['settings']['paused']
    
    @paused.setter
    def paused(self, value):
        self.put_setting('paused', value)

    @property
    def slow_feed(self):
        """If true, the feeder will dispense food slowly."""
        return self._data['settings']['slow_feed']

    @slow_feed.setter
    def slow_feed(self, value):
        self.put_setting('slow_feed', value)

    @property
    def child_lock(self):
        """If true, the feeder's physical button is disabled."""
        return self._data['settings']['child_lock']

    @child_lock.setter
    def child_lock(self, value):
        self.put_setting('child_lock', value)

    @property
    def friendly_name(self):
        """The feeder's display name."""
        return self._data['settings']['friendly_name']

    @friendly_name.setter
    def friendly_name(self, value):
        self.put_setting('friendly_name', value)

    @property
    def pet_type(self):
        """The feeder's pet type."""
        return self._data['settings']['pet_type']

    @pet_type.setter
    def pet_type(self, value):
        self.put_setting('pet_type', value)

    @property
    def food_sensor_current(self):
        """The feeder's food sensor status."""
        return self._data['food_sensor_current']

    @property
    def food_low_status(self):
        """
        The feeder's food low status.
        :return: 0 if Full, 1 if Low, 2 if Empty
        """
        return int(self._data['is_food_low'])

    @property
    def data_json(self):
        return self._data
