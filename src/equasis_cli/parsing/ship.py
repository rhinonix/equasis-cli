"""Parsers for the Ship Info, Inspections and Ship History pages."""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date

from bs4 import Tag

from ..exceptions import LayoutChangedError
from ..models import (
    ClassChange,
    ClassStatus,
    ClassSurvey,
    CompanyChange,
    CompanyRole,
    FlagChange,
    FlagPerformance,
    HumanElementDeficiency,
    Inspection,
    InspectionReport,
    NameChange,
    PandIInsurer,
    SafetyCertificate,
    Sighting,
    Vessel,
)
from .html import (
    class_list,
    clean,
    desktop_table,
    find_panel,
    iter_rows,
    make_soup,
    normalize_header,
    paragraph_texts,
    parse_date,
    parse_float,
    parse_int,
    text_of,
)
from .page import require_content

_IMO_IN_HEADING = re.compile(r"IMO\D*(\d{7})")
_FLAG_IMAGE = re.compile(r"/flags/([A-Z]{3})\.", re.IGNORECASE)
_ONCLICK_ID = re.compile(r"P_(?:COMP|INSP)\.value\s*=\s*'(\d+)'")

# Equasis cannot serve COM.png (a reserved file name on Windows), so the Comoros
# flag image is published as XCM.png.
_FLAG_CODE_ALIASES = {"XCM": "COM"}

# ------------------------------------------------------------------------- ship info


def parse_ship_info(html: str) -> Vessel:
    """Parse the Ship Info page into a :class:`Vessel` (without inspections or history)."""
    soup = make_soup(html)
    require_content(soup, html, page="Ship Info")

    heading = soup.find("h4", class_="color-gris-bleu-copyright")
    if not isinstance(heading, Tag):
        raise LayoutChangedError("Ship Info page has no vessel heading")
    name_tag = heading.find("b")
    imo_match = _IMO_IN_HEADING.search(heading.get_text(" "))
    name = text_of(name_tag if isinstance(name_tag, Tag) else None)
    if not name or not imo_match:
        raise LayoutChangedError("Ship Info heading does not contain a name and IMO number")

    vessel = Vessel(imo=imo_match.group(1), name=name)
    _parse_particulars(heading, vessel)

    vessel.flag_performance = _parse_overview(find_panel(soup, "overview"))
    vessel.management = _parse_management(find_panel(soup, "management detail"))
    vessel.class_status, vessel.class_surveys = _parse_classification(
        find_panel(soup, "classification")
    )
    vessel.safety_certificates = _parse_safety_certificates(
        find_panel(soup, "safety management certificate")
    )
    vessel.pandi = _parse_pandi(find_panel(soup, "p&i information"))
    vessel.sightings = _parse_sightings(find_panel(soup, "geographical information"))
    return vessel


def _parse_particulars(heading: Tag, vessel: Vessel) -> None:
    container = heading.find_parent("div", class_="col-lg-8") or heading.find_parent("div")
    if not isinstance(container, Tag):
        return

    for row in container.find_all("div", class_="row"):
        columns = [
            col
            for col in row.find_all("div", recursive=False)
            if "hidden-lg" not in class_list(col)
        ]
        if len(columns) < 2 or not columns[0].find("b"):
            continue
        label = normalize_header(columns[0].get_text(" "))
        value = text_of(columns[1])
        extra = text_of(columns[2]) if len(columns) > 2 else None

        if label == "flag":
            image = columns[1].find("img")
            if isinstance(image, Tag):
                code_match = _FLAG_IMAGE.search(str(image.get("src", "")))
                if code_match:
                    code = code_match.group(1).upper()
                    vessel.flag_code = _FLAG_CODE_ALIASES.get(code, code)
            vessel.flag = _unwrap_parentheses(extra) or value
        elif label == "call sign":
            vessel.call_sign = value
        elif label == "mmsi":
            vessel.mmsi = value
        elif label == "gross tonnage":
            vessel.gross_tonnage = parse_int(value)
        elif label == "dwt":
            vessel.deadweight = parse_int(value)
        elif label == "type of ship":
            vessel.ship_type = value
        elif label in ("year of build", "year built"):
            vessel.year_built = parse_int(value)
        elif label == "status":
            vessel.status = value
            vessel.status_since = parse_date(extra)

    badge = container.find("p", class_="badge-notification")
    if isinstance(badge, Tag):
        vessel.particulars_updated = parse_date(badge.get_text(" "))


def _unwrap_parentheses(text: str | None) -> str | None:
    """Turn ``"(Palau (Republic of))"`` into ``"Palau (Republic of)"``."""
    if text and text.startswith("(") and text.endswith(")"):
        return clean(text[1:-1])
    return clean(text)


def _parse_overview(panel: Tag | None) -> FlagPerformance:
    performance = FlagPerformance()
    if panel is None:
        return performance
    text = text_of(panel) or ""
    performance.iacs_classed = "classed by (at least) one of the IACS" in text
    rate = re.search(r"(\d+(?:\.\d+)?)\s*%\s*Of inspections having led to a detention", text, re.I)
    if rate:
        performance.detention_rate_36_months = parse_float(rate.group(1))

    for badge in panel.find_all("div", class_="badge"):
        parts = paragraph_texts(badge)
        if not parts:
            continue
        label = parts[0].lower()
        if label.startswith("paris mou") and len(parts) > 1:
            performance.paris_mou = parts[-1]
        elif label.startswith("tokyo mou") and len(parts) > 1:
            performance.tokyo_mou = parts[-1]
        elif label.startswith("uscg"):
            performance.uscg_targeted = "not targeted" not in label
    return performance


def _parse_management(panel: Tag | None) -> list[CompanyRole]:
    table = desktop_table(panel)
    if table is None:
        return []
    companies = []
    for row in iter_rows(table, required=("imo number", "role", "name of company")):
        name = row.text("name of company")
        if not name:
            continue
        companies.append(
            CompanyRole(
                company_id=row.text("imo number"),
                name=name,
                role=row.text("role") or "",
                address=row.text("address"),
                since=parse_date(row.text("date of effect")),
            )
        )
    return companies


def _parse_classification(panel: Tag | None) -> tuple[list[ClassStatus], list[ClassSurvey]]:
    statuses: list[ClassStatus] = []
    surveys: list[ClassSurvey] = []
    if panel is None:
        return statuses, surveys

    section = None
    for element in panel.find_all(["h5", "div"]):
        if element.name == "h5":
            section = normalize_header(element.get_text(" "))
            continue
        if "access-body" not in class_list(element) or element.find("h5"):
            continue
        paragraphs = paragraph_texts(element)
        if not paragraphs:
            continue

        if section == "status":
            badge = element.find("span", class_="badge")
            status = text_of(badge) if isinstance(badge, Tag) else None
            reason_tag = element.find("i")
            reason = text_of(reason_tag) if isinstance(reason_tag, Tag) else None
            since = next(
                (parse_date(p) for p in paragraphs if p.startswith(("since", "during"))), None
            )
            statuses.append(
                ClassStatus(society=paragraphs[0], status=status, since=since, reason=reason)
            )
        elif section == "surveys":
            survey = ClassSurvey(society=paragraphs[0])
            for paragraph in paragraphs[1:]:
                lowered = paragraph.lower()
                if lowered.startswith("last renewal"):
                    survey.last_renewal = parse_date(paragraph)
                elif lowered.startswith("next renewal"):
                    survey.next_renewal = parse_date(paragraph)
            surveys.append(survey)
    return statuses, surveys


def _parse_safety_certificates(panel: Tag | None) -> list[SafetyCertificate]:
    table = desktop_table(panel)
    if table is None:
        return []
    certificates = []
    for row in iter_rows(table, required=("classification society",)):
        society = row.text("classification society")
        if not society:
            continue
        certificates.append(
            SafetyCertificate(
                society=society,
                survey_date=parse_date(row.text("date survey")),
                expiry_date=parse_date(row.text("date expiry")),
                status_change_date=parse_date(row.text("date change status")),
                status=row.text("status"),
                reason=row.text("reason"),
                convention=row.text("top c/v"),
            )
        )
    return certificates


def _parse_pandi(panel: Tag | None) -> list[PandIInsurer]:
    if panel is None:
        return []
    insurers = []
    for body in panel.find_all("div", class_="access-body"):
        paragraphs = paragraph_texts(body)
        if not paragraphs:
            continue
        inception = next((parse_date(p) for p in paragraphs[1:] if "inception" in p.lower()), None)
        insurers.append(PandIInsurer(name=paragraphs[0], inception=inception))
    return insurers


def _parse_sightings(panel: Tag | None) -> list[Sighting]:
    table = desktop_table(panel)
    if table is None:
        return []
    sightings = []
    for row in iter_rows(table, required=("date of record", "area where the ship was seen")):
        period = row.text("date of record")
        if not period:
            continue
        areas = [a.strip() for a in (row.text("area where the ship was seen") or "").split(",")]
        sightings.append(
            Sighting(period=period, areas=[a for a in areas if a], source=row.text("source"))
        )
    return sightings


# ------------------------------------------------------------------------ inspections


def parse_inspections(html: str) -> tuple[list[Inspection], list[HumanElementDeficiency]]:
    """Parse the Inspections page.

    Returns the port state control inspections (newest first) and the human
    element deficiencies table.
    """
    soup = make_soup(html)
    require_content(soup, html, page="Inspections")

    inspections: list[Inspection] = []
    table = desktop_table(find_panel(soup, "list of port state controls"))
    if table is not None:
        required = ("authority", "port of inspection", "date of report", "detention")
        for row in iter_rows(table, required=required):
            report = InspectionReport(
                psc_organisation=row.text("psc organisation"),
                inspection_type=row.text("type of inspection"),
                duration_days=parse_int(row.text("duration (days)")),
                deficiencies=parse_int(row.text("number of deficiencies")),
                inspection_id=_onclick_id(row.cells.get("details")),
            )
            if row.continuation and inspections:
                inspections[-1].reports.append(report)
                continue
            detention = (row.text("detention") or "").strip().upper()
            inspections.append(
                Inspection(
                    authority=row.text("authority"),
                    port=row.text("port of inspection"),
                    date=parse_date(row.text("date of report")),
                    detained={"Y": True, "YES": True, "N": False, "NO": False}.get(detention),
                    reports=[report],
                )
            )

    human_element: list[HumanElementDeficiency] = []
    human_table = desktop_table(find_panel(soup, "human element deficiencies"))
    if human_table is not None:
        for row in iter_rows(human_table, required=("psc organisation", "date of report")):
            human_element.append(
                HumanElementDeficiency(
                    psc_organisation=row.text("psc organisation"),
                    authority=row.text("authority"),
                    port=row.text("port of inspection"),
                    inspection_type=row.text("type of inspection"),
                    date=parse_date(row.text("date of report")),
                    deficiencies=parse_int(row.text("human element deficiencies")),
                )
            )
    return inspections, human_element


def _onclick_id(cell: Tag | None) -> str | None:
    if cell is None:
        return None
    for element in [cell, *cell.find_all(onclick=True)]:
        match = _ONCLICK_ID.search(str(element.get("onclick", "")))
        if match:
            return match.group(1)
    return None


# ---------------------------------------------------------------------------- history


def parse_history(
    html: str,
) -> tuple[list[NameChange], list[FlagChange], list[ClassChange], list[CompanyChange]]:
    """Parse the Ship History page (newest records first)."""
    soup = make_soup(html)
    require_content(soup, html, page="Ship History")

    names: list[NameChange] = []
    table = desktop_table(find_panel(soup, "current and former name"))
    if table is not None:
        for row in iter_rows(table, required=("name of ship", "date of effect")):
            if value := row.text("name of ship"):
                names.append(
                    NameChange(
                        name=value,
                        since=parse_date(row.text("date of effect")),
                        source=row.text("source(s)"),
                    )
                )
    _derive_until(names)

    flags: list[FlagChange] = []
    table = desktop_table(find_panel(soup, "current and former flag"))
    if table is not None:
        for row in iter_rows(table, required=("flag", "date of effect")):
            if value := row.text("flag"):
                flags.append(
                    FlagChange(
                        flag=value,
                        since=parse_date(row.text("date of effect")),
                        source=row.text("source(s)"),
                    )
                )
    _derive_until(flags)

    classes: list[ClassChange] = []
    table = desktop_table(find_panel(soup, "list of class renewal surveys"))
    if table is not None:
        for row in iter_rows(table, required=("classification society",)):
            if value := row.text("classification society"):
                classes.append(
                    ClassChange(
                        society=value,
                        survey_date=parse_date(row.text("date of survey")),
                        source=row.text("source(s)"),
                    )
                )

    companies: list[CompanyChange] = []
    table = desktop_table(find_panel(soup, "company"))
    if table is not None:
        for row in iter_rows(table, required=("company", "role", "date of effect")):
            if value := row.text("company"):
                companies.append(
                    CompanyChange(
                        company=value,
                        role=row.text("role") or "",
                        since=parse_date(row.text("date of effect")),
                        source=row.text("source(s)"),
                    )
                )
    for role in {c.role for c in companies}:
        _derive_until([c for c in companies if c.role == role])

    return names, flags, classes, companies


def _derive_until(records: Sequence[NameChange | FlagChange | CompanyChange]) -> None:
    """Set each record's ``until`` to the start of the next newer record.

    Records are ordered newest first, so the newer record precedes it.
    """
    newer_since: date | None = None
    for index, record in enumerate(records):
        if index > 0:
            record.until = newer_since
        newer_since = record.since


def merge_vessel(
    vessel: Vessel,
    inspections: tuple[list[Inspection], list[HumanElementDeficiency]] | None,
    history: tuple[list[NameChange], list[FlagChange], list[ClassChange], list[CompanyChange]]
    | None,
) -> Vessel:
    """Attach inspections and history results to ``vessel`` and return it."""
    if inspections is not None:
        vessel.inspections, vessel.human_element_deficiencies = inspections
    if history is not None:
        (
            vessel.name_history,
            vessel.flag_history,
            vessel.class_history,
            vessel.company_history,
        ) = history
    return vessel


__all__ = [
    "merge_vessel",
    "parse_history",
    "parse_inspections",
    "parse_ship_info",
]
