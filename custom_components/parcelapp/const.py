"""Constants for the Parcel integration."""

DOMAIN = "parcelapp"
PARCEL_URL = "https://api.parcel.app/external/deliveries/"
UPDATE_INTERVAL_SECONDS = 300  # RATE LIMIT IS 20 PER HOUR
CARRIER_CODE_ENDPOINT = "https://api.parcel.app/external/supported_carriers.json"
DELIVERY_STATUS_CODES = {
    -1: "None",
    0: "Completed delivery.",
    1: "Frozen delivery. There were no updates for a long time or something else makes the app believe that it will never be updated in the future.",
    2: "Delivery in transit.",
    3: "Delivery expecting a pickup by the recipient.",
    4: "Out for delivery.",
    5: "Delivery not found.",
    6: "Failed delivery attempt.",
    7: "Delivery exception, something is wrong and requires your attention.",
    8: "Carrier has received information about a package, but has not physically received it yet.",
}
RETURN_CODES = {
    -1: "No active parcels.",
    -2: "Active parcel(s) but no ETA.",
    -3: "Error",
}


class Shipment:
    """Representation of a shipment as per the ParcelApp API."""

    def __init__(
        self,
        carrier_code="carrier_code",
        description="description",
        status_code=5,
        tracking_number="tracking_number",
        extra_information=None,
        date_expected=None,
        date_expected_end=None,
        timestamp_expected=None,
        timestamp_expected_end=None,
        events=[],
    ):
        self.carrier_code = carrier_code
        self.description = description
        self.status_code = status_code
        self.tracking_number = tracking_number
        self.extra_information = extra_information
        self.date_expected = date_expected
        self.date_expected_end = date_expected_end
        self.timestamp_expected = timestamp_expected
        self.timestamp_expected_end = timestamp_expected_end
        self.events = events


EMPTY_SHIPMENT = Shipment(
    carrier_code="none",
    description="None",
    status_code=-1,
    tracking_number="None",
    extra_information=None,
    date_expected="None",
    date_expected_end=None,
    timestamp_expected=None,
    timestamp_expected_end=None,
    events=[{"event": "None", "date": "None", "location": "None"}],
)
EMPTY_ATTRIBUTES = {
    "number_of_active_parcels": 0,
    "parcels_arriving_today": 0,
    "full_description": "No description",
    "tracking_number": "None",
    "date_expected": "None",
    "days_until_next_delivery": "No active parcels.",
    "event": "None",
    "event_date": "None",
    "event_location": "None",
    "next_delivery_status": "None",
    "next_delivery_carrier": "None",
}
PARCEL_NAME = "parcel_name"
TRACKING_NUMBER = "tracking_number"
COURIER = "courier"
