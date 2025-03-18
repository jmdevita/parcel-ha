"""Integration for Parcel tracking coordinator."""

from datetime import timedelta
import json
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, PARCEL_URL, UPDATE_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)
type ParcelConfigEntry = ConfigEntry[ParcelUpdateCoordinator]


class ParcelUpdateCoordinator(DataUpdateCoordinator):
    """Class to handle fetching data from the API."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the data update coordinator."""
        self.api_key = entry.data["api_key"]
        self._hass = hass
        self.session = async_get_clientsession(self._hass)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
            always_update=True,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the API and return the top value."""
        API_URL = f"{PARCEL_URL}?filter_mode=recent"
        try:
            headers = {"api-key": self.api_key, "Content-Type": "application/json"}
            response = await self.session.get(API_URL, headers=headers)
            response.raise_for_status()

            payload = await response.text()
            try:
                return json.loads(payload)["deliveries"]
            except TypeError:
                return json.loads(payload)

        except Exception as err:
            raise UpdateFailed(f"Error fetching data from API: {err}") from err
