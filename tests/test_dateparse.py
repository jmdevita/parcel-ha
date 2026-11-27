"""Tests for utils.dateparse fallback parsing."""

from datetime import date

import pytest

from custom_components.parcelapp import utils


@pytest.fixture
def today(monkeypatch):
    """Pin date.today() inside utils to 2025-03-06."""

    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2025, 3, 6)

    monkeypatch.setattr(utils, "date", FixedDate)
    return FixedDate.today()


def test_month_first_date_used_when_day_first_reading_is_far_off(today):
    """US-style 03/04/2025 is 4 March (2 days ago), not 3 April (4 weeks away)."""
    assert utils.dateparse("03/04/2025 10:00 AM") == date(2025, 3, 4)


def test_day_first_date_used_when_month_first_reading_is_far_off(today):
    """European-style 04.03.2025 is 4 March, not 3 April."""
    assert utils.dateparse("04.03.2025 10:00") == date(2025, 3, 4)


def test_unreadable_date_returns_none(today):
    assert utils.dateparse("not a date") is None


def test_overflowing_number_returns_none(today):
    """dateutil raises OverflowError for huge numbers; that must not crash the sensor."""
    assert utils.dateparse("99999999999999999999") is None
