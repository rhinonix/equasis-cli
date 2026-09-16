"""Validation and normalization of user-supplied identifiers and input lists."""

from __future__ import annotations

import re
from collections.abc import Iterable

from .exceptions import InvalidInputError

_IMO = re.compile(r"^(?:IMO[\s:-]*)?(\d{7})$", re.IGNORECASE)
_COMPANY_ID = re.compile(r"^\d{7}$")
_MMSI = re.compile(r"^\d{9}$")


def normalize_imo(value: str) -> str:
    """Return the 7-digit IMO number in ``value`` (``"IMO 9811000"`` is accepted).

    Raises:
        InvalidInputError: if ``value`` is not a 7-digit number.
    """
    match = _IMO.match(value.strip())
    if not match:
        raise InvalidInputError(f"'{value}' is not a valid IMO number (expected 7 digits)")
    return match.group(1)


def imo_check_digit_valid(imo: str) -> bool:
    """Verify the IMO check digit.

    The first six digits are multiplied by 7, 6, 5, 4, 3 and 2; the last digit of
    the sum must equal the seventh digit. A failure usually indicates a typo.
    """
    if not (len(imo) == 7 and imo.isdigit()):
        return False
    total = sum(int(digit) * weight for digit, weight in zip(imo[:6], range(7, 1, -1), strict=True))
    return total % 10 == int(imo[6])


def normalize_company_id(value: str) -> str:
    """Return a 7-digit Equasis company number.

    Raises:
        InvalidInputError: if ``value`` is not a 7-digit number.
    """
    cleaned = value.strip()
    if not _COMPANY_ID.match(cleaned):
        raise InvalidInputError(
            f"'{value}' is not a valid Equasis company number (expected 7 digits)"
        )
    return cleaned


def normalize_mmsi(value: str) -> str:
    """Return a 9-digit MMSI.

    Raises:
        InvalidInputError: if ``value`` is not a 9-digit number.
    """
    cleaned = value.strip()
    if not _MMSI.match(cleaned):
        raise InvalidInputError(f"'{value}' is not a valid MMSI (expected 9 digits)")
    return cleaned


def parse_list(lines: Iterable[str]) -> list[str]:
    """Parse list input: one item per line, ``#`` comments, blank lines ignored.

    Inline comments are supported (``9811000  # EVER GIVEN``). Duplicates are
    removed while preserving order.
    """
    items: list[str] = []
    seen: set[str] = set()
    for line in lines:
        item = line.split("#", 1)[0].strip()
        if item and item not in seen:
            seen.add(item)
            items.append(item)
    return items


def split_values(values: Iterable[str]) -> list[str]:
    """Flatten values that may themselves be comma-separated lists."""
    return parse_list(part for value in values for part in value.split(","))
