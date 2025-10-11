"""The ParcelApp Services."""

import json
import logging

from aiohttp import ClientResponseError
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    COURIER,
    DOMAIN,
    OLD_NUMBER,
    OLD_TYPE,
    PARCEL_NAME,
    TRACKING_NUMBER,
    TYPE,
)

_LOGGER = logging.getLogger(__name__)

ADD_PARCEL_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Required(PARCEL_NAME): cv.string,
        vol.Required(TRACKING_NUMBER): cv.string,
        vol.Required(COURIER): cv.string,
        vol.Required("send_push_confirmation", default=False): cv.boolean,
    }
)

DELETE_PARCEL_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Required(TRACKING_NUMBER): cv.string,
        vol.Required(TYPE): cv.string,
    }
)

EDIT_PARCEL_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Required(PARCEL_NAME): cv.string,
        vol.Required(TRACKING_NUMBER): cv.string,
        vol.Required(COURIER): cv.string,
        vol.Required(OLD_NUMBER): cv.string,
        vol.Required(OLD_TYPE): cv.string,
    }
)


async def async_get_config_entry_from_device_id(hass: HomeAssistant, device_id: str):
    """Get the config entry from a device ID."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if not device:
        _LOGGER.error("Device not found: %s", device_id)
        return None

    for entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry and entry.domain == DOMAIN:
            return entry
    return None


def get_http_error_message(
    status_code: int,
    operation: str,
    auth_type: str = "api_key",
    parcel_name: str | None = None,
    tracking_number: str | None = None,
    carrier: str | None = None,
) -> str:
    """Generate user-friendly error messages based on HTTP status codes."""

    auth_credential = "API key" if auth_type == "api_key" else "account token"

    # Build context string for the error message
    context = ""
    if parcel_name and tracking_number:
        context = f"'{parcel_name}' (tracking: {tracking_number})"
    elif tracking_number:
        context = f"(tracking: {tracking_number})"

    if status_code == 400:
        if operation == "add":
            return (
                f"Failed to add parcel {context}. "
                f"The Parcel App API rejected the request (HTTP 400 - Bad Request).\n"
                f"Please verify the tracking number and carrier code are correct."
            )
        if operation == "delete":
            return (
                f"Failed to delete parcel {context}. "
                f"Bad request (HTTP 400). Please verify the tracking number and type are correct."
            )

        return (
            f"Failed to edit parcel {context}. "
            f"Bad request (HTTP 400). Please verify the tracking number and carrier code are correct."
        )

    if status_code in {401, 403}:
        return (
            f"Authentication failed (HTTP {status_code}). "
            f"Your {auth_credential} may be invalid or expired. Please reconfigure the integration."
        )

    if status_code == 404:
        if operation == "delete":
            return (
                f"Parcel not found (HTTP 404). "
                f"The parcel with tracking number '{tracking_number}' may have already been deleted."
            )
        if operation == "edit":
            return (
                "Parcel not found (HTTP 404). "
                "The original parcel may not exist or has already been modified."
            )
        return "Resource not found (HTTP 404)."

    if status_code == 429:
        return (
            "Rate limit exceeded (HTTP 429). "
            "The Parcel App API allows 20 requests per day. Please try again later."
        )

    if status_code >= 500:
        return (
            f"Parcel App server error (HTTP {status_code}). "
            f"The service may be temporarily unavailable. Please try again later."
        )

    return (
        f"Failed to communicate with Parcel App API (HTTP {status_code}). "
        f"Please check your internet connection and try again."
    )


async def async_register_services(hass: HomeAssistant):
    """Register ParcelApp services."""

    session = async_get_clientsession(hass)

    async def async_add_parcel(call: ServiceCall):
        """Add a parcel to ParcelApp using the official API."""
        device_id = call.data["device_id"]
        config_entry = await async_get_config_entry_from_device_id(hass, device_id)
        if not config_entry:
            _LOGGER.error("Config entry not found for device: %s", device_id)
            raise HomeAssistantError("Config entry not found for device")

        api_key = config_entry.data.get("api_key", "")
        if not api_key:
            _LOGGER.error("API key not found for device: %s", device_id)
            raise HomeAssistantError(
                "API key not configured. Please reconfigure the integration with your API key."
            )

        parcel_name = call.data[PARCEL_NAME]
        tracking_number = str(call.data[TRACKING_NUMBER])
        courier = call.data[COURIER]
        send_push = call.data.get("send_push_confirmation", False)

        # Prepare the payload for the official API
        payload = {
            "tracking_number": tracking_number,
            "carrier_code": courier,
            "description": parcel_name,
            "send_push_confirmation": send_push,
        }
        headers = {
            "api-key": api_key,
            "Content-Type": "application/json",
        }

        try:
            # Official API Call for Adding Parcel
            async with session.post(
                "https://api.parcel.app/external/add-delivery/",
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                result = await response.json()

                if result.get("success"):
                    _LOGGER.info(
                        "Successfully added parcel: %s (tracking: %s, carrier: %s)",
                        parcel_name,
                        tracking_number,
                        courier,
                    )
                    return {
                        "success": True,
                        "message": f"Successfully added parcel '{parcel_name}'",
                        "parcel_name": parcel_name,
                        "tracking_number": tracking_number,
                        "carrier": courier,
                    }
                else:
                    error_msg = result.get("error_message", "Unknown error")
                    _LOGGER.error(
                        "Failed to add parcel: %s (tracking: %s, carrier: %s). Error: %s",
                        parcel_name,
                        tracking_number,
                        courier,
                        error_msg,
                    )
                    raise HomeAssistantError(
                        f"Failed to add parcel '{parcel_name}' (tracking: {tracking_number}). "
                        f"The Parcel App API returned an error: {error_msg}"
                    )

        except HomeAssistantError:
            raise
        except ClientResponseError as err:
            _LOGGER.error(
                "API call failed with status %s: %s. Parcel: %s, Tracking: %s, Carrier: %s",
                err.status,
                err.message,
                parcel_name,
                tracking_number,
                courier,
            )
            error_msg = get_http_error_message(
                status_code=err.status,
                operation="add",
                auth_type="api_key",
                parcel_name=parcel_name,
                tracking_number=tracking_number,
                carrier=courier,
            )
            raise HomeAssistantError(error_msg) from err
        except json.JSONDecodeError as err:
            _LOGGER.error("Failed to parse API response: %s", err)
            raise HomeAssistantError("Received invalid response from Parcel App API") from err
        except Exception as err:
            _LOGGER.error(
                "Unexpected error during API call: %s. Parcel: %s, Tracking: %s, Carrier: %s",
                err,
                parcel_name,
                tracking_number,
                courier,
            )
            raise HomeAssistantError(f"Unexpected error: {err}") from err

    async def async_delete_parcel(call: ServiceCall):
        """Delete a parcel from ParcelApp (using workaround API)."""
        tracking_number = str(call.data[TRACKING_NUMBER])
        parcel_type = call.data[TYPE]

        # Retrieve the account_token from the config entry
        config_entries_list = hass.config_entries.async_entries(DOMAIN)
        if not config_entries_list:
            _LOGGER.error("No config entry found for parcelapp domain")
            raise HomeAssistantError("No config entry found")

        config_entry = config_entries_list[0]
        account_token = config_entry.data.get("account_token", "")

        if not account_token:
            _LOGGER.error(
                "Account token not configured. Delete service requires account_token"
            )
            raise HomeAssistantError(
                "Account token not configured. Please reconfigure the integration."
            )

        # Prepare the payload for the API call
        payload = {
            "number": tracking_number,
            "type": parcel_type,
        }
        headers = {
            "User-Agent": "Home Assistant",
            "Content-Type": "application/x-www-form-urlencoded",
            "Cookie": f"account_token={account_token}",
        }

        try:
            # API Call for Deleting Parcel (BETA )
            async with session.post(
                "https://web.parcelapp.net/delete-ajax.php",
                headers=headers,
                data=payload,
            ) as response:
                response.raise_for_status()
                result = await response.text()
                _LOGGER.info("Parcel Delete Response: %s", result)

                # Check if the response indicates an error
                if result.strip().upper() == "ERROR":
                    _LOGGER.error(
                        "Failed to delete parcel. Tracking: %s, Type: %s",
                        tracking_number,
                        parcel_type,
                    )
                    raise HomeAssistantError(
                        f"Failed to delete parcel (tracking: {tracking_number})"
                    )

                _LOGGER.info(
                    "Successfully deleted parcel. Tracking: %s, Type: %s",
                    tracking_number,
                    parcel_type,
                )

                return {
                    "success": True,
                    "message": "Successfully deleted parcel",
                    "tracking_number": tracking_number,
                    "type": parcel_type,
                }

        except HomeAssistantError:
            raise
        except ClientResponseError as err:
            _LOGGER.error(
                "API call failed with status %s: %s. Tracking: %s, Type: %s",
                err.status,
                err.message,
                tracking_number,
                parcel_type,
            )
            error_msg = get_http_error_message(
                status_code=err.status,
                operation="delete",
                auth_type="account_token",
                tracking_number=tracking_number,
            )
            raise HomeAssistantError(error_msg) from err
        except Exception as err:
            _LOGGER.error(
                "Unexpected error during API call: %s. Tracking: %s, Type: %s",
                err,
                tracking_number,
                parcel_type,
            )
            raise HomeAssistantError(f"Unexpected error: {err}") from err

    async def async_edit_parcel(call: ServiceCall):
        """Edit a parcel in ParcelApp (BETA)."""
        parcel_name = call.data[PARCEL_NAME]
        tracking_number = str(call.data[TRACKING_NUMBER])
        courier = call.data[COURIER]
        old_number = str(call.data[OLD_NUMBER])
        old_type = call.data[OLD_TYPE]

        # Retrieve the account_token from the config entry
        config_entries_list = hass.config_entries.async_entries(DOMAIN)
        if not config_entries_list:
            _LOGGER.error("No config entry found for parcelapp domain")
            raise HomeAssistantError("No config entry found")

        config_entry = config_entries_list[0]
        account_token = config_entry.data.get("account_token", "")

        if not account_token:
            _LOGGER.error(
                "Account token not configured. Edit service requires account_token"
            )
            raise HomeAssistantError(
                "Account token not configured. Please reconfigure the integration."
            )

        # Prepare the payload for the API call
        payload = {
            "name": parcel_name,
            "number": tracking_number,
            "carrier": courier,
            "oldNumber": old_number,
            "oldType": old_type,
        }
        headers = {
            "User-Agent": "Home Assistant",
            "Content-Type": "application/x-www-form-urlencoded",
            "Cookie": f"account_token={account_token}",
        }

        try:
            # API Call for Editing Parcel (BETA)
            async with session.post(
                "https://web.parcelapp.net/edit-ajax.php", headers=headers, data=payload
            ) as response:
                response.raise_for_status()
                result = await response.text()
                _LOGGER.info("Parcel Edit Response: %s", result)

                # Check if the response indicates an error
                if result.strip().upper() == "ERROR":
                    _LOGGER.error(
                        "Failed to edit parcel: %s. Tracking: %s, Carrier: %s",
                        parcel_name,
                        tracking_number,
                        courier,
                    )
                    raise HomeAssistantError(
                        f"Failed to edit parcel '{parcel_name}' (tracking: {tracking_number})"
                    )

                _LOGGER.info(
                    "Successfully edited parcel: %s. Tracking: %s, Carrier: %s",
                    parcel_name,
                    tracking_number,
                    courier,
                )

                return {
                    "success": True,
                    "message": f"Successfully edited parcel '{parcel_name}'",
                    "parcel_name": parcel_name,
                    "tracking_number": tracking_number,
                    "carrier": courier,
                    "old_tracking_number": old_number,
                    "old_carrier": old_type,
                }

        except HomeAssistantError:
            raise
        except ClientResponseError as err:
            _LOGGER.error(
                "API call failed with status %s: %s. Parcel: %s, Tracking: %s",
                err.status,
                err.message,
                parcel_name,
                tracking_number,
            )
            error_msg = get_http_error_message(
                status_code=err.status,
                operation="edit",
                auth_type="account_token",
                parcel_name=parcel_name,
                tracking_number=tracking_number,
                carrier=courier,
            )
            raise HomeAssistantError(error_msg) from err
        except Exception as err:
            _LOGGER.error(
                "Unexpected error during API call: %s. Parcel: %s, Tracking: %s",
                err,
                parcel_name,
                tracking_number,
            )
            raise HomeAssistantError(f"Unexpected error: {err}") from err

    hass.services.async_register(
        DOMAIN,
        "add_parcel",
        async_add_parcel,
        schema=ADD_PARCEL_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    hass.services.async_register(
        DOMAIN,
        "delete_parcel",
        async_delete_parcel,
        schema=DELETE_PARCEL_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    hass.services.async_register(
        DOMAIN,
        "edit_parcel",
        async_edit_parcel,
        schema=EDIT_PARCEL_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
