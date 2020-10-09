import json

from requests import post, get, put

URL_SF_API = 'https://api.ps-smartfeed.cloud.petsafe.net/api/v2/'
URL_SF_USER_API = 'https://users-api.ps-smartfeed.cloud.petsafe.net/users/'


def headers(token=None):
    """
    Creates a dict of headers with JSON content-type and token, if supplied.

    :param token: access token for account
    :return: dictionary of headers

    """
    data = {'content-type': 'application/json'}
    if token:
        data['token'] = token
    return data


def sf_post(path='', token=None, data=None):
    """
    Sends a POST to PetSafe SmartFeed API.

    Example: sf_post(path=feeder.api_path + 'meals', token=user_token, data=food_data)

    :param path: the path on the API
    :param token: the account's token
    :param data: the POST data
    :return: the request response

    """
    return post(URL_SF_API + path, headers=headers(token), json=data)


def sf_get(path='', token=None):
    """
    Sends a GET to PetSafe SmartFeed API.

    Example: sf_get(path='feeders', token=user_token)

    :param path: the path on the API
    :param token: the account's token
    :return: the request response

    """
    return get(URL_SF_API + path, headers=headers(token))


def sf_put(path='', token=None, data=None):
    """
    Sends a PUTS to PetSafe SmartFeed API.

    Example: sf_put(path='feeders', token=user_token, data=my_data)

    :param path: the path on the API
    :param token: the account's token
    :param data: the PUT data
    :return: the request response

    """
    return put(URL_SF_API + path, headers=headers(token), json=data)


def sf_user_post(path='', token=None, data=None):
    """
    Sends a POST to PetSafe SmartFeed User API.

    Example: sf_user_post(path='token', data=user_data)

    :param path: the path on the API
    :param token: the account's token
    :param data: the POST data
    :return: the request response

    """
    return post(URL_SF_USER_API + path, headers=headers(token), json=data)


def sf_user_get(path='', token=None):
    """
    Sends a GET to PetSafe SmartFeed User API.

    Example: sf_user_get(path='')

    :param path: the path on the API
    :param token: the account's token
    :return: the request response

    """
    return get(URL_SF_USER_API + path, headers=headers(token))


def request_code(email):
    """
    Sends a request to PetSafe's User API to generate a code and send it to the specified email.

    :param email: the email of the account

    """
    data = {'email': email}
    response = sf_user_post(data=data)
    response.raise_for_status()


def request_token_from_code(email, code):
    """
    Send a request to PetSafe's User API to generate an access token for the specified email.

    :param email: the email of the account
    :param code: the code retrieved using request_code(email)
    :return: the token

    """
    data = {'email': email, 'code': code}

    response = sf_user_post('tokens', data=data)
    response.raise_for_status()

    content = json.loads(response.content.decode('UTF-8'))
    return content['deprecatedToken']
