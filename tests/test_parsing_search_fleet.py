"""Tests for the search results and Fleet info parsers."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from equasis_cli.models import CompanySummary, RoleSince, ShipSummary
from equasis_cli.parsing import parse_fleet, parse_search

Loader = Callable[[str], str]


def test_search_first_page(fixture_html: Loader) -> None:
    page = parse_search(fixture_html("search_torm_page1"))

    assert len(page.ships) == 100  # mobile duplicate rows are ignored
    assert page.total_ships == 105
    assert page.last_ship_page == 2
    assert page.ships[0] == ShipSummary(
        imo="9465992",
        name="TORM AGNES",
        gross_tonnage=30302,
        ship_type="Chemical/Oil Products Tanker",
        year_built=2011,
        flag="Denmark (DIS) (DIS)",
    )
    assert page.companies[0] == CompanySummary(
        company_id="0310062",
        name="TORM A/S",
        address="Tuborg Havnevej 18, 2900, Hellerup, Denmark.",
    )
    assert len({c.company_id for c in page.companies}) == len(page.companies) == 8


def test_search_last_page(fixture_html: Loader) -> None:
    page = parse_search(fixture_html("search_torm_page2"))
    assert len(page.ships) == 5
    assert page.total_ships == 105


def test_search_without_results(fixture_html: Loader) -> None:
    page = parse_search(fixture_html("search_no_results"))
    assert page.ships == []
    assert page.companies == []
    assert page.total_ships is None


def test_advanced_search_by_mmsi(fixture_html: Loader) -> None:
    page = parse_search(fixture_html("search_by_mmsi"))
    assert [s.imo for s in page.ships] == ["9811000"]


def test_fleet_single_page(fixture_html: Loader) -> None:
    page = parse_fleet(fixture_html("fleet_torm"))

    assert page.company.company_id == "0310062"
    assert page.company.name == "TORM A/S"
    assert page.company.status == "Active"
    assert page.company.address == "Tuborg Havnevej 18, 2900, Hellerup, Denmark."
    assert page.company.last_update == date(2026, 9, 15)
    assert len(page.vessels) == page.total_vessels == 94
    assert page.last_page == 1

    first = page.vessels[0]
    assert (first.imo, first.name, first.gross_tonnage) == ("9307798", "TORM VENTURE", 42162)
    assert first.flag == "Denmark (DIS)"
    assert first.class_societies == ["LRS"]
    assert first.detentions_all_companies_3y == 0
    assert RoleSince(role="ISM Manager", since=date(2008, 2, 26)) in first.roles
    assert len({v.imo for v in page.vessels}) == 94


def test_fleet_pagination_metadata(fixture_html: Loader) -> None:
    page = parse_fleet(fixture_html("fleet_msc_page1"))
    assert page.company.company_id == "0152944"
    assert page.total_vessels == 443
    assert page.last_page == 5


def test_fleet_role_with_year_only(fixture_html: Loader) -> None:
    page = parse_fleet(fixture_html("fleet_msc_page2"))
    roles = [role for vessel in page.vessels for role in vessel.roles]
    assert RoleSince(role="Ship manager/Commercial manager", since=None) in roles
