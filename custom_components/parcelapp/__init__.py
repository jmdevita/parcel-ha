"""Integration for Parcel tracking."""

import logging
from typing import Any

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN
from .coordinator import ParcelConfigEntry, ParcelUpdateCoordinator

PLATFORMS = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the integration."""
    _LOGGER.info("Setting up the Parcel integration")

    # Store integration data in hass.data
    hass.data[DOMAIN] = {}

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ParcelConfigEntry) -> bool:
    """Set up the integration based on a config entry."""
    _LOGGER.info("Setting up Parcel integration based on config entry")

    # Check if the entry is already set up
    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        raise ValueError(
            f"Config entry {entry.title} ({entry.entry_id}) for {DOMAIN} has already been setup!"
        )

    # Setup the coordinator
    coordinator = ParcelUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    # Store the coordinator in hass.data
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"coordinator": coordinator}

    # Forward entry setups only if not already forwarded
    if "platforms" not in hass.data[DOMAIN][entry.entry_id]:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        hass.data[DOMAIN][entry.entry_id]["platforms"] = PLATFORMS

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(async_update_entry))
    await cleanup_old_device(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ParcelConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Parcel integration")

    # Unload platforms
    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        platforms = hass.data[DOMAIN][entry.entry_id].get("platforms", [])
        unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)

        # Clean up resources
        if unload_ok:
            hass.data[DOMAIN].pop(entry.entry_id)
            if not hass.data[DOMAIN]:  # If no entries remain, clean up DOMAIN
                hass.data.pop(DOMAIN)

        return unload_ok

    return False


async def async_update_entry(hass: HomeAssistant, config_entry: ParcelConfigEntry):
    """Reload Parcel component when options changed."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def cleanup_old_device(hass: HomeAssistant) -> None:
    """Cleanup device without proper device identifier."""
    device_reg = dr.async_get(hass)
    device = device_reg.async_get_device(identifiers={(DOMAIN,)})
    if device:
        _LOGGER.debug("Removing improper device %s", device.name)
        device_reg.async_remove_device(device.id)
