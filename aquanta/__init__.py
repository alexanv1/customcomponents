"""
Support for Aquanta Water Header
"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

DOMAIN = 'aquanta'

PLATFORMS = ["water_heater"]

async def async_setup(hass, config):
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aquanta from a config entry."""

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True
