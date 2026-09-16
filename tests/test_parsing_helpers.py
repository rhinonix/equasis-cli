"""Tests for the low-level HTML helpers."""

from __future__ import annotations

from datetime import date

import pytest

from equasis_cli.exceptions import LayoutChangedError
from equasis_cli.parsing.html import iter_rows, make_soup, parse_date, parse_float, parse_int


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("since 01/02/2022", date(2022, 2, 1)),
        ("25/09/2018", date(2018, 9, 25)),
        ("2025-01-08", date(2025, 1, 8)),
        ("during 09/2024", date(2024, 9, 1)),
        ("Inception at 25/09/2018", date(2018, 9, 25)),
        ("Last update of ship particulars 15/09/2026", date(2026, 9, 15)),
        ("31/02/2020", None),
        ("", None),
        (None, None),
        ("September 2026", None),
    ],
)
def test_parse_date(text: str | None, expected: date | None) -> None:
    assert parse_date(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [("219079", 219079), ("1,234", 1234), (" 8 ", 8), ("", None), ("N/A", None)],
)
def test_parse_int(text: str, expected: int | None) -> None:
    assert parse_int(text) == expected


def test_parse_float() -> None:
    assert parse_float("12.5%") == 12.5
    assert parse_float("none") is None


TABLE = """
<table>
  <thead><tr><th>A</th><th>B</th><th>C</th></tr></thead>
  <tbody>
    <tr><td rowspan="2">a1</td><td>b1</td><td>c1</td>
    <tr><td>b2</td><td>c2</td></tr></tr>
    <tr class="hidden-lg hidden-md"><td>mobile duplicate</td></tr>
    <tr><td>a3</td><td>b3</td><td>c3</td></tr>
  </tbody>
</table>
"""


def test_iter_rows_expands_nested_rowspan_rows_and_skips_mobile_duplicates() -> None:
    table = make_soup(TABLE).find("table")
    rows = list(iter_rows(table, required=("a", "b")))  # type: ignore[arg-type]

    assert [(r.text("a"), r.text("b"), r.text("c")) for r in rows] == [
        ("a1", "b1", "c1"),
        ("a1", "b2", "c2"),
        ("a3", "b3", "c3"),
    ]
    assert [r.continuation for r in rows] == [False, True, False]
    assert rows[1].own_text("a") is None


def test_iter_rows_reports_missing_columns() -> None:
    table = make_soup(TABLE).find("table")
    with pytest.raises(LayoutChangedError, match="missing expected columns"):
        list(iter_rows(table, required=("a", "deficiencies")))  # type: ignore[arg-type]
