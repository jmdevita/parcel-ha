"""Provide info to system health."""

import os
from typing import Any

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback
from .const import DOMAIN, PARCEL_URL
from .coordinator import ParcelConfigEntry


@callback
def async_register(hass: HomeAssistant, register: system_health.SystemHealthRegistration) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)

async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the info page."""
    config_entry: ParcelConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]
    # quota_info = await config_entry.runtime_data.async_get_quota_info()

    return {
        # "consumed_requests": quota_info.consumed_requests,
        # "remaining_requests": quota_info.requests_remaining,
        "can_reach_server": system_health.async_check_can_reach_url(hass, PARCEL_URL),
    }