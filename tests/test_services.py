"""Tests for the add/edit/delete/detect parcel services (issue #38)."""

from urllib.parse import parse_qs

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.parcelapp.const import DOMAIN
from custom_components.parcelapp.services import (
    async_register_services,
    get_http_error_message,
)

ADD_URL = "https://api.parcel.app/external/add-delivery/"
EDIT_URL = "https://web.parcelapp.net/edit-ajax.php"
DELETE_URL = "https://web.parcelapp.net/delete-ajax.php"

UPS_NUMBER = "1Z999AA10123456784"  # detected as UPS with full confidence


@pytest.fixture
async def services(hass):
    """Register the services against a config entry with a device, like a real setup."""
    await async_setup_component(hass, "persistent_notification", {})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "test_api_key", "account_token": "test_account_token"},
    )
    entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
    )
    await async_register_services(hass)
    return {"entry": entry, "device_id": device.id}


async def _call(hass, service, data):
    return await hass.services.async_call(
        DOMAIN, service, data, blocking=True, return_response=True
    )


def _form(request_data):
    """Decode the form body aiohttp sent for an edit/delete call."""
    if isinstance(request_data, dict):
        return request_data
    if isinstance(request_data, bytes):
        request_data = request_data.decode()
    return {k: v[0] for k, v in parse_qs(str(request_data)).items()}


# ---------------------------------------------------------------- add_parcel


async def test_add_parcel_success(hass, aioclient_mock, services):
    aioclient_mock.post(ADD_URL, json={"success": True})

    result = await _call(
        hass,
        "add_parcel",
        {
            "device_id": services["device_id"],
            "parcel_name": "Headphones",
            "tracking_number": "123456789012",
            "courier": "fedex",
            "language": "de",
        },
    )

    assert result == {
        "success": True,
        "parcel_name": "Headphones",
        "tracking_number": "123456789012",
        "carrier": "fedex",
    }
    assert aioclient_mock.call_count == 1
    _method, _url, payload, headers = aioclient_mock.mock_calls[0]
    assert payload == {
        "tracking_number": "123456789012",
        "carrier_code": "fedex",
        "description": "Headphones",
        "send_push_confirmation": False,
        "language": "de",
    }
    assert headers["api-key"] == "test_api_key"


async def test_add_parcel_defaults_language_to_en(hass, aioclient_mock, services):
    aioclient_mock.post(ADD_URL, json={"success": True})

    await _call(
        hass,
        "add_parcel",
        {
            "device_id": services["device_id"],
            "parcel_name": "Book",
            "tracking_number": "123456789012",
            "courier": "fedex",
        },
    )

    assert aioclient_mock.mock_calls[0][2]["language"] == "en"


async def test_add_parcel_auto_detects_carrier(hass, aioclient_mock, services):
    aioclient_mock.post(ADD_URL, json={"success": True})

    result = await _call(
        hass,
        "add_parcel",
        {
            "device_id": services["device_id"],
            "parcel_name": "Shoes",
            "tracking_number": UPS_NUMBER,
        },
    )

    assert result["carrier"] == "ups"
    assert result["carrier_auto_detected"] is True
    assert result["detected_carrier_name"] == "UPS"
    assert aioclient_mock.mock_calls[0][2]["carrier_code"] == "ups"


async def test_add_parcel_undetectable_carrier_does_not_call_api(
    hass, aioclient_mock, services
):
    with pytest.raises(HomeAssistantError, match="Could not auto-detect carrier"):
        await _call(
            hass,
            "add_parcel",
            {
                "device_id": services["device_id"],
                "parcel_name": "Mystery",
                "tracking_number": "ZZZNOTREAL",
            },
        )
    assert aioclient_mock.call_count == 0


async def test_add_parcel_api_reports_failure(hass, aioclient_mock, services):
    aioclient_mock.post(
        ADD_URL, json={"success": False, "error_message": "Duplicate delivery"}
    )

    with pytest.raises(HomeAssistantError, match="Duplicate delivery"):
        await _call(
            hass,
            "add_parcel",
            {
                "device_id": services["device_id"],
                "parcel_name": "Again",
                "tracking_number": "123456789012",
                "courier": "fedex",
            },
        )


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (400, "HTTP 400 - Bad Request"),
        (401, "API key may be invalid"),
        (429, "Rate limit exceeded"),
        (503, "server error"),
    ],
)
async def test_add_parcel_http_errors(hass, aioclient_mock, services, status, message):
    aioclient_mock.post(ADD_URL, status=status)

    with pytest.raises(HomeAssistantError, match=message):
        await _call(
            hass,
            "add_parcel",
            {
                "device_id": services["device_id"],
                "parcel_name": "Lamp",
                "tracking_number": "123456789012",
                "courier": "fedex",
            },
        )


async def test_add_parcel_unknown_device(hass, aioclient_mock, services):
    with pytest.raises(HomeAssistantError, match="Config entry not found"):
        await _call(
            hass,
            "add_parcel",
            {
                "device_id": "not-a-device",
                "parcel_name": "Lamp",
                "tracking_number": "123456789012",
                "courier": "fedex",
            },
        )
    assert aioclient_mock.call_count == 0


async def test_add_parcel_missing_api_key(hass, aioclient_mock, services):
    hass.config_entries.async_update_entry(
        services["entry"], data={"api_key": "", "account_token": "t"}
    )

    with pytest.raises(HomeAssistantError, match="API key not configured"):
        await _call(
            hass,
            "add_parcel",
            {
                "device_id": services["device_id"],
                "parcel_name": "Lamp",
                "tracking_number": "123456789012",
                "courier": "fedex",
            },
        )
    assert aioclient_mock.call_count == 0


# ------------------------------------------------------------- delete_parcel


async def test_delete_parcel_success(hass, aioclient_mock, services):
    aioclient_mock.post(DELETE_URL, text="OK")

    result = await _call(
        hass,
        "delete_parcel",
        {
            "device_id": services["device_id"],
            "tracking_number": "123456789012",
            "type": "fedex",
        },
    )

    assert result == {"success": True, "tracking_number": "123456789012", "type": "fedex"}
    _method, _url, data, headers = aioclient_mock.mock_calls[0]
    assert _form(data) == {"number": "123456789012", "type": "fedex"}
    assert headers["Cookie"] == "account_token=test_account_token"


async def test_delete_parcel_error_response(hass, aioclient_mock, services):
    aioclient_mock.post(DELETE_URL, text=" Error\n")

    with pytest.raises(HomeAssistantError, match="Failed to delete parcel"):
        await _call(
            hass,
            "delete_parcel",
            {
                "device_id": services["device_id"],
                "tracking_number": "123456789012",
                "type": "fedex",
            },
        )


async def test_delete_parcel_not_found(hass, aioclient_mock, services):
    aioclient_mock.post(DELETE_URL, status=404)

    with pytest.raises(HomeAssistantError, match="may have already been deleted"):
        await _call(
            hass,
            "delete_parcel",
            {
                "device_id": services["device_id"],
                "tracking_number": "123456789012",
                "type": "fedex",
            },
        )


async def test_delete_parcel_requires_account_token(hass, aioclient_mock, services):
    hass.config_entries.async_update_entry(
        services["entry"], data={"api_key": "test_api_key"}
    )

    with pytest.raises(HomeAssistantError, match="Account token not configured"):
        await _call(
            hass,
            "delete_parcel",
            {
                "device_id": services["device_id"],
                "tracking_number": "123456789012",
                "type": "fedex",
            },
        )
    assert aioclient_mock.call_count == 0


# --------------------------------------------------------------- edit_parcel


async def test_edit_parcel_success(hass, aioclient_mock, services):
    aioclient_mock.post(EDIT_URL, text="OK")

    result = await _call(
        hass,
        "edit_parcel",
        {
            "device_id": services["device_id"],
            "parcel_name": "Renamed",
            "tracking_number": UPS_NUMBER,
            "oldNumber": "123456789012",
            "oldType": "fedex",
        },
    )

    assert result["success"] is True
    assert result["carrier"] == "ups"
    assert result["carrier_auto_detected"] is True
    assert result["old_tracking_number"] == "123456789012"
    assert result["old_carrier"] == "fedex"
    _method, _url, data, headers = aioclient_mock.mock_calls[0]
    assert _form(data) == {
        "name": "Renamed",
        "number": UPS_NUMBER,
        "carrier": "ups",
        "oldNumber": "123456789012",
        "oldType": "fedex",
    }
    assert headers["Cookie"] == "account_token=test_account_token"


async def test_edit_parcel_error_response(hass, aioclient_mock, services):
    aioclient_mock.post(EDIT_URL, text="error")

    with pytest.raises(HomeAssistantError, match="Failed to edit parcel 'Renamed'"):
        await _call(
            hass,
            "edit_parcel",
            {
                "device_id": services["device_id"],
                "parcel_name": "Renamed",
                "tracking_number": "123456789012",
                "courier": "fedex",
                "oldNumber": "123456789012",
                "oldType": "fedex",
            },
        )


async def test_edit_parcel_auth_failure(hass, aioclient_mock, services):
    aioclient_mock.post(EDIT_URL, status=403)

    with pytest.raises(HomeAssistantError, match="account token may be invalid"):
        await _call(
            hass,
            "edit_parcel",
            {
                "device_id": services["device_id"],
                "parcel_name": "Renamed",
                "tracking_number": "123456789012",
                "courier": "fedex",
                "oldNumber": "123456789012",
                "oldType": "fedex",
            },
        )


# ------------------------------------------------------------ detect_carrier


async def test_detect_carrier(hass, services):
    result = await _call(hass, "detect_carrier", {"tracking_number": UPS_NUMBER})

    assert result["tracking_number"] == UPS_NUMBER
    assert result["best_match"] == "ups"
    assert result["matches"][0]["carrier_name"] == "UPS"


async def test_detect_carrier_no_match(hass, services):
    result = await _call(hass, "detect_carrier", {"tracking_number": "ZZZNOTREAL"})

    assert result == {"tracking_number": "ZZZNOTREAL", "matches": [], "best_match": None}


# ---------------------------------------------------- get_http_error_message


def test_http_error_message_unexpected_status():
    message = get_http_error_message(418, "add")
    assert "HTTP 418" in message
