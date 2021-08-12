import json
import threading
import logging

from requests import post, get, put

URL_SF_API = 'https://platform.cloud.petsafe.net/smart-feed/'

ID_TOKEN = None

API_TOKEN = None

REFRESH_TIMER = None

_LOGGER = logging.getLogger(__name__)

def get_idtoken(api_token):
    global API_TOKEN
    global ID_TOKEN
    global REFRESH_TIMER

    API_TOKEN = api_token

    authData = {
        "AuthParameters": {"REFRESH_TOKEN": API_TOKEN},
        "AuthFlow": "REFRESH_TOKEN_AUTH",
        "ClientId": "18hpp04puqmgf5nc6o474lcp2g"
    }

    headers = {
        'Content-Type': 'application/x-amz-json-1.1',
        'X-Amz-Target': 'AWSCognitoIdentityProviderService.InitiateAuth'
    }

    authUrl = "https://cognito-idp.us-east-1.amazonaws.com/"
    _LOGGER.debug(f"get_idtoken: Sending POST to {authUrl} with headers={headers} and authData={authData}")

    # default expiry time to 30 minutes
    expiryTimeInSeconds = 1800

    try:
        response = post(authUrl, headers=headers, json=authData)
        response_content_json = json.loads(response.content)
        _LOGGER.debug(f"get_idtoken: Retrieved auth response: {response_content_json}")

        ID_TOKEN = response_content_json["AuthenticationResult"]["IdToken"]

        # Schedule a timer to refresh the ID token 2 minutes before it expires
        expiryTimeInSeconds = response_content_json["AuthenticationResult"]["ExpiresIn"]
    except Exception as exception:
        _LOGGER.error(f'get_idtoken: Failed to get ID token. Exception: {exception}')
    finally:
        _LOGGER.debug(f"get_idtoken: Token expires in {expiryTimeInSeconds} seconds, scheduling refresh timer to fire after {expiryTimeInSeconds - 120} seconds")
        REFRESH_TIMER = threading.Timer(expiryTimeInSeconds - 120, refresh_idtoken)
        REFRESH_TIMER.start()

def refresh_idtoken():
    _LOGGER.debug("refresh_idtoken: Timer fired, will retrieve new ID token.")
    get_idtoken(API_TOKEN)

    # Getting feeders after token refresh
    response = sf_get('feeders')
    response.raise_for_status()
    feederData = json.loads(response.content.decode('UTF-8'))
    _LOGGER.debug(f"refresh_idtoken: Retrieved updated feeder information: {feederData}")

def headers():
    headers = {
        'content-type': 'application/json',
        'Authorization': ID_TOKEN
    }

    return headers


def sf_post(path='', data=None):
    """
    Sends a POST to PetSafe SmartFeed API.

    Example: sf_post(path=feeder.api_path + 'meals', token=user_token, data=food_data)

    :param path: the path on the API
    :param data: the POST data
    :return: the request response

    """
    requestHeaders = headers()
    url = URL_SF_API + path
    _LOGGER.debug(f"sf_post: Sending POST to {url} with headers={requestHeaders} and data={data}")
    return post(url, headers=requestHeaders, json=data)


def sf_get(path=''):
    """
    Sends a GET to PetSafe SmartFeed API.

    Example: sf_get(path='feeders', token=user_token)

    :param path: the path on the API
    :return: the request response

    """
    requestHeaders = headers()
    url = URL_SF_API + path
    _LOGGER.debug(f"sf_get: Sending GET to {url} with headers={requestHeaders}")
    return get(url, headers=requestHeaders)


def sf_put(path='', data=None):
    """
    Sends a PUTS to PetSafe SmartFeed API.

    Example: sf_put(path='feeders', token=user_token, data=my_data)

    :param path: the path on the API
    :param data: the PUT data
    :return: the request response

    """
    requestHeaders = headers()
    url = URL_SF_API + path
    _LOGGER.debug(f"sf_put: Sending PUT to {url} with headers={requestHeaders} and data={data}")
    return put(url, headers=requestHeaders, json=data)