"""Test that add_parcel passes the API's error message on."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.exceptions import HomeAssistantError

from custom_components.parcelapp.const import DOMAIN
from custom_components.parcelapp.services import async_register_services

ADD_URL = "https://api.parcel.app/external/add-delivery/"


async def _call_add(hass):
    entry = Mock()
    entry.data = {"api_key": "test_api_key"}
    with patch(
        "custom_components.parcelapp.services.async_get_config_entry_from_device_id",
        AsyncMock(return_value=entry),
    ):
        await async_register_services(hass)
        await hass.services.async_call(
            DOMAIN,
            "add_parcel",
            {
                "device_id": "abc",
                "parcel_name": "Shoes",
                "tracking_number": "11750118044170",
                "courier": "gls",
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.asyncio
async def test_add_parcel_shows_api_error_message(hass, aioclient_mock):
    """A 400 with an error_message shows that message."""
    aioclient_mock.post(
        ADD_URL,
        json={"success": False, "error_message": "Invalid tracking number format."},
        status=400,
    )
    with pytest.raises(HomeAssistantError, match="Invalid tracking number format."):
        await _call_add(hass)


@pytest.mark.asyncio
async def test_add_parcel_without_api_error_message(hass, aioclient_mock):
    """A 400 without a readable body keeps the generic message."""
    aioclient_mock.post(ADD_URL, text="Bad Request", status=400)
    with pytest.raises(HomeAssistantError, match="HTTP 400"):
        await _call_add(hass)
