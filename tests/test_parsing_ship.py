"""Tests for the Ship Info, Inspections and Ship History parsers."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

import pytest

from equasis_cli.exceptions import LayoutChangedError
from equasis_cli.models import (
    ClassStatus,
    ClassSurvey,
    CompanyChange,
    CompanyRole,
    FlagChange,
    FlagPerformance,
    NameChange,
    PandIInsurer,
    SafetyCertificate,
)
from equasis_cli.parsing import parse_history, parse_inspections, parse_ship_info

Loader = Callable[[str], str]


def test_ship_info_particulars(fixture_html: Loader) -> None:
    vessel = parse_ship_info(fixture_html("ship_info_9811000"))

    assert vessel.imo == "9811000"
    assert vessel.name == "EVER GIVEN"
    assert vessel.flag == "Panama"
    assert vessel.flag_code == "PAN"
    assert vessel.call_sign == "H3RC"
    assert vessel.mmsi == "353136000"
    assert vessel.gross_tonnage == 219079
    assert vessel.deadweight == 199489
    assert vessel.ship_type == "Container Ship"
    assert vessel.year_built == 2018
    assert vessel.status == "In Service/Commission"
    assert vessel.status_since == date(2021, 11, 14)
    assert vessel.particulars_updated == date(2026, 9, 15)


def test_ship_info_panels(fixture_html: Loader) -> None:
    vessel = parse_ship_info(fixture_html("ship_info_9811000"))

    assert vessel.flag_performance == FlagPerformance(
        paris_mou="White",
        tokyo_mou="White",
        uscg_targeted=True,
        iacs_classed=True,
        detention_rate_36_months=0.0,
    )
    assert vessel.management[0] == CompanyRole(
        company_id="1135348",
        name="BERNHARD SCHULTE-HKG LP",
        role="Ship manager/Commercial manager",
        address="Room 2602, K Wah Centre, 191, Java Road, North Point, Hong Kong, China.",
        since=date(2021, 3, 1),
    )
    assert {c.role for c in vessel.management} >= {"ISM Manager", "Registered owner"}
    assert vessel.class_status == [
        ClassStatus(
            society="American Bureau of Shipping (IACS)",
            status="Delivered",
            since=date(2018, 10, 25),
        )
    ]
    assert vessel.class_surveys == [
        ClassSurvey(
            society="American Bureau of Shipping (IACS)",
            last_renewal=date(2023, 7, 12),
            next_renewal=date(2028, 9, 24),
        )
    ]
    assert vessel.safety_certificates == [
        SafetyCertificate(
            society="American Bureau of Shipping (IACS)",
            survey_date=date(2023, 12, 4),
            expiry_date=date(2029, 1, 31),
            status_change_date=date(2018, 9, 25),
            status="Delivered",
            convention="Convention",
        )
    ]
    assert vessel.pandi == [PandIInsurer(name="UK P&I Club", inception=date(2018, 9, 25))]
    assert vessel.sightings[1].areas == ["West Africa", "West Europe"]
    assert vessel.sightings[1].source == "VesselTracker"


def test_ship_info_black_listed_flag_and_withdrawn_class(fixture_html: Loader) -> None:
    vessel = parse_ship_info(fixture_html("ship_info_9074729"))

    assert vessel.flag == "Palau (Republic of)"
    assert vessel.flag_code == "PLW"
    assert vessel.status == "Broken Up"
    assert vessel.flag_performance.paris_mou == "Black"
    assert vessel.flag_performance.uscg_targeted is False
    assert vessel.flag_performance.iacs_classed is False
    withdrawn = vessel.class_status[1]
    assert withdrawn.status == "Withdrawn"
    assert withdrawn.reason == "Non-compliance with conditions of class / recommendations"
    assert vessel.class_status[0].since == date(2024, 9, 1)  # "during 09/2024"
    assert vessel.pandi == []


def test_comoros_flag_image_alias(fixture_html: Loader) -> None:
    html = fixture_html("ship_info_9811000").replace("flags/PAN.png", "flags/XCM.png")
    assert parse_ship_info(html).flag_code == "COM"


def test_ship_info_without_heading_is_a_layout_change(fixture_html: Loader) -> None:
    html = fixture_html("ship_info_9811000").replace("color-gris-bleu-copyright", "renamed")
    with pytest.raises(LayoutChangedError):
        parse_ship_info(html)


def test_inspections_with_detentions_and_multi_regime_reports(fixture_html: Loader) -> None:
    inspections, human_element = parse_inspections(fixture_html("inspections_9074729"))

    assert len(inspections) == 83
    assert sum(1 for i in inspections if i.detained) == 4
    assert all(i.detained is not None for i in inspections)

    latest = inspections[0]
    assert (latest.authority, latest.port, latest.date) == ("Oman", "Sohar", date(2025, 1, 8))
    assert latest.detained is False
    assert latest.deficiencies == 8
    assert latest.reports[0].psc_organisation == "Indian Ocean MoU"
    assert latest.reports[0].inspection_type == "Initial inspection"
    assert latest.reports[0].inspection_id

    # One inspection reported to two regimes is a single inspection, not two.
    romania = next(i for i in inspections if i.date == date(2022, 2, 20))
    assert romania.authority == "Romania"
    assert [r.psc_organisation for r in romania.reports] == ["Black Sea MoU", "Paris MoU"]
    assert all(i.authority not in {"Paris MoU", "Black Sea MoU"} for i in inspections)
    assert all(i.date is not None for i in inspections)

    assert human_element[0].psc_organisation == "Indian Ocean MoU"
    assert human_element[0].date == date(2025, 1, 8)
    assert human_element[0].deficiencies == 2


def test_inspections_without_human_element_panel(fixture_html: Loader) -> None:
    inspections, human_element = parse_inspections(fixture_html("inspections_9811000"))
    assert inspections
    assert human_element == []


def test_history(fixture_html: Loader) -> None:
    names, flags, classes, companies = parse_history(fixture_html("history_9074729"))

    assert names[:3] == [
        NameChange(name="KAVITA", since=date(2022, 2, 1), until=None, source="IHS Maritime"),
        NameChange(
            name="Diamond A", since=date(2016, 7, 1), until=date(2022, 2, 1), source="IHS Maritime"
        ),
        NameChange(
            name="Venta", since=date(2008, 5, 1), until=date(2016, 7, 1), source="IHS Maritime"
        ),
    ]
    assert flags[0] == FlagChange(
        flag="Palau (Republic of)", since=date(2016, 7, 1), until=None, source="IHS Maritime"
    )
    assert flags[1].until == date(2016, 7, 1)
    assert classes[0].society == "Registro Italiano Navale (IACS)"
    assert classes[0].survey_date == date(2022, 2, 18)
    assert companies[0] == CompanyChange(
        company="COSTALINA SHIP MANAGEMENT FZC",
        role="ISM Manager",
        since=date(2024, 4, 9),
        until=None,
        source="IHS Maritime",
    )
    ism_managers = [c for c in companies if c.role == "ISM Manager"]
    assert ism_managers[1].until == ism_managers[0].since
