"""Test that add_parcel forwards the optional postcode and email to the API."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.parcelapp.const import DOMAIN
from custom_components.parcelapp.services import async_register_services

ADD_URL = "https://api.parcel.app/external/add-delivery/"


async def _call_add(hass, aioclient_mock, **extra):
    aioclient_mock.post(ADD_URL, json={"success": True}, status=200)
    entry = Mock()
    entry.data = {"api_key": "test_api_key"}
    with patch(
        "custom_components.parcelapp.services.async_get_config_entry_from_device_id",
        AsyncMock(return_value=entry),
    ), patch(
        "custom_components.parcelapp.services.async_create_notification",
        AsyncMock(),
    ):
        await async_register_services(hass)
        result = await hass.services.async_call(
            DOMAIN,
            "add_parcel",
            {
                "device_id": "abc",
                "parcel_name": "Shoes",
                "tracking_number": "01234567890123",
                "courier": "dpdpcode",
                **extra,
            },
            blocking=True,
            return_response=True,
        )
    assert result["success"] is True
    _method, _url, payload, _headers = aioclient_mock.mock_calls[-1]
    return payload


@pytest.mark.asyncio
async def test_add_parcel_sends_postcode_and_email(hass, aioclient_mock):
    """Postcode and email end up in the request body, trimmed."""
    payload = await _call_add(
        hass, aioclient_mock, postcode=" 10115 ", email="me@example.com"
    )
    assert payload["carrier_code"] == "dpdpcode"
    assert payload["postcode"] == "10115"
    assert payload["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_add_parcel_without_extra_fields(hass, aioclient_mock):
    """Without postcode or email the request body stays as before."""
    payload = await _call_add(hass, aioclient_mock)
    assert "postcode" not in payload
    assert "email" not in payload
