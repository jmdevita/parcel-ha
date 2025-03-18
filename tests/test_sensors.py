import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from pathlib import Path
from custom_components.parcelapp.sensor import RecentShipment, ActiveShipment
from custom_components.parcelapp.coordinator import ParcelUpdateCoordinator


@pytest.mark.asyncio
async def test_recent_shipment_sensor():
    """Test the RecentShipment sensor with data from the recent.json fixture."""
    # Load the fixture data
    fixtures_path = Path(__file__).parent / "fixtures"
    with open(fixtures_path / "recent.json") as file:
        fixture_data = json.load(file)

    # Mock the coordinator
    mock_coordinator = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.data = fixture_data["deliveries"]

    # Initialize the RecentShipment sensor
    sensor = RecentShipment(mock_coordinator)

    # Call async_update to fetch data
    await sensor.async_update()

    # Assert the state and attributes for the first delivery in the fixture
    assert sensor.state == "Delivered to Address"
    assert sensor.extra_state_attributes == {
        "full_description": "Wireless Mouse Set",
        "tracking_number": "8217400125612976",
        "date_expected": "2023-03-05T00:00:00Z",
        "status_code": 3,
        "carrier_code": "fedex",
        "event_date": "Saturday, March 4, 2023 11:45 AM",
        "event_location": "Austin, TX, USA",
        "carrier_code_verbose": "FedEx",
    }


@pytest.mark.asyncio
async def test_active_shipment_sensor(hass):
    """Test the ActiveShipment sensor with data from the recent.json fixture."""
    # Load the fixture data
    fixtures_path = Path(__file__).parent / "fixtures"
    with open(fixtures_path / "recent.json") as file:
        fixture_data = json.load(file)

    # Modify Date Expected to be pertinent to the test
    tomorrow = datetime.now() + timedelta(days=1)
    fixture_data["deliveries"][0]["date_expected"] = str(tomorrow)

    # Mock the coordinator
    mock_coordinator = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.data = fixture_data["deliveries"]

    # Initialize the ActiveShipment sensor
    sensor = ActiveShipment(mock_coordinator)

    # Call async_update to fetch data
    await sensor.async_update()

    # Assert the state and attributes
    assert sensor.state == "in 1 day"
    assert sensor.extra_state_attributes == {
        "number_of_active_parcels": 1,
        "parcels_arriving_today": 0,
        "days_until_next_delivery": 1,
    }


@pytest.mark.asyncio
async def test_recent_shipment_sensor_no_data(hass):
    """Test the RecentShipment sensor when no data is available."""
    # Load the fixture data
    fixtures_path = Path(__file__).parent / "fixtures"
    with open(fixtures_path / "none.json") as file:
        fixture_data = json.load(file)

    # Mock the coordinator with no data
    mock_coordinator = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.data = fixture_data["deliveries"]

    # Initialize the RecentShipment sensor
    sensor = RecentShipment(mock_coordinator)

    # Call async_update to fetch data
    await sensor.async_update()

    # Assert the state and attributes
    assert sensor.state is None
    assert sensor.extra_state_attributes == {}


@pytest.mark.asyncio
async def test_active_shipment_sensor_no_data(hass):
    """Test the ActiveShipment sensor when no data is available."""
    # Load the fixture data
    fixtures_path = Path(__file__).parent / "fixtures"
    with open(fixtures_path / "none.json") as file:
        fixture_data = json.load(file)

    # Mock the coordinator with no data
    mock_coordinator = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.data = fixture_data["deliveries"]

    # Initialize the ActiveShipment sensor
    sensor = ActiveShipment(mock_coordinator)

    # Call async_update to fetch data
    await sensor.async_update()

    # Assert the state and attributes
    assert sensor.state is None
    assert sensor.extra_state_attributes == {}
