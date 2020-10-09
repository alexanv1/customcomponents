import json
from .api import *


def get_feeders(token):
    """
    Sends a request to PetSafe's API for all feeders associated with account.

    :param token: the access token for the account
    :return: list of Feeders

    """
    response = sf_get('feeders', token)
    response.raise_for_status()
    content = response.content.decode('UTF-8')
    return [DeviceSmartFeed(token, feeder_data) for feeder_data in json.loads(content)]


class DeviceSmartFeed:
    def __init__(self, token, data):
        self.token = token
        self.data = data

    def __str__(self):
        return json.dumps(self.data, indent=2)

    def update_data(self):
        """
        Updates self.data to the feeder's current online state.

        """
        response = sf_get(self.api_path, token=self.token)
        response.raise_for_status()
        self.data = json.loads(response.content.decode('UTF-8'))

    def put_setting(self, setting, value, force_update=False):
        """
        Changes the value of a specified setting. Sends PUT to API.

        :param setting: the setting to change
        :param value: the new value of that setting
        :param force_update: if True, update ALL data after PUT. Defaults to False.

        """
        response = sf_put(self.api_path + 'settings/' + setting, token=self.token, data={
            'value': value
        })
        response.raise_for_status()

        if force_update:
            self.update_data()
        else:
            self.data['settings'][setting] = value

    def get_messages_since(self, days=7):
        """
        Requests all feeder messages.

        :param days: how many days to request back. Defaults to 7.
        :return: the APIs response in JSON.

        """
        response = sf_get(self.api_path + 'messages?days=' + str(days), token=self.token)
        response.raise_for_status()
        return json.loads(response.content.decode('UTF-8'))

    def get_last_feeding(self):
        """
        Finds the last feeding in the feeder's messages.

        :return: the feeding message, if found. Otherwise, None.

        """
        messages = self.get_messages_since()
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
            slow_feed = self.data['settings']['slow_feed']
        response = sf_post(self.api_path + 'meals', self.token, data={
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
        self.feed(last_feeding['amount'])
        
    def prime(self):
        """
        Feeds 5/8 cups to prime the feeder.

        """
        self.feed(5, False)

    @property
    def api_name(self):
        """The feeder's thing_name from the API."""
        return self.data['thing_name']

    @property
    def api_path(self):
        """The feeder's path on the API."""
        return 'feeders/' + self.api_name + '/'

    @property
    def id(self):
        """The feeder's ID."""
        return self.data['id']

    @property
    def battery_voltage(self):
        """The feeder's calculated current battery voltage."""
        try:
            return round(int(self.data['battery_voltage']) / 32767 * 7.2, 3)
        except ValueError:
            return -1

    @property
    def battery_level(self):
        """The feeder's current battery level (high, medium, low, dead, not installed, unknown)."""
        if not self.data['is_batteries_installed']:
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
    def available(self):
        """If true, the feeder is connected\available."""
        return self.data['connection_status'] == 2
        
    @property
    def paused(self):
        """If true, the feeder will not follow its scheduling."""
        return self.data['settings']['paused']
    
    @paused.setter
    def paused(self, value):
        self.put_setting('paused', value)

    @property
    def slow_feed(self):
        """If true, the feeder will dispense food slowly."""
        return self.data['settings']['slow_feed']

    @slow_feed.setter
    def slow_feed(self, value):
        self.put_setting('slow_feed', value)

    @property
    def child_lock(self):
        """If true, the feeder's physical button is disabled."""
        return self.data['settings']['child_lock']

    @child_lock.setter
    def child_lock(self, value):
        self.put_setting('child_lock', value)

    @property
    def friendly_name(self):
        """The feeder's display name."""
        return self.data['settings']['friendly_name']

    @friendly_name.setter
    def friendly_name(self, value):
        self.put_setting('friendly_name', value)

    @property
    def pet_type(self):
        """The feeder's pet type."""
        return self.data['settings']['pet_type']

    @pet_type.setter
    def pet_type(self, value):
        self.put_setting('pet_type', value)

    @property
    def data_json(self):
        return self.data
