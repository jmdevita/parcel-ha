"""Utilities for ParcelApp"""

from datetime import datetime, timedelta, date


def dateparse(input_date_raw):
    """Try to parse a date/datetime and return a date."""
    try:
        date_converted = datetime.fromisoformat(
            input_date_raw
        )
        if date_converted is datetime:
            date_converted = date_converted.date()
    except:
        try:
            # Extra loop in case of double spacing in the reported date string and removing any time window
            input_date_raw = input_date_raw.replace("  "," ")[:19]
            date_converted = datetime.fromisoformat(
                input_date_raw
            )
            if date_converted is datetime:
                date_converted = date_converted.date()
        except KeyError:
            date_converted = None
    return date_converted