"""Tests for identifier validation and list parsing."""

from __future__ import annotations

import pytest

from equasis_cli.exceptions import InvalidInputError
from equasis_cli.validation import (
    imo_check_digit_valid,
    normalize_company_id,
    normalize_imo,
    normalize_mmsi,
    parse_list,
    split_values,
)


@pytest.mark.parametrize("value", ["9811000", " 9811000 ", "IMO 9811000", "imo:9811000"])
def test_normalize_imo_accepts_common_forms(value: str) -> None:
    assert normalize_imo(value) == "9811000"


@pytest.mark.parametrize("value", ["981100", "98110000", "EVER GIVEN", ""])
def test_normalize_imo_rejects_malformed_values(value: str) -> None:
    with pytest.raises(InvalidInputError):
        normalize_imo(value)


@pytest.mark.parametrize(
    ("imo", "valid"), [("9811000", True), ("9074729", True), ("9074728", False), ("abc", False)]
)
def test_imo_check_digit(imo: str, valid: bool) -> None:
    assert imo_check_digit_valid(imo) is valid


def test_company_id_and_mmsi() -> None:
    assert normalize_company_id("0310062") == "0310062"
    assert normalize_mmsi("353136000") == "353136000"
    with pytest.raises(InvalidInputError):
        normalize_company_id("TORM")
    with pytest.raises(InvalidInputError):
        normalize_mmsi("3531360")


def test_parse_list_handles_comments_blanks_and_duplicates() -> None:
    lines = ["# fleet list", "9811000  # EVER GIVEN", "", "  9074729", "9811000"]
    assert parse_list(lines) == ["9811000", "9074729"]


def test_split_values_flattens_comma_separated_input() -> None:
    assert split_values(["9811000,9074729", " 9811000 "]) == ["9811000", "9074729"]
