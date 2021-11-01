from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

CONF_HOSTNAME = 'hostname'

DOMAIN = 'hdhomerun'

PLATFORMS = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HDHomeRun from a config entry."""
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True