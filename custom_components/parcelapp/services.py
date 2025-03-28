"""The ParcelApp Services."""

import logging

from aiohttp import ClientResponseError
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import COURIER, DOMAIN, PARCEL_NAME, TRACKING_NUMBER

_LOGGER = logging.getLogger(__name__)

ADD_PARCEL_SCHEMA = vol.Schema(
    {
        vol.Required(PARCEL_NAME): cv.string,
        vol.Required(TRACKING_NUMBER): cv.string,
        vol.Required(COURIER): cv.string,
    }
)


async def async_register_services(hass: HomeAssistant):
    """Register ParcelApp services."""

    session = async_get_clientsession(hass)

    async def async_add_parcel(call: ServiceCall):
        """Add a parcel to ParcelApp."""
        parcel_name = call.data[PARCEL_NAME]
        tracking_number = call.data[TRACKING_NUMBER]
        courier = call.data[COURIER]

        # Retrieve the account_token from the config entry
        config_entry = hass.config_entries.async_entries(DOMAIN)[0]
        account_token = config_entry.data.get("account_token", "")

        # Prepare the payload for the API call
        payload = {
            "name": parcel_name,
            "number": tracking_number,
            "courier": courier,
        }
        headers = {
            "User-Agent": "Home Assistant",
            "Content-Type": "application/x-www-form-urlencoded",
            "Cookie": f"account_token={account_token}",
        }
        try:
            # API Call for Adding Parcel
            async with session.post(
                "https://web.parcelapp.net/add-ajax.php", headers=headers, data=payload
            ) as response:
                response.raise_for_status()
                result = await response.text()
                _LOGGER.info("Parcel Add Response: %s", result)

        except ClientResponseError as err:
            _LOGGER.error("API call failed with status %s: %s", err.status, err.message)
            result = "API Call Failed"
        except Exception as err:
            _LOGGER.error("Unexpected error during API call: %s", err)
            result = "Unexpected Error"

    hass.services.async_register(
        DOMAIN,
        "add_parcel",
        async_add_parcel,
        schema=ADD_PARCEL_SCHEMA,
    )
