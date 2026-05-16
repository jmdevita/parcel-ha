"""Test sensor for simple integration."""

import pytest
from unittest.mock import AsyncMock, Mock
from pathlib import Path
import json
from datetime import datetime
from custom_components.parcelapp.coordinator import ParcelUpdateCoordinator

from homeassistant.setup import async_setup_component
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from custom_components.parcelapp.const import DOMAIN


async def test_async_setup(hass):
    """Test the component gets setup."""
    assert await async_setup_component(hass, DOMAIN, {}) is True


@pytest.mark.asyncio
async def test_parcel_update_coordinator(hass, aioclient_mock):
    """Test the ParcelUpdateCoordinator with mocked API responses."""
    fixtures_path = Path(__file__).parent / "fixtures"
    with open(fixtures_path / "recent.json") as file:
        recent_deliveries = json.load(file)
    recent_deliveries['carrer_codes']  = {'pholder': 'Placeholder', 'none': 'None'}
    # Mock the carrier codes endpoint
    carrier_codes_url = "https://api.parcel.app/external/supported_carriers.json"
    aioclient_mock.get(
        carrier_codes_url,
        json={'fedex': 'Fedex', 'usps': 'USPS'},
        status=200,
    )
    # Mock the API endpoint for a successful response
    mock_api_url = "https://api.parcel.app/external/deliveries/?filter_mode=recent"
    aioclient_mock.get(
        mock_api_url,
        json=recent_deliveries,
        status=200,
    )

    # Mock ConfigEntry
    mock_entry = AsyncMock()
    mock_entry.data = {"api_key": "test_api_key"}
    mock_entry.options = {}
    mock_entry.entry_id = "test_entry_coord"
    mock_entry.async_on_unload = Mock()

    # Initialize the coordinator
    coordinator = ParcelUpdateCoordinator(hass, mock_entry)
    coordinator.api_key = "test_api_key"  # Ensure the API key is set
    coordinator.session = async_get_clientsession(hass)

    # Perform the update
    await coordinator.async_refresh()

    # Assert the data was fetched correctly
    assert coordinator.last_update_success
    assert coordinator.data['deliveries'] == recent_deliveries['deliveries'] # This is only looking at delivery data, not extra parcel info


@pytest.mark.asyncio
async def test_exponential_backoff_on_consecutive_429s(hass, aioclient_mock):
    """Consecutive 429s should double the backoff, reset on success."""
    from datetime import timedelta
    fixtures_path = Path(__file__).parent / "fixtures"
    with open(fixtures_path / "recent.json") as file:
        recent_deliveries = json.load(file)

    carrier_codes_url = "https://api.parcel.app/external/supported_carriers.json"
    mock_api_url = "https://api.parcel.app/external/deliveries/?filter_mode=recent"

    mock_entry = AsyncMock()
    mock_entry.data = {"api_key": "test_api_key"}
    mock_entry.options = {"update_interval": 600}
    mock_entry.entry_id = "test_entry_backoff"
    mock_entry.async_on_unload = Mock()

    coordinator = ParcelUpdateCoordinator(hass, mock_entry)
    coordinator.api_key = "test_api_key"
    coordinator.session = async_get_clientsession(hass)
    coordinator._cached_data = recent_deliveries

    aioclient_mock.get(carrier_codes_url, json={"fedex": "Fedex"}, status=200)
    aioclient_mock.get(mock_api_url, status=429)

    # 1st 429: 300 * 1 = 300, floored at configured 600
    await coordinator.async_refresh()
    assert coordinator._consecutive_429s == 1
    assert coordinator.update_interval == timedelta(seconds=600)

    # 2nd 429: 300 * 2 = 600
    await coordinator.async_refresh()
    assert coordinator._consecutive_429s == 2
    assert coordinator.update_interval == timedelta(seconds=600)

    # 3rd 429: 300 * 4 = 1200
    await coordinator.async_refresh()
    assert coordinator._consecutive_429s == 3
    assert coordinator.update_interval == timedelta(seconds=1200)

    # 4th 429: 300 * 8 = 2400
    await coordinator.async_refresh()
    assert coordinator._consecutive_429s == 4
    assert coordinator.update_interval == timedelta(seconds=2400)

    # Success resets the counter
    aioclient_mock.clear_requests()
    aioclient_mock.get(carrier_codes_url, json={"fedex": "Fedex"}, status=200)
    aioclient_mock.get(mock_api_url, json=recent_deliveries, status=200)
    await coordinator.async_refresh()
    assert coordinator._consecutive_429s == 0


@pytest.mark.asyncio
async def test_backoff_capped_at_max(hass, aioclient_mock):
    """Backoff should not exceed MAX_BACKOFF_SECONDS."""
    from datetime import timedelta
    from custom_components.parcelapp.const import MAX_BACKOFF_SECONDS

    fixtures_path = Path(__file__).parent / "fixtures"
    with open(fixtures_path / "recent.json") as file:
        recent_deliveries = json.load(file)

    carrier_codes_url = "https://api.parcel.app/external/supported_carriers.json"
    mock_api_url = "https://api.parcel.app/external/deliveries/?filter_mode=recent"

    mock_entry = AsyncMock()
    mock_entry.data = {"api_key": "test_api_key"}
    mock_entry.options = {"update_interval": 300}
    mock_entry.entry_id = "test_entry_cap"
    mock_entry.async_on_unload = Mock()

    coordinator = ParcelUpdateCoordinator(hass, mock_entry)
    coordinator.api_key = "test_api_key"
    coordinator.session = async_get_clientsession(hass)
    coordinator._cached_data = recent_deliveries
    coordinator._consecutive_429s = 9

    aioclient_mock.get(carrier_codes_url, json={"fedex": "Fedex"}, status=200)
    aioclient_mock.get(mock_api_url, status=429)
    await coordinator.async_refresh()
    assert coordinator.update_interval == timedelta(seconds=MAX_BACKOFF_SECONDS)