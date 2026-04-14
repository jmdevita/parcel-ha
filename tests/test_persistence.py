"""Tests for data persistence and rate limit handling."""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.parcelapp.coordinator import ParcelUpdateCoordinator
from custom_components.parcelapp.const import (
    UPDATE_INTERVAL_SECONDS,
    DEFAULT_RETRY_AFTER_SECONDS,
)


def _load_fixture(name: str) -> dict:
    """Load a test fixture JSON file."""
    fixtures_path = Path(__file__).parent / "fixtures"
    with open(fixtures_path / name) as file:
        return json.load(file)


def _make_mock_entry(entry_id: str = "test_entry_123") -> Mock:
    """Create a mock ConfigEntry."""
    mock_entry = AsyncMock()
    mock_entry.data = {"api_key": "test_api_key"}
    mock_entry.options = {}
    mock_entry.entry_id = entry_id
    mock_entry.state = ConfigEntryState.SETUP_IN_PROGRESS
    mock_entry.async_on_unload = Mock()
    return mock_entry


def _make_cached_data(age_seconds: float = 60.0) -> dict:
    """Create cached data with a timestamp of the given age."""
    fixture = _load_fixture("recent.json")
    cache_time = datetime.now() - timedelta(seconds=age_seconds)
    fixture["carrier_codes_updated"] = str(datetime.now())
    fixture["carrier_codes"] = {"fedex": "FedEx", "usps": "USPS", "pholder": "Placeholder", "none": "None"}
    fixture["utc_timestamp"] = cache_time.strftime("%Y-%m-%d %H:%M:%S.%f")
    return fixture


@pytest.mark.asyncio
async def test_fresh_cache_skips_api_call(hass: HomeAssistant, aioclient_mock):
    """Test that fresh cached data skips the first API call."""
    cached = _make_cached_data(age_seconds=60)  # 60s old, interval is 300s
    mock_entry = _make_mock_entry()

    # Mock the API — if called, will return 200 but we can track it
    api_url = "https://api.parcel.app/external/deliveries/?filter_mode=recent"
    aioclient_mock.get(api_url, json=_load_fixture("recent.json"), status=200)
    carrier_url = "https://api.parcel.app/external/supported_carriers.json"
    aioclient_mock.get(carrier_url, json={"fedex": "FedEx"}, status=200)

    coordinator = ParcelUpdateCoordinator(hass, mock_entry)
    coordinator.session = async_get_clientsession(hass)

    # Patch the store to return cached data
    with patch.object(coordinator._store, "async_load", return_value=cached):
        with patch.object(coordinator._store, "async_save") as mock_save:
            await coordinator.async_config_entry_first_refresh()

            # Should NOT have saved (didn't fetch from API)
            mock_save.assert_not_called()

    # Data should match the cache
    assert coordinator.data is not None
    assert coordinator.data["deliveries"] == cached["deliveries"]
    assert coordinator.last_update_success


@pytest.mark.asyncio
async def test_stale_cache_triggers_api_call(hass: HomeAssistant, aioclient_mock):
    """Test that stale cached data triggers an API call."""
    cached = _make_cached_data(age_seconds=600)  # 600s old, interval is 300s
    mock_entry = _make_mock_entry()

    fresh_data = _load_fixture("recent.json")
    api_url = "https://api.parcel.app/external/deliveries/?filter_mode=recent"
    aioclient_mock.get(api_url, json=fresh_data, status=200)
    carrier_url = "https://api.parcel.app/external/supported_carriers.json"
    aioclient_mock.get(carrier_url, json={"fedex": "FedEx"}, status=200)

    coordinator = ParcelUpdateCoordinator(hass, mock_entry)
    coordinator.session = async_get_clientsession(hass)

    with patch.object(coordinator._store, "async_load", return_value=cached):
        with patch.object(coordinator._store, "async_save") as mock_save:
            await coordinator.async_config_entry_first_refresh()

            # Should have saved fresh data
            mock_save.assert_called_once()

    assert coordinator.data is not None
    assert coordinator.last_update_success


@pytest.mark.asyncio
async def test_no_cache_fetches_from_api(hass: HomeAssistant, aioclient_mock):
    """Test that with no cache, data is fetched from API."""
    mock_entry = _make_mock_entry()

    api_url = "https://api.parcel.app/external/deliveries/?filter_mode=recent"
    aioclient_mock.get(api_url, json=_load_fixture("recent.json"), status=200)
    carrier_url = "https://api.parcel.app/external/supported_carriers.json"
    aioclient_mock.get(carrier_url, json={"fedex": "FedEx"}, status=200)

    coordinator = ParcelUpdateCoordinator(hass, mock_entry)
    coordinator.session = async_get_clientsession(hass)

    with patch.object(coordinator._store, "async_load", return_value=None):
        with patch.object(coordinator._store, "async_save") as mock_save:
            await coordinator.async_config_entry_first_refresh()

            mock_save.assert_called_once()

    assert coordinator.data is not None
    assert coordinator.data["deliveries"] == _load_fixture("recent.json")["deliveries"]


@pytest.mark.asyncio
async def test_429_with_cache_returns_stale_data(hass: HomeAssistant, aioclient_mock):
    """Test that 429 with cached data returns stale data and stretches interval."""
    mock_entry = _make_mock_entry()

    api_url = "https://api.parcel.app/external/deliveries/?filter_mode=recent"
    # First call succeeds, second returns 429
    aioclient_mock.get(api_url, json=_load_fixture("recent.json"), status=200)
    carrier_url = "https://api.parcel.app/external/supported_carriers.json"
    aioclient_mock.get(carrier_url, json={"fedex": "FedEx"}, status=200)

    coordinator = ParcelUpdateCoordinator(hass, mock_entry)
    coordinator.session = async_get_clientsession(hass)

    with patch.object(coordinator._store, "async_load", return_value=None):
        with patch.object(coordinator._store, "async_save"):
            await coordinator.async_config_entry_first_refresh()

    assert coordinator.last_update_success
    original_data = coordinator.data

    # Now simulate 429 on next refresh
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        api_url,
        status=429,
        headers={"Retry-After": "600"},
    )

    await coordinator.async_refresh()

    # Should still have data (stale) and update should be "successful" (returned data)
    assert coordinator.last_update_success
    assert coordinator.data["deliveries"] == original_data["deliveries"]
    # Interval should be stretched
    assert coordinator.update_interval == timedelta(seconds=600)


@pytest.mark.asyncio
async def test_429_without_cache_fails(hass: HomeAssistant, aioclient_mock):
    """Test that 429 without cached data raises UpdateFailed."""
    mock_entry = _make_mock_entry()

    api_url = "https://api.parcel.app/external/deliveries/?filter_mode=recent"
    aioclient_mock.get(api_url, status=429)
    carrier_url = "https://api.parcel.app/external/supported_carriers.json"
    aioclient_mock.get(carrier_url, json={"fedex": "FedEx"}, status=200)

    coordinator = ParcelUpdateCoordinator(hass, mock_entry)
    coordinator.session = async_get_clientsession(hass)

    with patch.object(coordinator._store, "async_load", return_value=None):
        with patch.object(coordinator._store, "async_save"):
            # First refresh should fail since no cache and 429
            with pytest.raises(Exception):
                await coordinator.async_config_entry_first_refresh()

    assert not coordinator.last_update_success


@pytest.mark.asyncio
async def test_429_default_retry_after(hass: HomeAssistant, aioclient_mock):
    """Test that missing Retry-After header uses default backoff."""
    mock_entry = _make_mock_entry()

    api_url = "https://api.parcel.app/external/deliveries/?filter_mode=recent"
    # First call succeeds
    aioclient_mock.get(api_url, json=_load_fixture("recent.json"), status=200)
    carrier_url = "https://api.parcel.app/external/supported_carriers.json"
    aioclient_mock.get(carrier_url, json={"fedex": "FedEx"}, status=200)

    coordinator = ParcelUpdateCoordinator(hass, mock_entry)
    coordinator.session = async_get_clientsession(hass)

    with patch.object(coordinator._store, "async_load", return_value=None):
        with patch.object(coordinator._store, "async_save"):
            await coordinator.async_config_entry_first_refresh()

    # Now 429 without Retry-After header
    aioclient_mock.clear_requests()
    aioclient_mock.get(api_url, status=429)

    await coordinator.async_refresh()

    assert coordinator.update_interval == timedelta(seconds=DEFAULT_RETRY_AFTER_SECONDS)


@pytest.mark.asyncio
async def test_interval_resets_after_success(hass: HomeAssistant, aioclient_mock):
    """Test that the interval resets to normal after a successful fetch following a 429."""
    mock_entry = _make_mock_entry()

    api_url = "https://api.parcel.app/external/deliveries/?filter_mode=recent"
    aioclient_mock.get(api_url, json=_load_fixture("recent.json"), status=200)
    carrier_url = "https://api.parcel.app/external/supported_carriers.json"
    aioclient_mock.get(carrier_url, json={"fedex": "FedEx"}, status=200)

    coordinator = ParcelUpdateCoordinator(hass, mock_entry)
    coordinator.session = async_get_clientsession(hass)

    with patch.object(coordinator._store, "async_load", return_value=None):
        with patch.object(coordinator._store, "async_save"):
            await coordinator.async_config_entry_first_refresh()

    # Simulate 429
    aioclient_mock.clear_requests()
    aioclient_mock.get(api_url, status=429, headers={"Retry-After": "900"})
    await coordinator.async_refresh()
    assert coordinator.update_interval == timedelta(seconds=900)

    # Now succeed again
    aioclient_mock.clear_requests()
    aioclient_mock.get(api_url, json=_load_fixture("recent.json"), status=200)

    with patch.object(coordinator._store, "async_save"):
        await coordinator.async_refresh()

    assert coordinator.update_interval == timedelta(seconds=UPDATE_INTERVAL_SECONDS)
    assert coordinator.last_update_success


@pytest.mark.asyncio
async def test_carrier_codes_persisted_and_restored(hass: HomeAssistant, aioclient_mock):
    """Test that carrier codes are included in cache and restored on startup."""
    cached = _make_cached_data(age_seconds=60)
    mock_entry = _make_mock_entry()

    api_url = "https://api.parcel.app/external/deliveries/?filter_mode=recent"
    aioclient_mock.get(api_url, json=_load_fixture("recent.json"), status=200)
    carrier_url = "https://api.parcel.app/external/supported_carriers.json"
    aioclient_mock.get(carrier_url, json={"fedex": "FedEx"}, status=200)

    coordinator = ParcelUpdateCoordinator(hass, mock_entry)
    coordinator.session = async_get_clientsession(hass)

    with patch.object(coordinator._store, "async_load", return_value=cached):
        with patch.object(coordinator._store, "async_save"):
            await coordinator.async_config_entry_first_refresh()

    # Carrier codes should be restored from cache
    assert "fedex" in coordinator.carrier_codes["carrier_codes"]
    assert "usps" in coordinator.carrier_codes["carrier_codes"]


@pytest.mark.asyncio
async def test_other_error_with_cache_returns_cached(hass: HomeAssistant, aioclient_mock):
    """Test that non-429 errors return cached data when available."""
    mock_entry = _make_mock_entry()

    api_url = "https://api.parcel.app/external/deliveries/?filter_mode=recent"
    aioclient_mock.get(api_url, json=_load_fixture("recent.json"), status=200)
    carrier_url = "https://api.parcel.app/external/supported_carriers.json"
    aioclient_mock.get(carrier_url, json={"fedex": "FedEx"}, status=200)

    coordinator = ParcelUpdateCoordinator(hass, mock_entry)
    coordinator.session = async_get_clientsession(hass)

    with patch.object(coordinator._store, "async_load", return_value=None):
        with patch.object(coordinator._store, "async_save"):
            await coordinator.async_config_entry_first_refresh()

    original_deliveries = coordinator.data["deliveries"]

    # Now simulate a server error
    aioclient_mock.clear_requests()
    aioclient_mock.get(api_url, status=500)

    await coordinator.async_refresh()

    # Should still have cached data
    assert coordinator.last_update_success
    assert coordinator.data["deliveries"] == original_deliveries
