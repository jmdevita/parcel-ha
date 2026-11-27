"""Tests for the integration setup helpers."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.parcelapp import cleanup_old_device
from custom_components.parcelapp.const import DOMAIN


@pytest.mark.asyncio
async def test_cleanup_removes_only_the_malformed_device(hass: HomeAssistant) -> None:
    """The legacy bare (DOMAIN,) device is removed, a well-formed one is kept."""
    entry = MockConfigEntry(
        domain=DOMAIN, entry_id="entry_1", data={"api_key": "test_api_key"}
    )
    entry.add_to_hass(hass)
    device_reg = dr.async_get(hass)
    legacy = device_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN,)}, name="Legacy"
    )
    current = device_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="Parcel",
    )

    await cleanup_old_device(hass)

    assert device_reg.async_get(legacy.id) is None
    assert device_reg.async_get(current.id) is not None
