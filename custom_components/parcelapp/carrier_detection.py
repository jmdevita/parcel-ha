"""Carrier auto-detection from tracking numbers.

Uses pattern data from jkeen/tracking_number_data to identify carriers
by matching tracking number formats and validating checksums.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

TRACKING_DATA_DIR = Path(__file__).parent / "tracking_data"

# Maps jkeen courier_code -> Parcel app carrier code.
# s10 is excluded because it's a universal postal format covering 160+ countries.
JKEEN_TO_PARCEL_APP_MAP: dict[str, str] = {
    "ups": "ups",
    "fedex": "fedex",
    "usps": "usps",
    "dhl": "dhl",
    "ontrac": "ontrac",
    "lasership": "lasership",
    "canada_post": "cp",
    "dpd": "dpd",
    "amazon": "amzlus",
    "landmark": "landmark",
    "old_dominion": "odfl",
}

# Courier files to skip for auto-detection
EXCLUDED_COURIERS = {"s10"}


@dataclass
class CarrierMatch:
    """Result of a carrier detection attempt."""

    courier_code: str
    parcel_app_code: str | None
    carrier_name: str
    format_name: str
    checksum_valid: bool | None
    confidence: float


@dataclass
class _TrackingPattern:
    """Compiled tracking number pattern with validation rules."""

    courier_code: str
    carrier_name: str
    format_name: str
    regex: re.Pattern[str]
    checksum: dict | None
    serial_number_format: dict | None


def _char_to_digit(c: str) -> int:
    """Convert a character to a digit for checksum calculation.

    Digits return their face value. Letters use (ord - 3) % 10,
    matching the jkeen/tracking_number Ruby gem convention.
    """
    if c.isdigit():
        return int(c)
    return (ord(c.upper()) - 3) % 10


def _serial_to_digits(serial: str) -> list[int]:
    """Convert an alphanumeric serial string to a list of digits."""
    return [_char_to_digit(c) for c in serial if c.isalnum()]


def _checksum_mod10(
    serial_chars: str,
    check_digit: int,
    evens_multiplier: int = 1,
    odds_multiplier: int = 2,
    reverse: bool = False,
) -> bool:
    """Validate mod10 checksum.

    Note: this does NOT split multi-digit products (not Luhn-style).
    Raw products are summed directly.
    """
    digits = _serial_to_digits(serial_chars)
    if reverse:
        digits = list(reversed(digits))
    total = 0
    for i, d in enumerate(digits):
        x = d
        if i % 2 == 0:
            x *= evens_multiplier
        else:
            x *= odds_multiplier
        total += x
    remainder = total % 10
    expected = (10 - remainder) if remainder != 0 else 0
    return expected == check_digit


def _checksum_mod7(serial_chars: str, check_digit: int) -> bool:
    """Validate mod7 checksum."""
    digits_only = "".join(c for c in serial_chars if c.isdigit())
    serial_num = int(digits_only)
    return serial_num % 7 == check_digit


def _checksum_s10(serial_digits: list[int], check_digit: int) -> bool:
    """Validate S10 international postal checksum."""
    weights = [8, 6, 4, 2, 3, 5, 9, 7]
    if len(serial_digits) != 8:
        return False
    total = sum(d * w for d, w in zip(serial_digits, weights))
    remainder = total % 11
    if remainder == 0:
        expected = 5
    elif remainder == 1:
        expected = 0
    else:
        expected = 11 - remainder
    return expected == check_digit


def _checksum_sum_product(
    serial_digits: list[int],
    check_digit: int,
    weightings: list[int],
    modulo1: int,
    modulo2: int,
) -> bool:
    """Validate weighted sum-product checksum with dual modulo."""
    total = sum(d * w for d, w in zip(serial_digits, weightings))
    expected = (total % modulo1) % modulo2
    return expected == check_digit


def _checksum_luhn(serial_chars: str, check_digit: int) -> bool:
    """Validate Luhn checksum.

    Unlike mod10, Luhn DOES subtract 9 from doubled values > 9.
    Processes the serial in reverse, doubling even-indexed positions.
    """
    digits = [int(c) for c in serial_chars if c.isdigit()]
    total = 0
    for i, d in enumerate(reversed(digits)):
        x = d
        if i % 2 == 0:
            x *= 2
        if x > 9:
            x -= 9
        total += x
    remainder = total % 10
    expected = (10 - remainder) if remainder != 0 else 0
    return expected == check_digit


def _checksum_mod_37_36(serial_chars: str, check_char: str) -> bool:
    """Validate ISO 7064 mod 37/36 checksum (alphanumeric).

    Based on DPD Parcel Label Specification, matching jkeen Ruby implementation.
    """
    weights = {chr(i + ord("A")): i + 10 for i in range(26)}  # A=10..Z=35
    mod = 36

    cd = mod
    for ch in serial_chars:
        if ch.isalpha():
            val = weights[ch.upper()]
        else:
            val = int(ch)

        cd = val + cd
        if cd > mod:
            cd -= mod
        cd = cd * 2
        if cd > mod + 1:
            cd -= mod + 1

    cd = (mod + 1) - cd
    if cd == mod:
        cd = 0

    # Convert computed check to character
    if cd >= 10:
        computed = chr(ord("A") + cd - 10)
    else:
        computed = str(cd)

    return computed == check_char.upper()


def _extract_digits(text: str) -> list[int]:
    """Extract only digit characters as a list of ints."""
    return [int(c) for c in text if c.isdigit()]


def _compile_regex(regex_input: str | list[str]) -> re.Pattern[str]:
    """Compile a jkeen regex pattern to a Python regex.

    Handles array-of-strings format and converts PCRE named groups to Python syntax.
    """
    raw = "".join(regex_input) if isinstance(regex_input, list) else regex_input
    # Convert (?<Name>...) to (?P<Name>...)
    converted = re.sub(r"\(\?<([^>]+)>", r"(?P<\1>", raw)
    return re.compile(f"^{converted}$", re.IGNORECASE)


def _validate_checksum(
    match: re.Match[str],
    checksum_config: dict,
    serial_number_format: dict | None,
) -> bool:
    """Validate a tracking number's checksum given the match and config."""
    algo = checksum_config.get("name", "")

    serial_group = match.group("SerialNumber")
    check_group = match.group("CheckDigit")
    if not serial_group or not check_group:
        return False

    serial_clean = serial_group.replace(" ", "")
    check_clean = check_group.strip()

    # Handle serial_number_format.prepend_if
    if serial_number_format and "prepend_if" in serial_number_format:
        prepend = serial_number_format["prepend_if"]
        prepend_regex = prepend.get("matches_regex", "")
        prepend_content = prepend.get("content", "")
        if prepend_regex and re.match(prepend_regex, serial_clean):
            serial_clean = prepend_content + serial_clean

    if algo == "mod10":
        check_digit = int(check_clean[0])
        return _checksum_mod10(
            serial_clean,
            check_digit,
            evens_multiplier=checksum_config.get("evens_multiplier", 1),
            odds_multiplier=checksum_config.get("odds_multiplier", 2),
            reverse=checksum_config.get("reverse", False),
        )

    if algo == "mod7":
        check_digit = int(check_clean[0])
        return _checksum_mod7(serial_clean, check_digit)

    if algo == "s10":
        serial_digits = _extract_digits(serial_clean)
        check_digit = int(check_clean[0])
        return _checksum_s10(serial_digits, check_digit)

    if algo == "sum_product_with_weightings_and_modulo":
        serial_digits = _extract_digits(serial_clean)
        check_digit = int(check_clean[0])
        return _checksum_sum_product(
            serial_digits,
            check_digit,
            weightings=checksum_config.get("weightings", []),
            modulo1=checksum_config.get("modulo1", 10),
            modulo2=checksum_config.get("modulo2", 10),
        )

    if algo == "luhn":
        check_digit = int(check_clean[0])
        return _checksum_luhn(serial_clean, check_digit)

    if algo == "mod_37_36":
        # Serial includes digits and the check char is alphanumeric
        serial_alnum = re.sub(r"\s", "", serial_clean)
        return _checksum_mod_37_36(serial_alnum, check_clean[0])

    _LOGGER.debug("Unknown checksum algorithm: %s", algo)
    return False


class CarrierDetector:
    """Detects carrier from tracking number using jkeen/tracking_number_data patterns."""

    def __init__(self) -> None:
        self._patterns: list[_TrackingPattern] = []
        self._loaded = False

    def load(self) -> None:
        """Load all tracking data JSON files from the bundled data directory."""
        if self._loaded:
            return

        for json_file in sorted(TRACKING_DATA_DIR.glob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as err:
                _LOGGER.warning("Failed to load tracking data from %s: %s", json_file.name, err)
                continue

            courier_code = data.get("courier_code", "")
            if courier_code in EXCLUDED_COURIERS:
                continue

            carrier_name = data.get("name", courier_code)

            for tn in data.get("tracking_numbers", []):
                regex_input = tn.get("regex")
                if not regex_input:
                    continue

                try:
                    compiled = _compile_regex(regex_input)
                except re.error as err:
                    _LOGGER.warning(
                        "Failed to compile regex for %s/%s: %s",
                        courier_code,
                        tn.get("name", "unknown"),
                        err,
                    )
                    continue

                validation = tn.get("validation", {})
                checksum = validation.get("checksum")
                serial_number_format = validation.get("serial_number_format")

                self._patterns.append(
                    _TrackingPattern(
                        courier_code=courier_code,
                        carrier_name=carrier_name,
                        format_name=tn.get("name", "Unknown"),
                        regex=compiled,
                        checksum=checksum,
                        serial_number_format=serial_number_format,
                    )
                )

        self._loaded = True
        _LOGGER.debug("Loaded %d tracking number patterns", len(self._patterns))

    def detect(self, tracking_number: str) -> list[CarrierMatch]:
        """Detect carrier(s) for a tracking number.

        Returns matches sorted by confidence (highest first).
        """
        results: list[CarrierMatch] = []

        for pattern in self._patterns:
            match = pattern.regex.match(tracking_number)
            if not match:
                continue

            checksum_valid: bool | None = None
            confidence = 0.5  # regex match only

            if pattern.checksum:
                try:
                    checksum_valid = _validate_checksum(
                        match, pattern.checksum, pattern.serial_number_format
                    )
                    confidence = 1.0 if checksum_valid else 0.3
                except (ValueError, IndexError, KeyError) as err:
                    _LOGGER.debug(
                        "Checksum validation error for %s/%s: %s",
                        pattern.courier_code,
                        pattern.format_name,
                        err,
                    )
                    confidence = 0.4

            results.append(
                CarrierMatch(
                    courier_code=pattern.courier_code,
                    parcel_app_code=JKEEN_TO_PARCEL_APP_MAP.get(pattern.courier_code),
                    carrier_name=pattern.carrier_name,
                    format_name=pattern.format_name,
                    checksum_valid=checksum_valid,
                    confidence=confidence,
                )
            )

        results.sort(key=lambda m: m.confidence, reverse=True)
        return results
