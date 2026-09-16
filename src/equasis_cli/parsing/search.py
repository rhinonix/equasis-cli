"""Parser for the search results page (ships and companies)."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar

from bs4 import BeautifulSoup, Tag

from ..models import CompanySummary, ShipSummary
from .html import iter_rows, make_soup, parse_int, text_of
from .page import require_content

_RESULTS = re.compile(r"(\d[\d,]*)\s+results? found", re.IGNORECASE)
_PAGE_LINK = re.compile(r"P_PAGE_(SHIP|COMP)\.value\s*=\s*(\d+)")
_SHIP_SECTION = "ShipResultId"
_COMPANY_SECTION = "CompanyResultId"

_T = TypeVar("_T")


@dataclass
class SearchPage:
    """One page of search results."""

    ships: list[ShipSummary] = field(default_factory=list)
    companies: list[CompanySummary] = field(default_factory=list)
    total_ships: int | None = None
    total_companies: int | None = None
    last_ship_page: int = 1
    last_company_page: int = 1


def parse_search(html: str) -> SearchPage:
    """Parse a search results page."""
    soup = make_soup(html)
    require_content(soup, html, page="Search")
    page = SearchPage()

    ship_table = _section_table(soup, _SHIP_SECTION)
    if ship_table is not None:
        for row in iter_rows(ship_table, required=("imo number", "name of ship")):
            imo = row.text("imo number")
            name = row.text("name of ship")
            if not imo or not name:
                continue
            page.ships.append(
                ShipSummary(
                    imo=imo,
                    name=name,
                    gross_tonnage=parse_int(row.text("gross tonnage")),
                    ship_type=row.text("type of ship"),
                    year_built=parse_int(row.text("year of build")),
                    flag=row.text("flag"),
                )
            )

    company_table = _section_table(soup, _COMPANY_SECTION)
    if company_table is not None:
        for row in iter_rows(company_table, required=("company number", "name of company")):
            company_id = row.text("company number")
            name = row.text("name of company")
            if not company_id or not name:
                continue
            page.companies.append(
                CompanySummary(company_id=company_id, name=name, address=row.text("address"))
            )

    for results in soup.find_all("div", class_="results"):
        match = _RESULTS.search(text_of(results) or "")
        section = results.find_previous(id=(_SHIP_SECTION, _COMPANY_SECTION))
        if not match or not isinstance(section, Tag):
            continue
        total = parse_int(match.group(1))
        if section.get("id") == _SHIP_SECTION:
            page.total_ships = total
        else:
            page.total_companies = total

    for kind, number in _PAGE_LINK.findall(html):
        if kind == "SHIP":
            page.last_ship_page = max(page.last_ship_page, int(number))
        else:
            page.last_company_page = max(page.last_company_page, int(number))

    page.ships = _dedupe(page.ships, key=lambda s: s.imo)
    page.companies = _dedupe(page.companies, key=lambda c: c.company_id)
    return page


def _section_table(soup: BeautifulSoup, section_id: str) -> Tag | None:
    section = soup.find(id=section_id)
    if not isinstance(section, Tag):
        return None
    table = section.find("table")
    return table if isinstance(table, Tag) else None


def _dedupe(items: list[_T], key: Callable[[_T], str]) -> list[_T]:
    seen: set[str] = set()
    unique: list[_T] = []
    for item in items:
        identity = key(item)
        if identity not in seen:
            seen.add(identity)
            unique.append(item)
    return unique
