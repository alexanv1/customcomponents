import voluptuous as vol
from homeassistant import config_entries

from . import DOMAIN, CONF_HOSTNAME

data_schema = vol.Schema({
    vol.Required(CONF_HOSTNAME): str,
})

class HDHomeRunConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, info):
        if info is not None:
            return self.async_create_entry(title="HD HomeRun", data=info)

        return self.async_show_form(step_id="user", data_schema=data_schema)