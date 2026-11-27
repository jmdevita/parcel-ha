"""Tests for event date normalization and the normalized shipment data sensor."""

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.parcelapp.coordinator import ParcelUpdateCoordinator
from custom_components.parcelapp.sensor import (
    NormalizedShipmentData,
    normalize_deliveries,
)
from custom_components.parcelapp.utils import normalize_event_date

NOW = datetime(2025, 5, 14, 12, 0)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Formats reported in issue #51
        ("Tuesday, May 13 1:31 PM", "2025-05-13T13:31:00"),
        ("Wednesday, April 30 ", "2025-04-30"),
        ("May 13, 2025 13:31", "2025-05-13T13:31:00"),
        ("05.13.2025 13:31", "2025-05-13T13:31:00"),
        ("Tuesday, May 13 1:31 pm", "2025-05-13T13:31:00"),
        # Day-first carriers (DHL, DPD, Australia Post)
        ("13.05.2025 13:31", "2025-05-13T13:31:00"),
        ("24.03.2025 12:02", "2025-03-24T12:02:00"),
        # Already ISO
        ("2025-05-13T13:31:00Z", "2025-05-13T13:31:00+00:00"),
        ("2025-05-13T13:31:00", "2025-05-13T13:31:00"),
        ("2025-05-13", "2025-05-13"),
        # Timezone abbreviations become offsets
        ("May 13, 2025 01:31 PM EST", "2025-05-13T13:31:00-05:00"),
        ("Tuesday, May 13 9:15 AM PDT", "2025-05-13T09:15:00-07:00"),
        ("13.05.2025 13:31 AEST", "2025-05-13T13:31:00+10:00"),
        ("May 13, 2025 13:31 est", "2025-05-13T13:31:00-05:00"),
        # Hour without minutes
        ("May 13, 2025 1 PM", "2025-05-13T13:00:00"),
        # Double spaces
        ("March  31 2025  10:33", "2025-03-31T10:33:00"),
    ],
)
def test_normalize_event_date(raw, expected):
    assert normalize_event_date(raw, now=NOW) == expected


@pytest.mark.parametrize(
    "raw",
    [None, "", "   ", "Delivered", "10:33", "Tuesday", 12345, "May 13, 2025 13:31 XYZT", "Monday, May 2025"],
)
def test_normalize_event_date_unreadable(raw):
    assert normalize_event_date(raw, now=NOW) is None


def test_missing_year_rolls_back_across_new_year():
    """An event from late December read in early January is from last year."""
    jan = datetime(2026, 1, 3, 8, 0)
    assert normalize_event_date("Friday, December 27 9:00 AM", now=jan) == "2025-12-27T09:00:00"
    assert normalize_event_date("Friday, January 2 9:00 AM", now=jan) == "2026-01-02T09:00:00"


def test_february_29_without_year():
    assert (
        normalize_event_date("February 29 10:00", now=datetime(2024, 3, 1, 12))
        == "2024-02-29T10:00:00"
    )


def test_february_29_without_year_in_non_leap_year():
    assert (
        normalize_event_date("February 29 10:00", now=datetime(2025, 3, 1, 12))
        == "2024-02-29T10:00:00"
    )


def test_missing_year_event_just_after_new_year_in_zone_ahead():
    """Read at 14:00 on Dec 31 (host time), 01:00 Jan 1 NZDT has already happened."""
    now = datetime(2025, 12, 31, 14, 0)
    assert (
        normalize_event_date("January 1 01:00 NZDT", now=now)
        == "2026-01-01T01:00:00+13:00"
    )


def test_ambiguous_day_month_compares_instants_across_timezones():
    """13:00 CEST on 6 May is 11:00 UTC, so it is already past at 12:00 UTC."""
    now = datetime(2025, 5, 6, 12, 0, tzinfo=timezone.utc)
    assert (
        normalize_event_date("05/06/2025 13:00 CEST", now=now)
        == "2025-05-06T13:00:00+02:00"
    )


def test_ambiguous_day_month_prefers_strictly_past_date():
    """04.05.2025 read on 2025-05-03: 5 April beats 4 May even though 4 May is close."""
    now = datetime(2025, 5, 3, 12, 0)
    assert normalize_event_date("04.05.2025 10:00", now=now) == "2025-04-05T10:00:00"


def test_ambiguous_day_month_prefers_past_date():
    """04.06.2025 read on 2025-05-14: 4 June is in the future, so 6 April wins."""
    assert normalize_event_date("04.06.2025 10:00", now=NOW) == "2025-04-06T10:00:00"


def test_normalize_deliveries_keeps_raw_and_does_not_mutate_input():
    deliveries = [
        {
            "carrier_code": "usps",
            "events": [
                {"event": "Delivered", "date": "Tuesday, May 13 1:31 PM", "location": "X"},
                {"event": "Label created", "date": "", "location": "Y"},
            ],
        },
        {"carrier_code": "dpd", "events": []},
        {"carrier_code": "none"},
    ]
    original = copy.deepcopy(deliveries)

    result = normalize_deliveries(deliveries)

    assert deliveries == original
    first = result[0]["events"][0]
    assert first["date_raw"] == "Tuesday, May 13 1:31 PM"
    assert first["date"].endswith("-05-13T13:31:00")
    assert first["event"] == "Delivered"
    assert first["location"] == "X"
    assert result[0]["events"][1] == {
        "event": "Label created",
        "date": None,
        "date_raw": "",
        "location": "Y",
    }
    assert result[1]["events"] == []
    assert result[2] == {"carrier_code": "none"}


@pytest.mark.asyncio
async def test_normalized_shipment_data_sensor(hass):
    fixtures_path = Path(__file__).parent / "fixtures"
    with open(fixtures_path / "multi.json") as file:
        data = json.load(file)
    data["carrier_codes_updated"] = "2025-05-14 12:00:00.000000"
    data["utc_timestamp"] = "2025-05-14 12:00:00.000000"
    raw_deliveries = copy.deepcopy(data["deliveries"])

    coordinator = AsyncMock(spec=ParcelUpdateCoordinator)
    coordinator.config_entry = AsyncMock(spec=ParcelUpdateCoordinator)
    coordinator.config_entry.entry_id = "test_entry_12345"
    coordinator.data = data

    sensor = NormalizedShipmentData(coordinator)
    sensor.hass = hass
    sensor.async_write_ha_state = Mock()
    sensor._handle_coordinator_update()

    assert sensor.unique_id == "test_entry_12345_normalized_shipment_data"
    assert sensor.entity_registry_enabled_default is False
    assert sensor.state == "2025-05-14 12:00:00.000000"

    attrs = sensor.extra_state_attributes
    assert attrs["success"] is True
    events = attrs["deliveries"][0]["events"]
    assert events[1]["date"] == "2025-03-24T12:02:00"
    assert events[1]["date_raw"] == "24.03.2025 12:02"
    assert attrs["deliveries"][1]["events"][1]["date"] == "2025-03-31T10:33:00"
    # The coordinator data (shared with the raw sensor) is left untouched
    assert data["deliveries"] == raw_deliveries
