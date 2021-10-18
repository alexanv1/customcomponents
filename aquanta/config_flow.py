import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (CONF_PASSWORD, CONF_USERNAME)

from . import DOMAIN

data_schema = vol.Schema({
    vol.Required(CONF_USERNAME): str,
    vol.Required(CONF_PASSWORD): str,
})

class AquantaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, info):
        if info is not None:
            return self.async_create_entry(title="Aquanta", data=info)

        return self.async_show_form(step_id="user", data_schema=data_schema)