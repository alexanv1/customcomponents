from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

CONF_API_TOKEN = 'api_token'

DOMAIN = 'moodo'

PLATFORMS = ["fan"]

async def async_setup(hass, config):
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Moodo from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True