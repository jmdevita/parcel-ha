"""Tests for carrier auto-detection module."""

import json
from pathlib import Path

import pytest

from custom_components.parcelapp.carrier_detection import (
    CarrierDetector,
    CarrierMatch,
    JKEEN_TO_PARCEL_APP_MAP,
    TRACKING_DATA_DIR,
    EXCLUDED_COURIERS,
    _checksum_mod10,
    _checksum_mod7,
    _checksum_s10,
    _checksum_sum_product,
    _checksum_luhn,
    _checksum_mod_37_36,
    _char_to_digit,
)


@pytest.fixture
def detector():
    """Create and load a CarrierDetector."""
    d = CarrierDetector()
    d.load()
    return d


def _load_test_numbers():
    """Load all valid/invalid test numbers from tracking data JSON files."""
    valid_cases = []
    invalid_cases = []

    for json_file in sorted(TRACKING_DATA_DIR.glob("*.json")):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        courier_code = data.get("courier_code", "")
        if courier_code in EXCLUDED_COURIERS:
            continue

        for tn in data.get("tracking_numbers", []):
            test_nums = tn.get("test_numbers", {})
            fmt_name = tn.get("name", "unknown")
            for num in test_nums.get("valid", []):
                valid_cases.append((courier_code, fmt_name, num))
            for num in test_nums.get("invalid", []):
                invalid_cases.append((courier_code, fmt_name, num))

    return valid_cases, invalid_cases


VALID_CASES, INVALID_CASES = _load_test_numbers()


class TestChecksums:
    """Test individual checksum algorithms."""

    def test_char_to_digit(self):
        # (ord - 3) % 10 for letters
        assert _char_to_digit("R") == 9  # (82-3)%10 = 9
        assert _char_to_digit("A") == 2  # (65-3)%10 = 2
        assert _char_to_digit("Z") == 7  # (90-3)%10 = 7
        assert _char_to_digit("5") == 5

    def test_mod10_ups(self):
        # 1Z5R89390357567127 -> serial "5R89390357567I2", check digit 7
        # UPS mod10: evens=1, odds=2, no digit splitting
        assert _checksum_mod10("5R8939035756712", 7, 1, 2) is True

    def test_mod7_dhl(self):
        # 3318810025 -> serial "331881002", check 5
        assert _checksum_mod7("331881002", 5) is True
        assert _checksum_mod7("331881002", 4) is False

    def test_s10(self):
        # RB123456785GB -> serial 12345678, check 5
        assert _checksum_s10([1, 2, 3, 4, 5, 6, 7, 8], 5) is True
        assert _checksum_s10([1, 2, 3, 4, 5, 6, 7, 8], 6) is False

    def test_sum_product_fedex_12(self):
        # 986578788855 -> serial 98657878885, check 5
        assert (
            _checksum_sum_product(
                [9, 8, 6, 5, 7, 8, 7, 8, 8, 8, 5],
                5,
                [3, 1, 7, 3, 1, 7, 3, 1, 7, 3, 1],
                11,
                10,
            )
            is True
        )

    def test_luhn_old_dominion(self):
        # 07209562763 -> serial "0720956276", check 3
        assert _checksum_luhn("0720956276", 3) is True
        assert _checksum_luhn("0720956277", 3) is False

    def test_mod_37_36_dpd(self):
        # 008182709980000020033350276C
        assert _checksum_mod_37_36("008182709980000020033350276", "C") is True


class TestDetectorLoading:
    """Test that the detector loads patterns correctly."""

    def test_loads_patterns(self, detector):
        assert len(detector._patterns) > 0

    def test_excludes_s10(self, detector):
        codes = {p.courier_code for p in detector._patterns}
        assert "s10" not in codes

    def test_includes_major_carriers(self, detector):
        codes = {p.courier_code for p in detector._patterns}
        assert "ups" in codes
        assert "fedex" in codes
        assert "usps" in codes
        assert "dhl" in codes

    def test_idempotent_load(self, detector):
        count = len(detector._patterns)
        detector.load()
        assert len(detector._patterns) == count


class TestDetection:
    """Test carrier detection from tracking numbers."""

    def test_ups_1z(self, detector):
        matches = detector.detect("1Z5R89390357567127")
        assert len(matches) >= 1
        assert matches[0].courier_code == "ups"
        assert matches[0].checksum_valid is True
        assert matches[0].confidence == 1.0

    def test_ups_waybill(self, detector):
        matches = detector.detect("K2479825491")
        ups_matches = [m for m in matches if m.courier_code == "ups"]
        assert len(ups_matches) >= 1
        assert ups_matches[0].checksum_valid is True

    def test_fedex_12(self, detector):
        matches = detector.detect("986578788855")
        fedex_matches = [m for m in matches if m.courier_code == "fedex"]
        assert len(fedex_matches) >= 1
        assert any(m.checksum_valid for m in fedex_matches)

    def test_usps_22(self, detector):
        matches = detector.detect("9400111206206406260787")
        usps_matches = [m for m in matches if m.courier_code == "usps"]
        assert len(usps_matches) >= 1

    def test_dhl_express(self, detector):
        matches = detector.detect("3318810025")
        dhl_matches = [m for m in matches if m.courier_code == "dhl"]
        assert len(dhl_matches) >= 1
        assert any(m.checksum_valid for m in dhl_matches)

    def test_amazon_tba(self, detector):
        matches = detector.detect("TBA000000000000")
        amazon_matches = [m for m in matches if m.courier_code == "amazon"]
        assert len(amazon_matches) >= 1

    def test_ontrac_c(self, detector):
        matches = detector.detect("C11031500001879")
        ontrac_matches = [m for m in matches if m.courier_code == "ontrac"]
        assert len(ontrac_matches) >= 1
        assert any(m.checksum_valid for m in ontrac_matches)

    def test_no_match_garbage(self, detector):
        matches = detector.detect("XXXXXXXXX")
        assert len(matches) == 0

    def test_no_match_empty(self, detector):
        matches = detector.detect("")
        assert len(matches) == 0

    def test_parcel_app_code_mapping(self, detector):
        matches = detector.detect("1Z5R89390357567127")
        assert matches[0].parcel_app_code == "ups"

    def test_results_sorted_by_confidence(self, detector):
        # Use a number that might match multiple patterns
        matches = detector.detect("986578788855")
        if len(matches) > 1:
            for i in range(len(matches) - 1):
                assert matches[i].confidence >= matches[i + 1].confidence

    def test_strips_whitespace_in_tracking_number(self, detector):
        # UPS with spaces should still match
        matches = detector.detect(" 1 Z 8 V 9 2 A 7 0 3 6 7 2 0 3 0 2 4 ")
        ups_matches = [m for m in matches if m.courier_code == "ups"]
        assert len(ups_matches) >= 1


class TestValidNumbers:
    """Parametrized tests using valid test numbers from jkeen data."""

    @pytest.mark.parametrize(
        "courier_code,format_name,tracking_number",
        VALID_CASES,
        ids=[f"{c[0]}/{c[1]}/{c[2][:20]}" for c in VALID_CASES],
    )
    def test_valid_number_detected(self, detector, courier_code, format_name, tracking_number):
        """Each valid test number should be detected as its courier with valid checksum."""
        matches = detector.detect(tracking_number)
        courier_matches = [m for m in matches if m.courier_code == courier_code]
        assert len(courier_matches) >= 1, (
            f"Expected {courier_code}/{format_name} to match {tracking_number!r}, "
            f"but got: {[m.courier_code for m in matches]}"
        )
        # If the format has a checksum, it should be valid
        best = courier_matches[0]
        if best.checksum_valid is not None:
            assert best.checksum_valid is True, (
                f"Checksum failed for {courier_code}/{format_name}: {tracking_number!r}"
            )


class TestInvalidNumbers:
    """Parametrized tests using invalid test numbers from jkeen data."""

    @pytest.mark.parametrize(
        "courier_code,format_name,tracking_number",
        INVALID_CASES,
        ids=[f"{c[0]}/{c[1]}/{c[2][:20]}" for c in INVALID_CASES],
    )
    def test_invalid_number_not_validated(self, detector, courier_code, format_name, tracking_number):
        """Invalid test numbers should either not match or fail checksum."""
        matches = detector.detect(tracking_number)
        courier_matches = [
            m for m in matches if m.courier_code == courier_code and m.checksum_valid is True
        ]
        assert len(courier_matches) == 0, (
            f"Expected {courier_code}/{format_name} to NOT validate {tracking_number!r}, "
            f"but it passed checksum"
        )


class TestCarrierCodeMapping:
    """Test the carrier code mapping is reasonable."""

    def test_all_loaded_couriers_have_mapping(self, detector):
        """Every non-excluded courier in tracking data should have a Parcel app mapping."""
        loaded_codes = {p.courier_code for p in detector._patterns}
        for code in loaded_codes:
            assert code in JKEEN_TO_PARCEL_APP_MAP, (
                f"Courier {code!r} loaded but has no Parcel app mapping"
            )

    def test_mapping_values_are_strings(self):
        for key, val in JKEEN_TO_PARCEL_APP_MAP.items():
            assert isinstance(val, str)
            assert len(val) > 0
