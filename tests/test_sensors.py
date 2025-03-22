import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from pathlib import Path
from custom_components.parcelapp.sensor import RecentShipment, ActiveShipment
from custom_components.parcelapp.coordinator import ParcelUpdateCoordinator

# Load the fixture data
## Recent Data
fixtures_path = Path(__file__).parent / "fixtures"
with open(fixtures_path / "recent.json") as file:
    recent_data = json.load(file)
### Mock extra parcel info
mock_datetime = datetime.now().strftime(
    "%Y-%m-%d %H:%M:%S.%f"
)
recent_data["carrier_codes_updated"] = mock_datetime
recent_data["carrier_codes"] = {'pholder': 'Placeholder', 'none': 'None'}
recent_data["utc_timestamp"] = mock_datetime

## No Data
with open(fixtures_path / "none.json") as file:
    no_data = json.load(file)

@pytest.mark.asyncio
async def test_recent_shipment_sensor():
    """Test the RecentShipment sensor with data from the recent.json fixture."""
    # Mock the coordinator
    mock_coordinator = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.data = recent_data

    # Initialize the RecentShipment sensor
    sensor = RecentShipment(mock_coordinator)

    # Call async_update to fetch data
    await sensor.async_update()

    # Assert the state and attributes for the first delivery in the fixture
    assert sensor.state == "Delivery expecting a pickup by the recipient."
    assert sensor.extra_state_attributes == {
        "full_description": "Wireless Mouse Set",
        "tracking_number": "8217400125612976",
        "date_expected": "2023-03-05T00:00:00Z",
        "event_date": "Saturday, March 4, 2023 11:45 AM",
        "event_location": "Austin, TX, USA",
        "status": "Delivery expecting a pickup by the recipient.",
        "carrier": "Unknown",
    }


@pytest.mark.asyncio
async def test_active_shipment_sensor(hass):
    """Test the ActiveShipment sensor with data from the recent.json fixture."""

    # Modify Date Expected to be pertinent to the test
    tomorrow = datetime.now() + timedelta(days=1)
    recent_data["deliveries"][0]["date_expected"] = str(tomorrow)

    # Mock the coordinator
    mock_coordinator = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.data = recent_data

    # Initialize the ActiveShipment sensor
    sensor = ActiveShipment(mock_coordinator)

    # Call async_update to fetch data
    await sensor.async_update()

    # Assert the state and attributes
    assert sensor.state == "in 1 day"
    assert sensor.extra_state_attributes == {
        'number_of_active_parcels': 1,
        'parcels_arriving_today': 0,
        'full_description': 'Wireless Mouse Set',
        'tracking_number': '8217400125612976',
        'date_expected': tomorrow,
        'days_until_next_delivery': 1,
        'event': 'Delivered to Address',
        'event_date': 'Saturday, March 4, 2023 11:45 AM',
        'event_location': 'Austin, TX, USA',
        'next_delivery_status': 'Delivery expecting a pickup by the recipient.',
        'next_delivery_carrier': 'Unknown'
    }


@pytest.mark.asyncio
async def test_recent_shipment_sensor_no_data(hass):
    """Test the RecentShipment sensor when no data is available."""

    # Mock the coordinator with no data
    mock_coordinator = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.data = no_data

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

    # Mock the coordinator with no data
    mock_coordinator = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.data = no_data

    # Initialize the ActiveShipment sensor
    sensor = ActiveShipment(mock_coordinator)

    # Call async_update to fetch data
    await sensor.async_update()

    # Assert the state and attributes
    assert sensor.state is None
    assert sensor.extra_state_attributes == {}
