"""Parser for the company Fleet info page."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import Tag
from bs4.element import Comment, NavigableString

from ..exceptions import LayoutChangedError
from ..models import Company, FleetVessel, RoleSince
from .html import (
    TableRow,
    clean,
    desktop_table,
    find_panel,
    iter_rows,
    make_soup,
    normalize_header,
    parse_date,
    parse_int,
    text_of,
)
from .page import require_content

_COMPANY_HEADING = re.compile(r"IMO\D*(\d{7})")
_IMO = re.compile(r"\b(\d{7})\b")
_RESULTS = re.compile(r"(\d[\d,]*)\s+results? found", re.IGNORECASE)
_PAGE_LINK = re.compile(r"formFleet\.P_PAGE\.value\s*=\s*(\d+)\s*;")
_ROLE = re.compile(r"^(?P<role>.+?)\s*\((?:since|during)\s+(?P<since>[^)]*)\)\s*$")

_IMO_HEADER = "(imo) ship's name"
_ISM_DETENTIONS = "detentions in last 3 years for this company (acting as ism manager)"
_ALL_DETENTIONS = "detentions in last 3 years for all companies (whatever their role)"


@dataclass
class FleetPage:
    """One page of a company's fleet."""

    company: Company
    vessels: list[FleetVessel] = field(default_factory=list)
    total_vessels: int | None = None
    last_page: int = 1


def parse_fleet(html: str) -> FleetPage:
    """Parse a Fleet info page."""
    soup = make_soup(html)
    require_content(soup, html, page="Fleet info")

    heading = soup.find("h4", class_="color-gris-bleu-copyright")
    if not isinstance(heading, Tag):
        raise LayoutChangedError("Fleet info page has no company heading")
    name_tag = heading.find("b")
    id_match = _COMPANY_HEADING.search(heading.get_text(" "))
    name = text_of(name_tag if isinstance(name_tag, Tag) else None)
    if not name or not id_match:
        raise LayoutChangedError("Fleet info heading does not contain a company name and number")

    company = Company(company_id=id_match.group(1), name=name)
    container = heading.find_parent("div", class_="col-lg-8")
    if isinstance(container, Tag):
        for info_row in container.find_all("div", class_="row"):
            columns = list(info_row.find_all("div", recursive=False))
            if len(columns) < 2 or not columns[0].find("b"):
                continue
            label = normalize_header(columns[0].get_text(" "))
            if label == "address":
                company.address = text_of(columns[1])
            elif label == "status":
                company.status = text_of(columns[1])
        badge = container.find("p", class_="badge-notification")
        if isinstance(badge, Tag):
            company.last_update = parse_date(badge.get_text(" "))

    page = FleetPage(company=company)
    table = desktop_table(find_panel(soup, "fleet"))
    if table is None:
        raise LayoutChangedError("Fleet info page has no fleet table")

    for row in iter_rows(table, required=(_IMO_HEADER, "gross tonnage")):
        first = row.cells.get(_IMO_HEADER)
        if first is None:
            continue
        link = first.find("a")
        imo_match = _IMO.search(link.get_text() if isinstance(link, Tag) else first.get_text())
        if not imo_match:
            continue
        imo = imo_match.group(1)
        cell_text = clean(first.get_text(" ")) or ""
        name = clean(cell_text.split(imo, 1)[-1].lstrip(" )")) or ""

        page.vessels.append(
            FleetVessel(
                imo=imo,
                name=name,
                gross_tonnage=parse_int(row.text("gross tonnage")),
                ship_type=row.text("ship's type"),
                year_built=parse_int(row.text("year of build")),
                flag=row.text("current flag"),
                class_societies=_lines(row.cells.get("current class(es)")),
                detentions_as_ism_manager_3y=_count(row, _ISM_DETENTIONS),
                detentions_all_companies_3y=_count(row, _ALL_DETENTIONS),
                roles=[_role(line) for line in _lines(row.cells.get("acting as (since)"))],
            )
        )

    results = soup.find("div", class_="results")
    if isinstance(results, Tag) and (match := _RESULTS.search(text_of(results) or "")):
        page.total_vessels = parse_int(match.group(1))
    page.last_page = max([1, *(int(n) for n in _PAGE_LINK.findall(html))])
    return page


def _count(row: TableRow, header: str) -> int | None:
    """Detention counts are left blank when there were none."""
    if header not in row.cells:
        return None
    return parse_int(row.text(header)) or 0


def _lines(cell: Tag | None) -> list[str]:
    """Split a cell into the lines separated by ``<br>`` tags.

    Text between two ``<br>`` tags forms one line even if the markup itself wraps
    it across several source lines.
    """
    if cell is None:
        return []
    lines: list[str] = []
    current: list[str] = []
    for node in cell.descendants:
        if isinstance(node, Tag):
            if node.name == "br":
                lines.append(" ".join(current))
                current = []
        elif isinstance(node, NavigableString) and not isinstance(node, Comment):
            current.append(str(node))
    lines.append(" ".join(current))
    return [text for line in lines if (text := clean(line))]


def _role(line: str) -> RoleSince:
    match = _ROLE.match(line)
    if not match:
        return RoleSince(role=line)
    return RoleSince(role=match.group("role"), since=parse_date(match.group("since")))
