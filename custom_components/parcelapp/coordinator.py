"""Integration for Parcel tracking coordinator."""

from datetime import timedelta, datetime
import json
import logging
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    PARCEL_URL,
    UPDATE_INTERVAL_SECONDS,
    CARRIER_CODE_ENDPOINT,
    STORAGE_KEY,
    STORAGE_VERSION,
    DEFAULT_RETRY_AFTER_SECONDS,
)

_LOGGER = logging.getLogger(__name__)
type ParcelConfigEntry = ConfigEntry[ParcelUpdateCoordinator]


class ParcelUpdateCoordinator(DataUpdateCoordinator):
    """Class to handle fetching data from the API."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the data update coordinator."""
        self.api_key = entry.data["api_key"]
        self._hass = hass
        self.session = async_get_clientsession(self._hass)
        self.carrier_codes = {"carrier_codes_updated": "", "carrier_codes": {}}
        self._configured_interval_seconds = entry.options.get(
            "update_interval", UPDATE_INTERVAL_SECONDS
        )
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry.entry_id}")
        self._cached_data: dict[str, Any] | None = None
        self._skip_next_update = False

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=self._configured_interval_seconds),
            always_update=True,
        )

    async def _async_setup(self) -> None:
        """Load cached data from disk on startup."""
        stored = await self._store.async_load()
        if stored is None:
            return

        self._cached_data = stored

        # Restore carrier codes from cache
        cached_carrier_codes = stored.get("carrier_codes", {})
        if cached_carrier_codes:
            self.carrier_codes = {
                "carrier_codes_updated": stored.get("carrier_codes_updated", ""),
                "carrier_codes": cached_carrier_codes,
            }

        # If cache is fresh enough, skip the first API call
        cached_timestamp = stored.get("utc_timestamp")
        if cached_timestamp:
            try:
                cache_time = datetime.strptime(
                    cached_timestamp, "%Y-%m-%d %H:%M:%S.%f"
                )
                age_seconds = (datetime.now() - cache_time).total_seconds()
                if age_seconds < self._configured_interval_seconds:
                    self._skip_next_update = True
                    _LOGGER.info(
                        "Cached data is fresh (%.0fs old), will skip first API call",
                        age_seconds,
                    )
            except (ValueError, TypeError):
                _LOGGER.debug(
                    "Could not parse cached timestamp, will fetch fresh data"
                )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the API and return the top value."""
        if self._skip_next_update and self._cached_data is not None:
            self._skip_next_update = False
            _LOGGER.debug("Returning cached data, skipping API call")
            return self._cached_data

        API_URL = f"{PARCEL_URL}?filter_mode=recent"
        carrier_codes_updated = self.carrier_codes["carrier_codes_updated"]
        try:
            updated = datetime.strptime(carrier_codes_updated, "%Y-%m-%d %H:%M:%S.%f")
        except (ValueError, TypeError):
            updated = datetime.now() + timedelta(hours=-13)
        if updated < datetime.now() + timedelta(hours=-12):
            try:
                response = await self.session.get(CARRIER_CODE_ENDPOINT)
                if response.status == 429:
                    _LOGGER.warning(
                        "Rate limited on carrier codes endpoint, keeping existing codes"
                    )
                    carrier_codes_raw_json = None
                else:
                    response.raise_for_status()
                    payload = await response.text()
                    carrier_codes_raw_json = json.loads(payload)
            except (aiohttp.ClientError, json.JSONDecodeError, TimeoutError):
                carrier_codes_raw_json = None
            if carrier_codes_raw_json is not None:
                carrier_codes_raw_json.update(pholder="Placeholder")
                carrier_codes_raw_json.update(none="None")
                carrier_codes_json = {
                    "carrier_codes_updated": str(datetime.now()),
                    "carrier_codes": {},
                }
                carrier_codes_json["carrier_codes"] = carrier_codes_raw_json
                self.carrier_codes = carrier_codes_json
        carrier_codes_json = self.carrier_codes
        try:
            headers = {"api-key": self.api_key, "Content-Type": "application/json"}
            response = await self.session.get(API_URL, headers=headers)

            if response.status == 429:
                retry_after = DEFAULT_RETRY_AFTER_SECONDS
                retry_header = response.headers.get("Retry-After")
                if retry_header:
                    try:
                        retry_after = int(retry_header)
                    except ValueError:
                        pass
                _LOGGER.warning(
                    "Parcel API rate limit hit (429). Backing off for %d seconds",
                    retry_after,
                )
                if self._cached_data is not None:
                    self.update_interval = timedelta(seconds=retry_after)
                    return self._cached_data
                raise UpdateFailed(
                    "Rate limited by Parcel API (429) and no cached data available."
                )

            response.raise_for_status()
            payload = await response.text()
            payload_json = json.loads(payload)
            payload_json["carrier_codes_updated"] = carrier_codes_json[
                "carrier_codes_updated"
            ]
            payload_json["carrier_codes"] = carrier_codes_json["carrier_codes"]
            payload_json["utc_timestamp"] = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S.%f"
            )
            self._cached_data = payload_json
            await self._store.async_save(payload_json)
            self.update_interval = timedelta(seconds=self._configured_interval_seconds)

            return payload_json

        except UpdateFailed:
            raise
        except Exception as err:
            if self._cached_data is not None:
                _LOGGER.warning(
                    "Error fetching data from API: %s. Returning cached data.", err
                )
                return self._cached_data
            raise UpdateFailed(f"Error fetching data from API: {err}") from err
