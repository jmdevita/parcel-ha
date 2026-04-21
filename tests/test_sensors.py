import pytest
import json
from datetime import datetime, timedelta, date
from unittest.mock import AsyncMock, Mock
from dateutil.parser import parse as dateparse
from pathlib import Path
from custom_components.parcelapp.sensor import RecentShipment, ActiveShipment, CollectionShipment
from custom_components.parcelapp.coordinator import ParcelUpdateCoordinator

# Modify Date Expected to be pertinent to the test
today = date.today()
yesterday = today + timedelta(days=-1)
tomorrow = today + timedelta(days=1)

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
recent_data["carrier_codes"] = {'pholder': 'Placeholder', 'none': 'None', 'fedex': 'Fedex'}
recent_data["utc_timestamp"] = mock_datetime
# Modify the active parcel to be out for delivery tomorrow
recent_data["deliveries"][0]["date_expected"] = datetime.strftime(tomorrow,"%Y-%m-%d") + "T00:00:00Z"
# Set delivery window end to tomorrow as well
recent_data["deliveries"][0]["date_expected_end"] = datetime.strftime(tomorrow,"%Y-%m-%d") + "T17:00:00Z"
# Set timestamp values for delivery window
tomorrow_start = datetime.combine(tomorrow, datetime.min.time())
recent_data["deliveries"][0]["timestamp_expected"] = int(tomorrow_start.timestamp())
recent_data["deliveries"][0]["timestamp_expected_end"] = int(tomorrow_start.timestamp()) + 61200  # +17 hours
# Modify the active parcel's event date to be yesterday
recent_data["deliveries"][0]["events"][0]["date"] = datetime.strftime(yesterday,"%A, %B %-d, %Y %-I:%M %p")

## No Data
with open(fixtures_path / "none.json") as file:
    no_data = json.load(file)

with open(fixtures_path / "multi.json") as file:
    recent_multi_data = json.load(file)
### Mock extra parcel info
recent_multi_data["carrier_codes_updated"] = mock_datetime
recent_multi_data["carrier_codes"] = {'pholder': 'Placeholder', 'none': 'None', 'au':'Australia Post', 'dhl': 'DHL Express', 'dpd':'DPD Germany', 'fedex': 'Fedex', 'usps':'USPS'}
recent_multi_data["utc_timestamp"] = mock_datetime
# Modify the collectable parcel to have been delivered yesterday
recent_multi_data["deliveries"][0]["events"][0]["date"] = datetime.strftime(yesterday,"%d.%m.%Y %H:%M")
# Modify the delivered parcel to have been delivered today
recent_multi_data["deliveries"][1]["events"][0]["date"] = datetime.strftime(today,"%A, %B %-d, %Y %-I:%M %p")
# Modify the active parcel to be out for delivery today
recent_multi_data["deliveries"][3]["date_expected"] = datetime.strftime(today,"%Y-%m-%dT") + "09:00:00-05:00" + datetime.strftime(today+timedelta(hours=5),"%H:%M")
# Modify the active parcel's event date to be yesterday
recent_multi_data["deliveries"][3]["events"][0]["date"] = datetime.strftime(yesterday,"%B %-d, %Y %I:%M %p") + " EST"

@pytest.mark.asyncio
async def test_recent_shipment_sensor(hass):
    """Test the RecentShipment sensor with data from the recent.json fixture."""
    # Mock the coordinator
    mock_coordinator = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.config_entry = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.data = recent_data
    mock_coordinator.config_entry.entry_id = "test_entry_12345"

    # Initialize the RecentShipment sensor
    sensor = RecentShipment(mock_coordinator)
    sensor.hass = hass
    sensor.async_write_ha_state = Mock()

    # Call _handle_coordinator_update to fetch data
    sensor._handle_coordinator_update()

    # Assert the state and attributes for the first delivery in the fixture
    assert sensor.state == "Delivery in transit."
    attrs = sensor.extra_state_attributes
    assert attrs["full_description"] == "Wireless Mouse Set"
    assert attrs["tracking_number"] == "8217400125612976"
    assert attrs["date_expected"] == tomorrow
    assert attrs["date_expected_end"] == tomorrow
    assert attrs["timestamp_expected"] == datetime.fromtimestamp(recent_data["deliveries"][0]["timestamp_expected"])
    assert attrs["timestamp_expected_end"] == datetime.fromtimestamp(recent_data["deliveries"][0]["timestamp_expected_end"])
    assert attrs["extra_information"] == "FedEx SmartPost"
    assert attrs["event_date"] == yesterday
    assert attrs["event_location"] == "Harrisburg, PA, USA"
    assert attrs["status"] == "Delivery in transit."
    assert attrs["carrier"] == "Fedex"


@pytest.mark.asyncio
async def test_active_shipment_sensor(hass):
    """Test the ActiveShipment sensor with data from the recent.json fixture."""

    # Mock the coordinator
    mock_coordinator = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.config_entry = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.data = recent_data
    mock_coordinator.config_entry.entry_id = "test_entry_12345"

    # Initialize the ActiveShipment sensor
    sensor = ActiveShipment(mock_coordinator)
    sensor.hass = hass
    sensor.async_write_ha_state = Mock()

    # Call async_update to fetch data
    sensor._handle_coordinator_update()

    # Assert the state and attributes
    assert sensor.state == 2
    assert sensor.extra_state_attributes == {
        'status_text': 'in 1 day',
        'number_of_active_parcels': 2,
        'parcels_arriving_today': 0,
        'full_description': 'Wireless Mouse Set',
        'tracking_number': '8217400125612976',
        'date_expected': tomorrow,
        'date_expected_end': dateparse(recent_data["deliveries"][0]["date_expected_end"]).date(),
        'timestamp_expected': datetime.fromtimestamp(recent_data["deliveries"][0]["timestamp_expected"]),
        'timestamp_expected_end': datetime.fromtimestamp(recent_data["deliveries"][0]["timestamp_expected_end"]),
        'extra_information': 'FedEx SmartPost',
        'days_until_next_delivery': 1,
        'event': 'Departure Scan',
        'event_date': yesterday,
        'event_location': 'Harrisburg, PA, USA',
        'next_delivery_status': 'Delivery in transit.',
        'next_delivery_carrier': 'Fedex',
        'delivered_today': 0,
    }

@pytest.mark.asyncio
async def test_collectable_shipment_sensor(hass):
    """Test the CollectionShipment sensor with data from the recent.json fixture."""

    # Modify Date Expected to be pertinent to the test
    recent_collectable_data = recent_data
    del recent_collectable_data["deliveries"][0]["date_expected"]
    recent_collectable_data["deliveries"][0]["events"][0]["date"] = datetime.strftime(yesterday,"%A, %B %-d, %Y %-I:%M %p")

    # Mock the coordinator
    mock_coordinator = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.config_entry = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.data = recent_collectable_data
    mock_coordinator.config_entry.entry_id = "test_entry_12345"

    # Initialize the ActiveShipment sensor
    sensor = CollectionShipment(mock_coordinator)
    sensor.hass = hass
    sensor.async_write_ha_state = Mock()

    # Call async_update to fetch data
    sensor._handle_coordinator_update()

    # Assert the state and attributes
    assert sensor.state == 0
    assert sensor.extra_state_attributes == {
        'collectable_shipments': [],
    }

@pytest.mark.asyncio
async def test_recent_shipment_sensor_no_data(hass):
    """Test the RecentShipment sensor when no data is available."""

    # Mock the coordinator with no data
    mock_coordinator = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.config_entry = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.data = no_data
    mock_coordinator.config_entry.entry_id = "test_entry_12345"

    # Initialize the RecentShipment sensor
    sensor = RecentShipment(mock_coordinator)
    sensor.hass = hass
    sensor.async_write_ha_state = Mock()

    # Call async_update to fetch data
    sensor._handle_coordinator_update()

    # Assert the state and attributes
    assert sensor.state == 'No parcels for now..'
    assert sensor.extra_state_attributes == {
        'date_expected': 'None',
        'date_expected_end': None,
        'timestamp_expected': None,
        'timestamp_expected_end': None,
        'days_until_next_delivery': 'No active parcels.',
        'event': 'None',
        'event_date': 'None',
        'event_location': 'None',
        'extra_information': None,
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
    mock_coordinator.config_entry = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.data = no_data
    mock_coordinator.config_entry.entry_id = "test_entry_12345"

    # Initialize the ActiveShipment sensor
    sensor = ActiveShipment(mock_coordinator)
    sensor.hass = hass
    sensor.async_write_ha_state = Mock()

    # Call async_update to fetch data
    sensor._handle_coordinator_update()

    # Assert the state and attributes
    assert sensor.state == 0
    assert sensor.extra_state_attributes == {
        'status_text': 'No parcels for now..',
        'date_expected': 'None',
        'date_expected_end': None,
        'timestamp_expected': None,
        'timestamp_expected_end': None,
        'days_until_next_delivery': 'No active parcels.',
        'event': 'None',
        'event_date': 'None',
        'event_location': 'None',
        'extra_information': None,
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
    mock_coordinator.config_entry = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.data = no_data
    mock_coordinator.config_entry.entry_id = "test_entry_12345"

    # Initialize the RecentShipment sensor
    sensor = CollectionShipment(mock_coordinator)
    sensor.hass = hass
    sensor.async_write_ha_state = Mock()

    # Call async_update to fetch data
    sensor._handle_coordinator_update()

    # Assert the state and attributes
    assert sensor.state == 0
    assert sensor.extra_state_attributes == {
        'collectable_shipments': [],
    }


@pytest.mark.asyncio
async def test_recent_shipment_sensor_multi_data(hass):
    """Test the RecentShipment sensor with data from the multi.json fixture."""

    # Mock the coordinator
    mock_coordinator = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.config_entry = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.data = recent_multi_data
    mock_coordinator.config_entry.entry_id = "test_entry_12345"

    # Initialize the RecentShipment sensor
    sensor = RecentShipment(mock_coordinator)
    sensor.hass = hass
    sensor.async_write_ha_state = Mock()

    # Call _handle_coordinator_update to fetch data
    sensor._handle_coordinator_update()

    # Assert the state and attributes for the first delivery in the fixture
    assert sensor.state == "Delivery expecting a pickup by the recipient."
    assert sensor.extra_state_attributes == {
        "full_description": "Collectable Parcel",
        "tracking_number": "12345678",
        "date_expected": "Unknown",
        "date_expected_end": None,
        "timestamp_expected": None,
        "timestamp_expected_end": None,
        "extra_information": None,
        "event_date": yesterday,
        "event_location": "Somewhere",
        "status": "Delivery expecting a pickup by the recipient.",
        "carrier": "Australia Post",
    }

@pytest.mark.asyncio
async def test_active_shipment_sensor_multi_data(hass):
    """Test the ActiveShipment sensor with data from the multi.json fixture."""

    # Mock the coordinator with no data
    mock_coordinator = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.config_entry = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.data = recent_multi_data
    mock_coordinator.config_entry.entry_id = "test_entry_12345"

    # Initialize the ActiveShipment sensor
    sensor = ActiveShipment(mock_coordinator)
    sensor.hass = hass
    sensor.async_write_ha_state = Mock()

    # Call async_update to fetch data
    sensor._handle_coordinator_update()

    # Assert the state and attributes
    # one parcel arriving today, not an error!
    assert sensor.state == 2
    assert sensor.extra_state_attributes == {
        'status_text': '1 parcel',
        'date_expected': today,
        'date_expected_end': None,
        'timestamp_expected': None,
        'timestamp_expected_end': None,
        'days_until_next_delivery': 0,
        'event': 'Postmark Mailpiece by Carrier',
        'event_date': yesterday,
        'event_location': 'The Moon',
        'extra_information': None,
        'full_description': 'An out for delivery shipment',
        'next_delivery_carrier': 'USPS',
        'next_delivery_status': 'Out for delivery.',
        'number_of_active_parcels': 2,
        'parcels_arriving_today': 1,
        'tracking_number': '4567891011',
        'delivered_today': 1,
    }

@pytest.mark.asyncio
async def test_collectable_shipment_sensor_multi_data(hass):
    """Test the CollectionShipment sensor with data from the multi.json fixture."""

    # Mock the coordinator
    mock_coordinator = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.config_entry = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.data = recent_multi_data
    mock_coordinator.config_entry.entry_id = "test_entry_12345"

    # Initialize the ActiveShipment sensor
    sensor = CollectionShipment(mock_coordinator)
    sensor.hass = hass
    sensor.async_write_ha_state = Mock()

    # Call async_update to fetch data
    sensor._handle_coordinator_update()

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


@pytest.mark.asyncio
async def test_delivery_window_attributes(hass):
    """Test that delivery window attributes are properly exposed on both sensors."""
    # Create test data with delivery window fields
    tomorrow_ts = int(datetime.combine(tomorrow, datetime.min.time()).timestamp())
    tomorrow_end_ts = tomorrow_ts + 14400  # +4 hours

    delivery_window_data = {
        "success": True,
        "deliveries": [
            {
                "carrier_code": "fedex",
                "description": "Package with delivery window",
                "status_code": 4,  # Out for delivery
                "tracking_number": "1234567890",
                "date_expected": datetime.strftime(tomorrow, "%Y-%m-%d") + "T09:00:00Z",
                "date_expected_end": datetime.strftime(tomorrow, "%Y-%m-%d") + "T13:00:00Z",
                "timestamp_expected": tomorrow_ts,
                "timestamp_expected_end": tomorrow_end_ts,
                "events": [
                    {
                        "event": "Out for Delivery",
                        "date": datetime.strftime(today, "%A, %B %-d, %Y %-I:%M %p"),
                        "location": "Local Facility"
                    }
                ]
            }
        ],
        "carrier_codes": {"fedex": "FedEx"},
        "carrier_codes_updated": mock_datetime,
        "utc_timestamp": mock_datetime,
    }

    # Mock the coordinator
    mock_coordinator = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.config_entry = AsyncMock(spec=ParcelUpdateCoordinator)
    mock_coordinator.data = delivery_window_data
    mock_coordinator.config_entry.entry_id = "test_entry_12345"

    # Test RecentShipment sensor
    recent_sensor = RecentShipment(mock_coordinator)
    recent_sensor.hass = hass
    recent_sensor.async_write_ha_state = Mock()
    recent_sensor._handle_coordinator_update()

    # Verify delivery window attributes on RecentShipment
    attrs = recent_sensor.extra_state_attributes
    assert attrs["date_expected"] == tomorrow
    assert attrs["date_expected_end"] == tomorrow
    assert attrs["timestamp_expected"] == datetime.fromtimestamp(tomorrow_ts)
    assert attrs["timestamp_expected_end"] == datetime.fromtimestamp(tomorrow_end_ts)

    # Test ActiveShipment sensor
    active_sensor = ActiveShipment(mock_coordinator)
    active_sensor.hass = hass
    active_sensor.async_write_ha_state = Mock()
    active_sensor._handle_coordinator_update()

    # Verify delivery window attributes on ActiveShipment
    attrs = active_sensor.extra_state_attributes
    assert attrs["date_expected"] == tomorrow
    assert attrs["date_expected_end"] == tomorrow
    assert attrs["timestamp_expected"] == datetime.fromtimestamp(tomorrow_ts)
    assert attrs["timestamp_expected_end"] == datetime.fromtimestamp(tomorrow_end_ts)