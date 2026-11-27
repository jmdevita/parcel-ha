"""Utilities for ParcelApp"""

import re
import warnings
from datetime import datetime, timedelta, date
from dateutil.parser import parse, UnknownTimezoneWarning

def dateparse(input_date_raw):
    # May need to introduce timezone parsing to avoid an exception in dateutil.parser
    """Try to parse a date/datetime and return a date."""
    today = date.today()
    try:
        date_converted = datetime.fromisoformat(
            input_date_raw
        )
    except (ValueError, TypeError, AttributeError):
        try:
            # Extra loop in case of double spacing in the reported date string and removing any time window
            input_date_raw_truncated = input_date_raw.replace("  "," ")[:19]
            date_converted = datetime.fromisoformat(
                input_date_raw_truncated
            )
            if date_converted is datetime:
                date_converted = date_converted.date()
        except (ValueError, TypeError, AttributeError):
            try:
                # If it's not in ISO format, try to parse it with dateutil and try for the day being first
                    date_expected_dayfirst = parse(input_date_raw,dayfirst=True,fuzzy=True)
                    date_expected_dayfirst = date_expected_dayfirst.date()
            except (ValueError, TypeError, AttributeError, OverflowError):
                # If this fails, set this attempt to a static value
                date_expected_dayfirst = date(1970,1,1)
            try:
                # Now try again with month first
                date_expected_monthfirst = parse(input_date_raw,dayfirst=False,fuzzy=True)
                date_expected_monthfirst = date_expected_monthfirst.date()
            except (ValueError, TypeError, AttributeError, OverflowError):
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


# Fixed-offset zones for the abbreviations carriers commonly append to event
# dates (e.g. "May 13, 2025 01:31 PM EST"). dateutil handles UTC/GMT/Z itself.
_TZ_ABBREVIATIONS = {
    "EST": -5 * 3600,
    "EDT": -4 * 3600,
    "CST": -6 * 3600,
    "CDT": -5 * 3600,
    "MST": -7 * 3600,
    "MDT": -6 * 3600,
    "PST": -8 * 3600,
    "PDT": -7 * 3600,
    "AKST": -9 * 3600,
    "AKDT": -8 * 3600,
    "HST": -10 * 3600,
    "CET": 1 * 3600,
    "CEST": 2 * 3600,
    "BST": 1 * 3600,
    "AEST": 10 * 3600,
    "AEDT": 11 * 3600,
    "ACST": int(9.5 * 3600),
    "ACDT": int(10.5 * 3600),
    "AWST": 8 * 3600,
    "NZST": 12 * 3600,
    "NZDT": 13 * 3600,
    "JST": 9 * 3600,
    "KST": 9 * 3600,
}

# Two defaults that differ in every field, used to tell which fields a string
# actually contained. Both years are leap years so "February 29" parses.
_PROBE_DEFAULT_A = datetime(2000, 1, 1, 0, 0)
# The days are more than a week apart so a weekday name ("Monday, May 2025")
# can't move both to the same day and hide a missing day of the month.
_PROBE_DEFAULT_B = datetime(2004, 2, 15, 1, 1)

# How far past "now" an event may be before it counts as in the future. Allows
# for a carrier reporting local time in a timezone ahead of the HA host.
_FUTURE_SLACK = timedelta(days=1)


_TRAILING_TZ = re.compile(
    r"\b(" + "|".join(_TZ_ABBREVIATIONS) + r")\s*$", re.IGNORECASE
)


def _since(value, now):
    """Return value - now, comparing instants when value has a timezone.

    A naive ``now`` is taken as the HA host's local time; a naive ``value`` is
    the carrier's local time and is compared on the host's calendar.
    """
    if value.tzinfo is not None:
        now_aware = now.astimezone() if now.tzinfo is None else now
        return value - now_aware
    if now.tzinfo is not None:
        now = now.astimezone().replace(tzinfo=None)
    return value - now


def _parse_candidate(input_date_raw, dayfirst, now):
    """Parse one interpretation of an event date. Return (value, has_time) or None."""
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", UnknownTimezoneWarning)
            probe_a = parse(
                input_date_raw,
                dayfirst=dayfirst,
                fuzzy=True,
                default=_PROBE_DEFAULT_A,
                tzinfos=_TZ_ABBREVIATIONS,
            )
            probe_b = parse(
                input_date_raw,
                dayfirst=dayfirst,
                fuzzy=True,
                default=_PROBE_DEFAULT_B,
                tzinfos=_TZ_ABBREVIATIONS,
            )
    except (ValueError, OverflowError, TypeError):
        return None

    # A named timezone we can't resolve: publishing the time without it would
    # silently shift it, so treat the value as unreadable (date_raw keeps it).
    if any(issubclass(w.category, UnknownTimezoneWarning) for w in caught):
        return None

    # A string without a month or day ("10:33", "Today") is not a usable date.
    if probe_a.month != probe_b.month or probe_a.day != probe_b.day:
        return None

    # An hour means a time was given; probe A fills a missing minute with 0.
    has_time = probe_a.hour == probe_b.hour
    year_missing = probe_a.year != probe_b.year

    value = probe_a
    if year_missing:
        # Carriers like USPS and Amazon omit the year. Events are in the past,
        # so take the latest year that doesn't put the event in the future.
        # Next year is included for events near New Year in a timezone ahead
        # of the HA host; invalid dates (Feb 29) are skipped.
        options = []
        for year in (now.year + 1, now.year, now.year - 1, now.year - 2):
            try:
                options.append(probe_a.replace(year=year))
            except ValueError:
                continue
        options = [o for o in options if _since(o, now) <= _FUTURE_SLACK]
        if not options:
            return None
        value = options[0]

    return value, has_time


def normalize_event_date(input_date_raw, now=None):
    """Convert a carrier event date string to an ISO 8601 string.

    Carriers report event dates in their own formats, for example
    "Tuesday, May 13 1:31 PM", "May 13, 2025 13:31" or "13.05.2025 13:31".
    This returns "2025-05-13T13:31:00" (with an offset when the source named a
    timezone), "2025-05-13" when the source has no time of day, or None when
    the value cannot be read as a date.
    """
    if not isinstance(input_date_raw, str) or not input_date_raw.strip():
        return None
    input_date_raw = " ".join(input_date_raw.split())
    # dateutil only recognizes upper-case zone names; "est" would be skipped.
    input_date_raw = _TRAILING_TZ.sub(lambda m: m.group(1).upper(), input_date_raw)
    if now is None:
        now = datetime.now()

    try:
        return date.fromisoformat(input_date_raw).isoformat()
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(input_date_raw).isoformat()
    except ValueError:
        pass

    candidates = [
        result
        for dayfirst in (False, True)
        if (result := _parse_candidate(input_date_raw, dayfirst, now)) is not None
    ]
    if not candidates:
        return None

    # When month-first and day-first readings disagree (e.g. "03.04.2025"),
    # prefer one in the past, then one at most _FUTURE_SLACK ahead, then the
    # one closest to now.
    def rank(candidate):
        since = _since(candidate[0], now)
        return (since > _FUTURE_SLACK, since > timedelta(0), abs(since))

    value, has_time = min(candidates, key=rank)
    if not has_time:
        return value.date().isoformat()
    return value.isoformat()
