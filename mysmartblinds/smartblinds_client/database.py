import warnings

from .base import AuthenticationBase


class Database(AuthenticationBase):
    """Database & Active Directory / LDAP Authentication.

    Args:
        domain (str): Your auth0 domain (e.g: username.auth0.com)
    """

    def login(self, client_id, username, password, connection, id_token=None,
              grant_type='password', device=None, scope='openid'):
        """Login using username and password

        Given the user credentials and the connection specified, it will do
        the authentication on the provider and return a dict with the
        access_token and id_token. This endpoint only works for database
        connections, passwordless connections, Active Directory/LDAP,
        Windows Azure AD and ADFS.
        """
        warnings.warn("/oauth/ro will be deprecated in future releases", DeprecationWarning)

        body = {
            'client_id': client_id,
            'username': username,
            'password': password,
            'connection': connection,
            'grant_type': grant_type,
            'scope': scope,
        }
        if id_token:
            body.update({'id_token': id_token})
        if device:
            body.update({'device': device})
        return self.post('{}://{}/oauth/ro'.format(self.protocol, self.domain), data=body)
