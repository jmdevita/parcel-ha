import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from pathlib import Path
from custom_components.parcelapp.sensor import RecentShipment, ActiveShipment, CollectionShipment
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

with open(fixtures_path / "multi.json") as file:
    recent_multi_data = json.load(file)
### Mock extra parcel info
# Modify Date Expected to be pertinent to the test
today = datetime.now()
yesterday = today + timedelta(days=-1)
tomorrow = today + timedelta(days=1)
recent_multi_data["carrier_codes_updated"] = mock_datetime
recent_multi_data["carrier_codes"] = {'pholder': 'Placeholder', 'none': 'None', 'au':'Australia Post', 'dhl': 'DHL Express', 'dpd':'DPD Germany', 'usps':'USPS'}
recent_multi_data["utc_timestamp"] = mock_datetime
recent_multi_data["deliveries"][0]["events"][0]["date"] = datetime.strftime(yesterday,"%d.%m.%Y %H:%M")
recent_multi_data["deliveries"][1]["events"][0]["date"] = datetime.strftime(today,"%A, %B %-d, %Y %-I:%M %p")
recent_multi_data["deliveries"][3]["date_expected"] = datetime.strftime(today,"%Y-%m-%dT") + "09:00:00-05:00" + datetime.strftime(today+timedelta(hours=5),"%H:%M")

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
        'next_delivery_carrier': 'Unknown',
        'delivered_today': 0,
    }

@pytest.mark.asyncio
async def test_collectable_shipment_sensor(hass):
    """Test the CollectionShipment sensor with data from the recent.json fixture."""

    # Modify Date Expected to be pertinent to the test
    yesterday = datetime.now() + timedelta(days=-1)
    recent_collectable_data = recent_data
    del recent_collectable_data["deliveries"][0]["date_expected"]
    recent_collectable_data["deliveries"][0]["events"][0]["date"] = datetime.strftime(yesterday,"%A, %B %-d, %Y %-I:%M %p")

    # Mock the coordinator
    mock_coordinator = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.data = recent_collectable_data

    # Initialize the ActiveShipment sensor
    sensor = CollectionShipment(mock_coordinator)

    # Call async_update to fetch data
    await sensor.async_update()

    # Assert the state and attributes
    assert sensor.state == 1
    assert sensor.extra_state_attributes == {
        'collectable_shipments': [
            {
            "description": "Wireless Mouse Set",
            "location": "Austin, TX, USA",
            # This is temporary until we add the parsing function
            "delivered": datetime.strftime(yesterday,"%A, %B %-d, %Y %-I:%M %p"),
            }
        ],
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
    assert sensor.state == 'No parcels for now..'
    assert sensor.extra_state_attributes == {
        'date_expected': 'None',
        'days_until_next_delivery': 'No active parcels.',
        'event': 'None',
        'event_date': 'None',
        'event_location': 'None',
        'full_description': 'No description',
        'next_delivery_carrier': 'None',
        'next_delivery_status': 'None',
        'number_of_active_parcels': 0,
        'parcels_arriving_today': 0,
        'tracking_number': 'None',
    }


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
    assert sensor.state == 'No parcels for now..'
    assert sensor.extra_state_attributes == {
        'date_expected': 'None',
        'days_until_next_delivery': 'No active parcels.',
        'event': 'None',
        'event_date': 'None',
        'event_location': 'None',
        'full_description': 'No description',
        'next_delivery_carrier': 'None',
        'next_delivery_status': 'None',
        'number_of_active_parcels': 0,
        'parcels_arriving_today': 0,
        'tracking_number': 'None',
        'delivered_today': 0,
    }

@pytest.mark.asyncio
async def test_collection_shipment_sensor_no_data(hass):
    """Test the CollectionShipment sensor when no data is available."""

    # Mock the coordinator with no data
    mock_coordinator = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.data = no_data

    # Initialize the RecentShipment sensor
    sensor = CollectionShipment(mock_coordinator)

    # Call async_update to fetch data
    await sensor.async_update()

    # Assert the state and attributes
    assert sensor.state == 0
    assert sensor.extra_state_attributes == {
        'collectable_shipments': [],
    }


@pytest.mark.asyncio
async def test_recent_shipment_sensor_multi_data():
    """Test the RecentShipment sensor with data from the multi.json fixture."""

    # Mock the coordinator
    mock_coordinator = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.data = recent_multi_data

    # Initialize the RecentShipment sensor
    sensor = RecentShipment(mock_coordinator)

    # Call async_update to fetch data
    await sensor.async_update()

    # Assert the state and attributes for the first delivery in the fixture
    assert sensor.state == "Delivery expecting a pickup by the recipient."
    assert sensor.extra_state_attributes == {
        "full_description": "Collectable Parcel",
        "tracking_number": "12345678",
        "date_expected": "Unknown",
        # This is temporary until we add the parsing function
        "event_date": datetime.strftime(yesterday,"%d.%m.%Y %H:%M"),
        "event_location": "Somewhere",
        "status": "Delivery expecting a pickup by the recipient.",
        "carrier": "Australia Post",
    }

@pytest.mark.asyncio
async def test_active_shipment_sensor_no_data(hass):
    """Test the ActiveShipment sensor with data from the multi.json fixture."""

    # Mock the coordinator with no data
    mock_coordinator = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.data = recent_multi_data

    # Initialize the ActiveShipment sensor
    sensor = ActiveShipment(mock_coordinator)

    # Call async_update to fetch data
    await sensor.async_update()

    # Assert the state and attributes
    assert sensor.state == '1 parcel'
    assert sensor.extra_state_attributes == {
        'date_expected': today.date(),
        'days_until_next_delivery': 0,
        'event': 'Postmark Mailpiece by Carrier',
        'event_date': 'February 14, 2025 04:27 PM EST',
        'event_location': 'The Moon',
        'full_description': 'An out for delivery shipment',
        'next_delivery_carrier': 'USPS',
        'next_delivery_status': 'Out for delivery.',
        'number_of_active_parcels': 2,
        'parcels_arriving_today': 1,
        'tracking_number': '4567891011'
    }

@pytest.mark.asyncio
async def test_collectable_shipment_sensor_multi_data(hass):
    """Test the CollectionShipment sensor with data from the multi.json fixture."""

    # Mock the coordinator
    mock_coordinator = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.data = recent_multi_data

    # Initialize the ActiveShipment sensor
    sensor = CollectionShipment(mock_coordinator)

    # Call async_update to fetch data
    await sensor.async_update()

    # Assert the state and attributes
    assert sensor.state == 1
    assert sensor.extra_state_attributes == {
        'collectable_shipments': [
            {
            "description": "Collectable Parcel",
            "location": "Somewhere",
            # This is temporary until we add the parsing function
            "delivered": datetime.strftime(yesterday,"%d.%m.%Y %H:%M")
            }
        ],
    }