"""Test sensor for simple integration."""

import pytest
from unittest.mock import AsyncMock
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

    # Initialize the coordinator
    coordinator = ParcelUpdateCoordinator(hass, mock_entry)
    coordinator.api_key = "test_api_key"  # Ensure the API key is set
    coordinator.session = async_get_clientsession(hass)

    # Perform the update
    await coordinator.async_refresh()

    # Assert the data was fetched correctly
    assert coordinator.last_update_success
    assert coordinator.data['deliveries'] == recent_deliveries['deliveries'] # This is only looking at delivery data, not extra parcel info