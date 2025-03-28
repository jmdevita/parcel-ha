"""Integration for Parcel tracking config flow."""

import logging
from typing import Any

import requests
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, PARCEL_URL

_LOGGER = logging.getLogger(__name__)


class ParcelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for your integration."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._api_key: str | None = None
        self._error: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Handle the user step to collect the API key and optional account token."""
        if user_input is not None:
            # User submitted the form with API Key and optional Account Token
            api_key = user_input["api_key"]
            account_token = user_input.get("account_token", None)

            # Validate the API key by making a request to the API
            try:
                headers = {"api-key": api_key}
                response = await self.hass.async_add_executor_job(
                    self._validate_api_key, headers
                )

                if response.status_code == 200:
                    # API key is valid, proceed to store the configuration
                    return self.async_create_entry(
                        title="Parcel",
                        data={"api_key": api_key, "account_token": account_token},
                    )
                self._error = "Invalid API Key"
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._create_schema(),
                    errors={"base": self._error},
                )
            except requests.exceptions.RequestException:
                self._error = "Could not connect to the API"
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._create_schema(),
                    errors={"base": self._error},
                )

        # Show the API key form to the user
        return self.async_show_form(
            step_id="user",
            data_schema=self._create_schema(),
            errors={"base": self._error} if self._error else None,
        )

    def _create_schema(self) -> vol.Schema:
        """Create the form schema for collecting the API key and optional account token."""
        return vol.Schema(
            {
                vol.Required("api_key", default=""): str,
                vol.Optional("account_token", default=""): str,
            }
        )

    def _validate_api_key(self, headers: dict[str, str]) -> requests.Response:
        """Validate the API key with the API."""
        return requests.get(PARCEL_URL, headers=headers, timeout=10)

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigFlow,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return ParcelOptionsFlow()


class ParcelOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for the Parcel integration."""

    @property
    def config_entry(self):
        """Retrieve the current configuration entry."""
        return self.hass.config_entries.async_get_entry(self.handler)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            # Validate the new API key if it was changed
            new_api_key = user_input.get("api_key")
            new_account_token = user_input.get("account_token")

            # Check if the API key or account token has changed
            if new_api_key != self.config_entry.data.get(
                "api_key"
            ) or new_account_token != self.config_entry.data.get("account_token"):
                try:
                    # Validate the API key if it has changed
                    if new_api_key != self.config_entry.data.get("api_key"):
                        headers = {"api-key": new_api_key}
                        response = await self.hass.async_add_executor_job(
                            self._validate_api_key, headers
                        )
                        if response.status_code != 200:
                            return self.async_show_form(
                                step_id="init",
                                data_schema=self._create_schema(),
                                errors={"base": "invalid_api_key"},
                            )

                    # Update the config entry with the new values
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data={
                            "api_key": new_api_key,
                            "account_token": new_account_token,
                        },
                    )

                except requests.exceptions.RequestException:
                    return self.async_show_form(
                        step_id="init",
                        data_schema=self._create_schema(),
                        errors={"base": "cannot_connect"},
                    )

            # Save the updated options
            return self.async_create_entry(data=user_input)

        return self.async_show_form(step_id="init", data_schema=self._create_schema())

    def _create_schema(self) -> vol.Schema:
        """Create the form schema for updating the API key and optional account token."""
        return vol.Schema(
            {
                vol.Required(
                    "api_key",
                    default=self.config_entry.data.get("api_key", ""),
                ): str,
                vol.Optional(
                    "account_token",
                    default=self.config_entry.data.get("account_token", ""),
                ): str,
            }
        )

    def _validate_api_key(self, headers: dict[str, str]) -> requests.Response:
        """Validate the API key with the API."""
        return requests.get(PARCEL_URL, headers=headers, timeout=10)
