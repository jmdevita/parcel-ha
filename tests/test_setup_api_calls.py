"""Setup must not spend extra API calls (issue #81).

The Parcel API allows 20 requests per hour. Sensors used to be added with
update_before_add=True, which made each Home Assistant restart request another
refresh straight after the coordinator's first one: 3 calls instead of 1 with
no cache, and 2 instead of 0 with fresh cached data.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.parcelapp.const import DOMAIN, STORAGE_KEY, STORAGE_VERSION

DELIVERIES_URL = "https://api.parcel.app/external/deliveries/?filter_mode=recent"
CARRIERS_URL = "https://api.parcel.app/external/supported_carriers.json"
ENTRY_ID = "test_entry_setup"


def _deliveries_calls(aioclient_mock):
    return sum(1 for call in aioclient_mock.mock_calls if str(call[1]) == DELIVERIES_URL)


@pytest.fixture
def api_data():
    with open(Path(__file__).parent / "fixtures" / "recent.json") as file:
        return json.load(file)


async def _setup(hass, aioclient_mock, api_data):
    aioclient_mock.get(CARRIERS_URL, json={"fedex": "Fedex"})
    aioclient_mock.get(DELIVERIES_URL, json=api_data)
    entry = MockConfigEntry(domain=DOMAIN, data={"api_key": "k"}, entry_id=ENTRY_ID)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    # Let any debounced refresh requests fire.
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()


def _recent_state(hass):
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{ENTRY_ID}_recent_shipment"
    )
    return hass.states.get(entity_id)


async def test_setup_without_cache_makes_one_api_call(hass, aioclient_mock, api_data):
    await _setup(hass, aioclient_mock, api_data)

    assert _deliveries_calls(aioclient_mock) == 1
    # Sensors are populated from that call, not left waiting for the next update.
    assert _recent_state(hass).state == "Delivery in transit."


async def test_setup_with_fresh_cache_makes_no_api_call(
    hass, aioclient_mock, hass_storage, api_data
):
    cached = dict(
        api_data,
        utc_timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        carrier_codes={"fedex": "Fedex"},
        carrier_codes_updated=str(datetime.now()),
    )
    key = f"{STORAGE_KEY}_{ENTRY_ID}"
    hass_storage[key] = {
        "version": STORAGE_VERSION,
        "minor_version": 1,
        "key": key,
        "data": cached,
    }

    await _setup(hass, aioclient_mock, api_data)

    assert _deliveries_calls(aioclient_mock) == 0
    assert _recent_state(hass).state == "Delivery in transit."
