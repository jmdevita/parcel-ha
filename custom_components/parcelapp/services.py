"""The ParcelApp Services."""

import inspect
import json
import logging

from aiohttp import ClientResponseError
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .carrier_detection import CarrierDetector
from .const import (
    CARRIER_CODE_ENDPOINT,
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
        vol.Optional(COURIER): cv.string,
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
        vol.Optional(COURIER): cv.string,
        vol.Required(OLD_NUMBER): cv.string,
        vol.Required(OLD_TYPE): cv.string,
    }
)

DETECT_CARRIER_SCHEMA = vol.Schema(
    {
        vol.Required(TRACKING_NUMBER): cv.string,
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


async def async_create_notification(
    hass: HomeAssistant,
    title: str,
    message: str,
    notification_id: str,
) -> None:
    """Create a persistent notification in Home Assistant."""
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "title": title,
            "message": message,
            "notification_id": notification_id,
        },
    )


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
            "The Parcel App API allows 20 requests per hour. Please try again later."
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


def _resolve_courier(
    detector: CarrierDetector, tracking_number: str, courier: str | None
) -> tuple[str, dict | None]:
    """Resolve the courier code, auto-detecting if not provided.

    Returns (courier_code, detection_info_dict_or_None).
    Raises HomeAssistantError if auto-detection fails.
    """
    if courier:
        return courier, None

    matches = detector.detect(tracking_number)
    if not matches:
        raise HomeAssistantError(
            f"Could not auto-detect carrier for tracking number '{tracking_number}'. "
            f"Please provide the 'courier' field manually. "
            f"See {CARRIER_CODE_ENDPOINT} for supported carrier codes."
        )

    # Filter to matches that have a Parcel app mapping
    mapped = [m for m in matches if m.parcel_app_code is not None]
    if not mapped:
        names = ", ".join(m.carrier_name for m in matches)
        raise HomeAssistantError(
            f"Detected carrier(s) [{names}] but none map to a supported Parcel app code. "
            f"Please provide the 'courier' field manually."
        )

    high_confidence = [m for m in mapped if m.confidence >= 0.8]

    # Deduplicate by parcel_app_code — multiple formats from the same
    # carrier (e.g. USPS 22 and USPS 91) should not trigger disambiguation.
    unique_codes = {m.parcel_app_code for m in high_confidence}

    if len(unique_codes) <= 1 and high_confidence:
        best = high_confidence[0]
    elif len(unique_codes) > 1:
        # Show only one entry per distinct carrier
        seen = set()
        options_parts = []
        for m in high_confidence:
            if m.parcel_app_code not in seen:
                seen.add(m.parcel_app_code)
                options_parts.append(f"{m.parcel_app_code} ({m.carrier_name})")
        options = ", ".join(options_parts)
        raise HomeAssistantError(
            f"Multiple carriers match tracking number '{tracking_number}': {options}. "
            f"Please provide the 'courier' field to disambiguate."
        )
    else:
        best = mapped[0]
        _LOGGER.warning(
            "Low confidence carrier detection for %s: %s (%.0f%%)",
            tracking_number,
            best.parcel_app_code,
            best.confidence * 100,
        )

    detection_info = {
        "carrier_auto_detected": True,
        "detected_carrier_name": best.carrier_name,
        "detected_format": best.format_name,
    }
    return best.parcel_app_code, detection_info


async def async_register_services(hass: HomeAssistant):
    """Register ParcelApp services."""

    session = async_get_clientsession(hass)
    detector = CarrierDetector()
    detector.load()

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
        courier, detection_info = _resolve_courier(
            detector, tracking_number, call.data.get(COURIER)
        )
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

                    # Create success notification
                    await async_create_notification(
                        hass,
                        title="Parcel Added Successfully",
                        message=f"Successfully added parcel '{parcel_name}' with tracking number {tracking_number}",
                        notification_id=f"parcelapp_add_{tracking_number}",
                    )

                    result = {
                        "success": True,
                        "parcel_name": parcel_name,
                        "tracking_number": tracking_number,
                        "carrier": courier,
                    }
                    if detection_info:
                        result.update(detection_info)
                    return result
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

                # Create success notification
                await async_create_notification(
                    hass,
                    title="Parcel Deleted Successfully",
                    message=f"Successfully deleted parcel with tracking number {tracking_number}",
                    notification_id=f"parcelapp_delete_{tracking_number}",
                )

                return {
                    "success": True,
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
        courier, detection_info = _resolve_courier(
            detector, tracking_number, call.data.get(COURIER)
        )
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

                # Create success notification
                await async_create_notification(
                    hass,
                    title="Parcel Edited Successfully",
                    message=f"Successfully edited parcel '{parcel_name}' with tracking number {tracking_number}",
                    notification_id=f"parcelapp_edit_{tracking_number}",
                )

                result = {
                    "success": True,
                    "parcel_name": parcel_name,
                    "tracking_number": tracking_number,
                    "carrier": courier,
                    "old_tracking_number": old_number,
                    "old_carrier": old_type,
                }
                if detection_info:
                    result.update(detection_info)
                return result

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

    async def async_detect_carrier(call: ServiceCall):
        """Detect carrier from a tracking number."""
        tracking_number = str(call.data[TRACKING_NUMBER])
        matches = detector.detect(tracking_number)
        return {
            "tracking_number": tracking_number,
            "matches": [
                {
                    "carrier_code": m.parcel_app_code or m.courier_code,
                    "carrier_name": m.carrier_name,
                    "format": m.format_name,
                    "confidence": m.confidence,
                    "checksum_valid": m.checksum_valid,
                }
                for m in matches
            ],
            "best_match": matches[0].parcel_app_code if matches else None,
        }

    # description_placeholders was added in HA 2025.12
    _supports_placeholders = "description_placeholders" in inspect.signature(
        hass.services.async_register
    ).parameters

    placeholders_kwargs: dict = {}
    if _supports_placeholders:
        placeholders_kwargs["description_placeholders"] = {
            "supported_carriers_url": CARRIER_CODE_ENDPOINT,
        }

    hass.services.async_register(
        DOMAIN,
        "add_parcel",
        async_add_parcel,
        schema=ADD_PARCEL_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
        **placeholders_kwargs,
    )

    hass.services.async_register(
        DOMAIN,
        "delete_parcel",
        async_delete_parcel,
        schema=DELETE_PARCEL_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
        **placeholders_kwargs,
    )

    hass.services.async_register(
        DOMAIN,
        "edit_parcel",
        async_edit_parcel,
        schema=EDIT_PARCEL_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
        **placeholders_kwargs,
    )

    hass.services.async_register(
        DOMAIN,
        "detect_carrier",
        async_detect_carrier,
        schema=DETECT_CARRIER_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
