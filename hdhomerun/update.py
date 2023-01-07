"""
Simple sensor platform for HDHomeRun devices
"""

from datetime import timedelta
from typing import Any

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)

from homeassistant.core import callback
from homeassistant.util import slugify

from . import DOMAIN, HDHomeRunDevice

SCAN_INTERVAL = timedelta(seconds=30)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up of the HDHomeRun device."""

    device = hass.data[DOMAIN]
    async_add_entities([HDHomeRunUpdate(device)])


class HDHomeRunUpdate(UpdateEntity):
    """Update entity for HD HomeRun device."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = UpdateEntityFeature.INSTALL

    def __init__(self, device : HDHomeRunDevice):
        self._device = device

    @property
    def device_info(self):
        return self._device.device_info

    @property
    def name(self):
        return f'HDHomeRun Firmware'

    @property
    def unique_id(self):
        return f'{slugify(self.name)}'

    @property
    def installed_version(self) -> str | None:
        """Version currently in use."""
        return self._device.device_data["FirmwareVersion"]

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""

        upgrade_available = None
        if "UpgradeAvailable" in self._device.device_data:
            upgrade_available = self._device.device_data["UpgradeAvailable"]

        if upgrade_available is not None and not upgrade_available.startswith(self.installed_version):
            return upgrade_available

        return self.installed_version

    @property
    def should_poll(self):
        return True

    def install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        self._device.upgrade_firmware()

    def update(self) -> None:
        """Updates are handled via the info sensor entity"""