"""
Support for AutoPi
"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

DOMAIN = 'autopi'

PLATFORMS = ["device_tracker"]

async def async_setup(hass, config):
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AutoPi from a config entry."""

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True