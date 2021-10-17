import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (CONF_PASSWORD, CONF_USERNAME)

from . import DOMAIN, CONF_INCLUDE_ROOMS

data_schema = vol.Schema({
    vol.Required(CONF_USERNAME): str,
    vol.Required(CONF_PASSWORD): str,
    vol.Optional(CONF_INCLUDE_ROOMS, default=False): bool,
})

class MySmartBlindsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, info):
        if info is not None:
            return self.async_create_entry(title="MySmartBlinds", data=info)

        return self.async_show_form(step_id="user", data_schema=data_schema)