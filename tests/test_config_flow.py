"""Tests for the config flow API key validation."""

from unittest.mock import patch

import aiohttp
import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.parcelapp.const import DOMAIN, PARCEL_URL

USER_INPUT = {"api_key": "test_api_key", "account_token": ""}


@pytest.fixture(autouse=True)
def skip_setup():
    """Don't set up the integration when the flow creates an entry."""
    with patch("custom_components.parcelapp.async_setup_entry", return_value=True):
        yield


async def _submit(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )


@pytest.mark.asyncio
async def test_valid_api_key_creates_entry(hass: HomeAssistant, aioclient_mock) -> None:
    """A 200 from the API creates the entry and sends the api-key header."""
    aioclient_mock.get(PARCEL_URL, status=200, json={"success": True})

    result = await _submit(hass)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"api_key": "test_api_key", "account_token": ""}
    assert aioclient_mock.mock_calls[0][3]["api-key"] == "test_api_key"


@pytest.mark.asyncio
async def test_invalid_api_key_shows_error(hass: HomeAssistant, aioclient_mock) -> None:
    """A non-200 from the API re-shows the form with an error."""
    aioclient_mock.get(PARCEL_URL, status=401)

    result = await _submit(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "Invalid API Key"}


@pytest.mark.asyncio
async def test_connection_error_shows_error(hass: HomeAssistant, aioclient_mock) -> None:
    """A client error re-shows the form with a connection error."""
    aioclient_mock.get(PARCEL_URL, exc=aiohttp.ClientError())

    result = await _submit(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "Could not connect to the API"}
