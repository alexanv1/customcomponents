from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .devices import get_feeders

CONF_API_TOKEN = 'api_token'

DOMAIN = 'smartfeed'

PLATFORMS = ["switch", "sensor"]

async def async_setup(hass, config):
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SmartFeed from a config entry."""
    
    token = entry.data[CONF_API_TOKEN]

    # Get the devices
    hass.data[DOMAIN] = await hass.async_add_executor_job(get_feeders, token)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True

def get_device_info(feeder):
    return {
        "name": f'{feeder.friendly_name} Feeder',
        "identifiers": {(DOMAIN, feeder.api_name)},
        "model": "PetSafe SmartFeed",
        "manufacturer": "PetSafe",
    }