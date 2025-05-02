[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![GH-release](https://img.shields.io/github/v/release/jmdevita/parcel-ha)](https://github.com/jmdevita/parcel-ha/releases)
[![GH-downloads](https://img.shields.io/github/downloads/jmdevita/parcel-ha/total)](https://github.com/jmdevita/parcel-ha/releases)
![GH-stars](https://img.shields.io/github/stars/jmdevita/parcel-ha?style=flat-square)
\
[![Python package](https://github.com/jmdevita/parcel-ha/actions/workflows/pythonpackage.yaml/badge.svg?branch=main)](https://github.com/jmdevita/parcel-ha/actions/workflows/pythonpackage.yaml)
[![Validate with hassfest](https://github.com/jmdevita/parcel-ha/actions/workflows/hassfest.yaml/badge.svg?branch=main)](https://github.com/jmdevita/parcel-ha/actions/workflows/hassfest.yaml)
[![HACS Action](https://github.com/jmdevita/parcel-ha/actions/workflows/validate.yaml/badge.svg?branch=main)](https://github.com/jmdevita/parcel-ha/actions/workflows/validate.yaml)
[![Latest Commit](https://badgen.net/github/last-commit/jmdevita/parcel-ha/main)](https://github.com/jmdevita/parcel-ha/commit/HEAD)

Parcel App Integration for Home Assistant
=====================================

This is an integration for Home Assistant that allows you to track your parcels using the [Parcel REST API](https://web.parcelapp.net/#apiPanel). This integration fetches the latest shipment data and displays it as a sensor in Home Assistant. This does require a pro account, but only costs $5/year.

Features
--------

-   Track most recent parcel shipments
-   Display shipment details such as description, tracking number, status code, carrier code, event date, and event location
-   Automatically updates the shipment data at a 5 minute interval.

Installation
------------

### HACS (Home Assistant Community Store)
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jmdevita&repository=parcel-ha&category=Integration)

### Other ways to Install

1.  Ensure that you have HACS installed in your Home Assistant instance.
2.  Add this repository to HACS as a custom repository.
3.  Search for "Parcel" in HACS and install it.

Configuration
-------------

### Adding the Integration

1.  In Home Assistant, navigate to **Configuration** > **Devices & Services**.
2.  Click on **Add Integration** and search for "Parcel".
3.  Follow the prompts to enter your Parcel API key. You can find your key [here](https://web.parcelapp.net/#apiPanel)

### Configuration Options

You can configure the integration options by navigating to **Configuration** > **Devices & Services**, selecting the Parcel integration, and clicking on **Options**.

Usage
-----

Once the integration is set up, it will create a sensor entity named sensor.parcel_recent_shipment. This sensor will display the most recent shipment event and provide additional attributes with detailed information about the shipment.

### Sensor Attributes
-   `full_description`: Full description of the shipment.
-   `tracking_number`: Tracking number of the shipment.
-   `date_expected`: Date the shipment is expected.
-   `event_date`: Date of the latest shipment event.
-   `event_location`: Location of the shipment event.
-   `status`: The converted (from status code) delivery status of the shipment.
-   `carrier`: The converted (from carrier code) carrier name of the shipment.

From v1.0.0 a second sensor entity is added, called sensor.parcel_active_shipment. It's intended to be used to provide information about when the next shipment is due, and how many shipments are currently actively being tracked. It has the following attributes:

### Beta Features (BETA)
This integration includes beta features for adding, editing, and deleting parcels. For more details, refer to the [Beta Features Documentation](docs/parcel_edits_beta.md).

### Sensor Attributes
-   `Number_of_active_parcels`: The number of active shipment being tracked.
-   `parcels_arriving_today`: The number of shipment with an ETA of the current date.
-   `Full description`: Full description of the next shipment.
-   `tracking_number`: Tracking number of the shipment.
-   `date_expected`: Date the shipment is expected.
-   `days_until_next_delivery`: The number of days until the next delivery or text description.
-   `event`: The state of the latest shipment event.
-   `event_date`: Date of the latest shipment event.
-   `event_location`: Location of the shipment event.
-   `next_delivery_status`: The converted (from status code) delivery status of the next shipment arriving.
-   `next_delivery_carrier`: The converted (from carrier code) carrier name of the next shipment arriving.

### Raw Data Sensor
From v1.2.0 another sensor entity is added, called `sensor.parcel_raw_shipment_data`. It contains raw json data from the API pull for debugging or custom templating. It has the following attributes:

#### Raw Data Sensor Attributes
As per the [Parcel App API documentation](https://parcelapp.net/help/api.html)

-   `success` (bool, always provided): Whether a request was successful.
-   `error_message` (string): Provided in case of an error.
-   `deliveries` (array): Requested deliveries.
-   `Utc timestamp`: The time the data in the sensor was last updated

Response Schema for Deliveries Attribute
-  `carrier_code` (string, always provided): Carrier for a delivery, provided as an internal code. Full list (updated daily) is available [here](https://api.parcel.app/external/supported_carriers.json).
-  `description` (string, always provided): Description that was provided for a delivery when it was created.
-  `status_code` (int, always provided): See the "Delivery Status Codes" paragraph below.
-  `tracking_number` (string, always provided): Tracking number for a delivery.
-  `events` (array, always provided): Delivery events. Empty if no data is available.
-  `extra_information` (string): It could be a postcode or an email. Something extra that was required by a carrier to track a delivery.
-  `date_expected` (string): Expected delivery date/time without specific timezone information.
-  `date_expected_end` (string): If provided, that means that a has delivery window for package and this is the end date/time.
-  `timestamp_expected` (int): Epoch time for expected delivery date. Available only when a carrier provides full date/time/timezone for an expected delivery date.
-  `timestamp_expected_end` (int): Similar to date_expected_end, used to indicate the end time for a delivery window.

Response Schema for Delivery Events:
-  `event` (string, always provided): Description of the delivery event.
-  `date` (string, always provided): Delivery date/time info.
-  `location` (string): Location of the delivery event.
-  `additional` (string): Additional information from the carrier related to the delivery event.

Delivery Status Codes:
-  0 - completed delivery.
-  1 - frozen delivery. There were no updates for a long time or something else makes the app believe that it will never be updated in the future.
-  2 - delivery in transit.
-  3 - delivery expecting a pickup by the recipient.
-  4 - out for delivery.
-  5 - delivery not found.
-  6 - failed delivery attempt.
-  7 - delivery exception, something is wrong and requires your attention.
-  8 - carrier has received information about a package, but has not physically received it yet.

The raw data sensor is disabled by default and has to be enabled. To do so, in the integration, click on the "Parcel Raw Shipment Data" entity, click on settings, toggle the "Enabled" setting to "on", click "Update".

## Custom Button Card

If you are familiar with custom button card, one way to use the active_parcel_shipment sensor is with the following button card template:

```
type: custom:button-card
entity: sensor.parcel_active_shipment
name: Parcels
show_name: true
show_icon: true
show_state: true
styles:
  grid:
    - grid-template-areas: '"i n" "i s"'
    - grid-template-columns: auto 1fr
    - grid-template-rows: 12px 12px
  card:
    - padding: 22px 22px 22px 22px
    - height: 150px
    - background: rgba(10,10,10,0.85)
  name:
    - justify-self: end
    - font-size: 18px
    - font-weight: 500
    - color: '#d2ae71'
  state:
    - justify-self: end
    - font-size: 14px
    - opacity: '0.7'
    - padding-top: 12px
    - padding-left: 0px
  img_cell:
    - justify-content: start
    - position: absolute
    - width: 120px
    - height: 120px
    - left: 0
    - bottom: 0
    - margin: 0 0 -20px -20px
    - background: '#d2ae71'
    - border-radius: 500px
  icon:
    - position: relative
    - width: 75px
    - color: black
    - opacity: "0.5"
```

<img src="/docs/images/parcel_button_card.png" alt="Example Button Card" width="250"/>

You may want to modify the dimensions, opacity, etc to suit your tastes.

### Community Cards
Feel free to make a pull request with your template under docs/community_templates !

[Auto-Entities Card](/docs/community_templates/auto_entities.yaml) by @robbinonline
\
<img src="/docs/images/parcel_auto_entities_card.png" alt="Example Bubble Card" width="250"/>

[Bubble Card](/docs/community_templates/bubble_card.yaml) by @georgefahmy
\
<img src="/docs/images/parcel_bubble_card.png" alt="Example Bubble Card" width="250"/>

Development
-----------

### Prerequisites

-   Home Assistant
-   HACS

Contributing
------------

Contributions are welcome! Please open an issue or submit a pull request on the [GitHub repository](https://github.com/jmdevita/parcel-ha/pulls).

License
-------

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](/LICENSE) file for details.

Support
-------

If you encounter any issues or have questions, please open an issue on the [GitHub repository](https://github.com/jmdevita/parcel-ha/issues).

Acknowledgements
----------------

This integration uses the Parcel REST API. Special thanks to the developer of the Parcel API for providing this service.

* * * * *

**Note:** This integration is unofficial and not affiliated with the Parcel API developers.
