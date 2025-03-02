Parcel Integration for Home Assistant
=====================================

This is an unofficial integration for Home Assistant that allows you to track your parcels using the Parcel REST API. This integration fetches the latest shipment data and displays it as a sensor in Home Assistant. This requires a pro account, which costs $5/year.

Features
--------

-   Track recent parcel shipments
-   Display shipment details such as description, tracking number, status code, carrier code, event date, and event location
-   Automatically updates the shipment data at a 5 minute interval.

Installation
------------

### HACS (Home Assistant Community Store)

1.  Ensure that you have HACS installed in your Home Assistant instance.
2.  Add this repository to HACS as a custom repository.
3.  Search for "Parcel (Unofficial)" in HACS and install it.

### Manual Installation

1.  Download the latest release of this integration from the GitHub repository.
2.  Extract the downloaded archive and copy the [parcel](/custom_components/parcel/) directory to your Home Assistant's **custom_components** directory.

Configuration
-------------

### Adding the Integration

1.  In Home Assistant, navigate to **Configuration** > **Devices & Services**.
2.  Click on **Add Integration** and search for "Parcel".
3.  Follow the prompts to enter your Parcel API key.

### Configuration Options

You can configure the integration options by navigating to **Configuration** > **Devices & Services**, selecting the Parcel integration, and clicking on **Options**.

Usage
-----

Once the integration is set up, it will create a sensor entity named sensor.recent_parcel_shipment. This sensor will display the most recent shipment event and provide additional attributes with detailed information about the shipment.

### Sensor Attributes
-   `full_description`: Full description of the shipment
-   `tracking_number`: Tracking number of the shipment
-   `status_code`: Status code of the shipment
-   `carrier_code`: Carrier code of the shipment
-   `event_date`: Date of the shipment event
-   `event_location`: Location of the shipment event

Example Automation
------------------

You can create automations in Home Assistant to notify you of shipment updates. Here is an example automation that sends a notification when a new shipment event is detected:

```yaml
automation:

  - alias: Notify on New Parcel Shipment Event

    trigger:

      platform: state

      entity_id: sensor.recent_parcel_shipment

    action:

      service: notify.notify

      data:

        title: "New Parcel Shipment Event"

        message: >

          Shipment {{ state_attr('sensor.recent_parcel_shipment', 'full_description') }} has a new event:

          {{ state_attr('sensor.recent_parcel_shipment', 'event_date') }} - {{ state_attr('sensor.recent_parcel_shipment', 'event_location') }} - {{ states('sensor.recent_parcel_shipment') }}
```

Development
-----------

### Prerequisites

-   Home Assistant
-   HACS

### Running Tests

To run the tests for this integration, use the following command:
```zsh
pytest tests
```
Contributing
------------

Contributions are welcome! Please open an issue or submit a pull request on the [GitHub repository](/).

License
-------

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](/LICENSE) file for details.

Support
-------

If you encounter any issues or have questions, please open an issue on the [GitHub repository](/).

Acknowledgements
----------------

This integration uses the Parcel REST API. Special thanks to the developer of the Parcel API for providing this service.

* * * * *

**Note:** This integration is unofficial and not affiliated with the Parcel API developers. Use it at your own risk.