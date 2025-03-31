"""Integration for Parcel tracking sensor."""

from datetime import datetime, timedelta, date
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    UPDATE_INTERVAL_SECONDS,
    RETURN_CODES,
    DELIVERY_STATUS_CODES,
    Shipment,
    EMPTY_SHIPMENT,
    EMPTY_ATTRIBUTES,
)
from .coordinator import ParcelConfigEntry, ParcelUpdateCoordinator

PLATFORMS = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)
SCAN_INTERVAL = timedelta(seconds=UPDATE_INTERVAL_SECONDS)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ParcelConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Parcel sensor platform from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        [
            RecentShipment(coordinator),
            ActiveShipment(coordinator),
            CollectionShipment(coordinator),
            RawShipmentData(coordinator),
        ],
        update_before_add=True,
    )


class RecentShipment(SensorEntity):
    """Representation of a sensor that fetches the top value from an API."""

    def __init__(self, coordinator: ParcelUpdateCoordinator) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._hass_custom_attributes = {}
        self._attr_name = "Parcel Recent Shipment"
        self._attr_unique_id = "Parcel_Recent_Shipment"
        self._globalid = "Parcel_Recent_Shipment"
        self._attr_icon = "mdi:package"
        self._attr_state = None

    @property
    def state(self) -> Any:
        """Return the current state of the sensor."""
        return self._attr_state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._hass_custom_attributes

    async def async_update(self) -> None:
        """Fetch the latest data from the coordinator."""
        await self.coordinator.async_request_refresh()
        parcel_api_data = self.coordinator.data

        if parcel_api_data["deliveries"] == []:
            self._attr_state = "No parcels for now.."
            self._attr_icon = "mdi:close-circle"
            self._hass_custom_attributes = EMPTY_ATTRIBUTES
        elif parcel_api_data["deliveries"]:
            data = parcel_api_data["deliveries"]
            carrier_codes = parcel_api_data["carrier_codes"]
            try:
                description = data[0]["description"]
            except KeyError:
                description = "No description"
            try:
                tracking_number = data[0]["tracking_number"]
            except KeyError:
                tracking_number = "Unknown"
            try:
                date_expected = data[0]["date_expected"]
            except KeyError:
                date_expected = "Unknown"
            try:
                event_date = data[0]["events"][0]["date"]
            except KeyError:
                event_date = "Unknown"
            try:
                event_location = data[0]["events"][0]["location"]
            except KeyError:
                event_location = "Unknown"
            try:
                status = DELIVERY_STATUS_CODES[data[0]["status_code"]]
                self._attr_state = status
            except:
                status = "Unknown"
                self._attr_state = status
            try:
                carrier = carrier_codes[data[0]["carrier_code"]]
            except KeyError:
                carrier = "Unknown"
            attributes = {
                "full_description": description,
                "tracking_number": tracking_number,
                "date_expected": date_expected,
                "event_date": event_date,
                "event_location": event_location,
                "status": status,
                "carrier": carrier,
            }
            self._hass_custom_attributes = attributes


class ActiveShipment(SensorEntity):
    """Representation of a sensor that manipulates the data from the API, presents the next parcel due, and presents multiple attributes."""

    def __init__(self, coordinator: ParcelUpdateCoordinator) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._hass_custom_attributes = {}
        self._attr_name = "Parcel Active Shipment"
        self._attr_unique_id = "Parcel_Active_Shipment"
        self._globalid = "Parcel_Active_Shipment"
        self._attr_icon = "mdi:package"
        self._attr_state = None

    @property
    def state(self) -> Any:
        """Return the current state of the sensor."""
        return self._attr_state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._hass_custom_attributes

    async def async_update(self) -> None:
        """Fetch the latest data from the coordinator."""
        await self.coordinator.async_request_refresh()
        parcel_api_data = self.coordinator.data
        shipments = []
        active_shipments = []
        traceable_active_shipments = []
        today = date.today()

        if parcel_api_data["deliveries"] == []:
            self._attr_state = "No parcels for now.."
            self._attr_icon = "mdi:close-circle"
            self._hass_custom_attributes = EMPTY_ATTRIBUTES
        elif parcel_api_data["deliveries"]:
            data = parcel_api_data["deliveries"]
            carrier_codes = parcel_api_data["carrier_codes"]
            for item in data:
                # These are the mandatory properties
                carrier_code = item["carrier_code"]
                description = item["description"]
                status_code = item["status_code"]
                tracking_number = item["tracking_number"]
                # These are the optional properties
                # Events _should_ be present
                try:
                    events = item["events"]
                except KeyError:
                    events = "None"
                # Extra information is rarely present, so don't raise a KeyError
                try:
                    extra_information = item["extra_information"]
                except:
                    extra_information = None
                # We try to parse the dates for use later
                try:
                    date_expected_raw = item["date_expected"]
                    try:
                        date_expected = datetime.fromisoformat(date_expected_raw)
                    except:
                        try:
                            # Extra loop in case of double spacing in the reported date string
                            date_expected_raw = date_expected_raw.replace("  "," ")
                            date_expected = datetime.fromisoformat(
                                date_expected_raw
                            )
                        except KeyError:
                            date_expected = None
                except KeyError:
                    date_expected = None
                try:
                    date_expected_end_raw = item["date_expected_end"]
                    try:
                        date_expected_end = datetime.fromisoformat(
                            date_expected_end_raw
                        )
                    except:
                        try:
                            # Extra loop in case of double spacing in the reported date string
                            date_expected_end_raw = date_expected_end_raw.replace("  "," ")
                            date_expected_end = datetime.fromisoformat(
                                date_expected_end_raw
                            )
                        except KeyError:
                            date_expected_end = None
                except KeyError:
                    date_expected_end = None
                try:
                    timestamp_expected_raw = item["timestamp_expected"]
                    try:
                        timestamp_expected = datetime.fromisoformat(
                            timestamp_expected_raw
                        )
                    except KeyError:
                        timestamp_expected = None
                except:
                    timestamp_expected = None
                try:
                    timestamp_expected_end_raw = item["timestamp_expected_end"]
                    try:
                        timestamp_expected_end = datetime.fromisoformat(
                            timestamp_expected_end_raw
                        )
                    except KeyError:
                        timestamp_expected_end = None
                except:
                    timestamp_expected_end = None
                new_shipment = Shipment(
                    carrier_code=carrier_code,
                    description=description,
                    status_code=status_code,
                    tracking_number=tracking_number,
                    extra_information=extra_information,
                    date_expected=date_expected,
                    date_expected_end=date_expected_end,
                    timestamp_expected=timestamp_expected,
                    timestamp_expected_end=timestamp_expected_end,
                    events=events,
                )
                shipments.append(new_shipment)
                # Build the active shipments list, but remove any delivered parcels and any active parcles with no date_expected key
                if new_shipment.status_code != 0:
                    if new_shipment.date_expected is None:
                        active_shipments.append(new_shipment)
                    else:
                        # Build a list of active shipments that have a date_expected key which is today or in the future
                        if today <= new_shipment.date_expected.date():
                            active_shipments.append(new_shipment)
                            traceable_active_shipments.append(new_shipment)
            # catch if there are no active shipments
            if len(traceable_active_shipments) == 0:
                if len(active_shipments) == 0:
                    days_until_next_delivery = -1
                else:
                    # Treat as unknown but something IS coming
                    days_until_next_delivery = -2
                next_traceable_shipment = EMPTY_SHIPMENT
            else:
                try:
                    # sort the traceable active shipments list so the next shipment is first
                    traceable_active_shipments.sort(key=lambda x: x.date_expected)
                    next_traceable_shipment = traceable_active_shipments[0]
                    next_delivery_date = next_traceable_shipment.date_expected
                    days_until_next_delivery = (next_delivery_date.date() - today).days
                except ValueError:
                    # Treat as unknown but something IS coming
                    next_traceable_shipment = EMPTY_SHIPMENT
                    days_until_next_delivery = -3
            # Set the icon based upon the days until next delivery
            if days_until_next_delivery == -3:
                icon = "mdi:close-circle"
            elif days_until_next_delivery == -2:
                icon = "mdi:help-circle"
            elif days_until_next_delivery == -1:
                icon = "mdi:shopping"
            elif days_until_next_delivery == 0:
                icon = "mdi:package"
            elif days_until_next_delivery > 9:
                icon = "mdi:numeric-9-plus-circle"
            else:
                icon = "mdi:numeric-" + str(days_until_next_delivery) + "-circle"
            self._attr_icon = icon
            # Count the number of parcels arriving today
            arriving_today = sum(
                shipment.date_expected.date() == today
                for shipment in traceable_active_shipments
            )
            # Set up the verbose text
            if arriving_today > 0:
                if arriving_today == 1:
                    verbose = "1 parcel"
                else:
                    verbose = str(arriving_today) + " parcels"
            elif days_until_next_delivery > 0:
                if days_until_next_delivery == 1:
                    verbose = "in 1 day"
                else:
                    verbose = "in " + str(days_until_next_delivery) + " days"
            elif days_until_next_delivery == -2:
                if len(active_shipments) == 1:
                    verbose = "1 active parcel"
                else:
                    verbose = str(len(active_shipments)) + " active parcels"
            else:
                verbose = "No parcels for now.."
            try:
                description = next_traceable_shipment.description
            except KeyError:
                description = "No description"
            try:
                tracking_number = next_traceable_shipment.tracking_number
            except KeyError:
                tracking_number = "Unknown"
            # This would've been caught earlier, but for consistency
            try:
                date_expected = next_traceable_shipment.date_expected
            except KeyError:
                date_expected = "Unknown"
            # Catch the error codes before returning the days_until_delivery
            if days_until_next_delivery < 0:
                days_until_next_delivery = RETURN_CODES[days_until_next_delivery]
            # Retrieve further details of the next shipment if they exist
            next_traceable_shipment_events = next_traceable_shipment.events
            if len(next_traceable_shipment_events) > 0:
                try:
                    event = next_traceable_shipment.events[0]["event"]
                except KeyError:
                    event = "Unknown"
                try:
                    event_date = next_traceable_shipment.events[0]["date"]
                except KeyError:
                    event_date = "Unknown"
                try:
                    event_location = next_traceable_shipment.events[0]["location"]
                except KeyError:
                    event_location = "Unknown"
            else:
                event = "Unknown"
                event_date = "Unknown"
                event_location = "Unknown"
            try:
                next_delivery_status = DELIVERY_STATUS_CODES[
                    next_traceable_shipment.status_code
                ]
            except:
                next_delivery_status = "Unknown"
            try:
                next_delivery_carrier = carrier_codes[
                    next_traceable_shipment.carrier_code
                ]
            except KeyError:
                next_delivery_carrier = "Unknown"
            # Set the attributes
            self._attr_state = verbose
            self._hass_custom_attributes = {
                "number_of_active_parcels": len(active_shipments),
                "parcels_arriving_today": arriving_today,
                "full_description": description,
                "tracking_number": tracking_number,
                "date_expected": date_expected,
                "days_until_next_delivery": days_until_next_delivery,
                "event": event,
                "event_date": event_date,
                "event_location": event_location,
                "next_delivery_status": next_delivery_status,
                "next_delivery_carrier": next_delivery_carrier,
            }

class CollectionShipment(SensorEntity):
    """Representation of a sensor that reports any parcels currently ready for collection."""

    # Disabled by default
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: ParcelUpdateCoordinator) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._hass_custom_attributes = {}
        self._attr_name = "Parcel Collection Shipment"
        self._attr_unique_id = "Parcel_Collection_Shipment"
        self._globalid = "Parcel_Collection_Shipment"
        self._attr_icon = "mdi:package-up"
        self._attr_state = None

    @property
    def state(self) -> Any:
        """Return the current state of the sensor."""
        return self._attr_state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._hass_custom_attributes

    async def async_update(self) -> None:
        """Fetch the latest data from the coordinator."""
        await self.coordinator.async_request_refresh()
        parcel_api_data = self.coordinator.data
        collectable_shipments = [] 

        if parcel_api_data["deliveries"]:
            data = parcel_api_data["deliveries"]
            for item in data:
                # These are the mandatory properties
                carrier_code = item["carrier_code"]
                description = item["description"]
                status_code = item["status_code"]
                tracking_number = item["tracking_number"]
                # These are the optional properties
                # Events _should_ be present
                try:
                    events = item["events"]
                except KeyError:
                    events = "None"
                # The collection location _should_ be the location in the latest event
                try:
                    location = events[0]["location"]
                except:
                    location = "Unknown"
                # The collection date/time _should_ be the date in the latest event
                # For this version this will only return the datetime as given by the carrier
                try:
                    delivered = events[0]["date"]
                except:
                    delivered = "Unknown"
                if status_code == 3:
                    new_shipment = {
                        "description": description,
                        "location": location,
                        "delivered": delivered,
                    }
                    collectable_shipments.append(new_shipment)
            collectables = len(collectable_shipments)
            self._attr_state = collectables
            icon = "mdi:package-up"
            if 0 < collectables < 10:
                icon = "mdi:numeric-" + str(collectables) + "-circle"
            elif 10 <= collectables:
                icon = "mdi:numeric-9-plus-circle"
            self._attr_icon = icon
            self._hass_custom_attributes = {                
                "collectable_shipments": collectable_shipments,
            }

class RawShipmentData(SensorEntity):
    """Representation of a sensor that fetches the raw data from the API."""

    # Disabled by default
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: ParcelUpdateCoordinator) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._hass_custom_attributes = {}
        self._attr_name = "Parcel Raw Shipment Data"
        self._attr_unique_id = "Parcel_Raw_Shipment_Data"
        self._globalid = "Parcel_Raw_Shipment_Data"
        self._attr_icon = "mdi:package-down"
        self._attr_state = None

    @property
    def state(self) -> Any:
        """Return the current state of the sensor."""
        return self._attr_state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._hass_custom_attributes

    async def async_update(self) -> None:
        """Fetch the latest data from the coordinator."""
        await self.coordinator.async_request_refresh()
        parcel_api_data = self.coordinator.data

        if parcel_api_data:
            self._attr_state = parcel_api_data["utc_timestamp"]
            self._hass_custom_attributes = {
                "success": parcel_api_data["success"],
                "deliveries": parcel_api_data["deliveries"],
                "carrier_codes_updated": parcel_api_data["carrier_codes_updated"],
                "utc_timestamp": parcel_api_data["utc_timestamp"],
            }
