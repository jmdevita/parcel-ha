"""Utilities for ParcelApp"""

from datetime import datetime, timedelta, date
from dateutil.parser import parse

def dateparse(input_date_raw):
    # May need to introduce timezone parsing to avoid an exception in dateutil.parser
    """Try to parse a date/datetime and return a date."""
    today = date.today()
    try:
        date_converted = datetime.fromisoformat(
            input_date_raw
        )
    except:
        try:
            # Extra loop in case of double spacing in the reported date string and removing any time window
            input_date_raw_truncated = input_date_raw.replace("  "," ")[:19]
            date_converted = datetime.fromisoformat(
                input_date_raw_truncated
            )
            if date_converted is datetime:
                date_converted = date_converted.date()
        except:
            try:
                # If it's not in ISO format, try to parse it with dateutil and try for the day being first
                    date_expected_dayfirst = parse(input_date_raw,dayfirst=True,fuzzy=True)
                    date_expected_dayfirst = date_expected_dayfirst.date()
            except:
                # If this fails, set this attempt to a static value
                date_expected_dayfirst = date(1970,1,1)
            try:
                # Now try again with month first
                date_expected_monthfirst = parse(input_date_raw,monthfirst=True,fuzzy=True)
                date_expected_monthfirst = date_expected_monthfirst.date()
            except:
                # Again, if this fails, set to a static value
                date_expected_monthfirst = date(1970,1,1)
            # Next, if either of the attempts are TODAY, assume the parcel has been delivered today. Delivered parcels aren't included for long
            if (date_expected_dayfirst == today) or (date_expected_monthfirst == today):
                date_converted = today
            # If this isn't true, then check to see if either date is within 7 days, if so, then that's probably the correct date.
            elif date_expected_dayfirst + timedelta(days=-7) <= today <= date_expected_dayfirst + timedelta(days=7):
                date_converted = date_expected_dayfirst
            elif date_expected_monthfirst + timedelta(days=-7) <= today <= date_expected_monthfirst + timedelta(days=7):
                date_converted = date_expected_monthfirst
            # If none of this returns a reasonable date, give up.
            else:
                date_converted = None
    if type(date_converted) is datetime:
            date_converted = date_converted.date()
    return date_converted