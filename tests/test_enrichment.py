"""Tests for reference data and derived vessel indicators."""

from __future__ import annotations

from datetime import date

import pytest

from equasis_cli.enrichment import compute_indicators, country, country_by_name, mmsi_country
from equasis_cli.enrichment.indicators import months_before
from equasis_cli.models import (
    ClassStatus,
    CompanyChange,
    FlagChange,
    FlagPerformance,
    Inspection,
    InspectionReport,
    NameChange,
    PandIInsurer,
    Vessel,
)
from tests.fakes import fixture_vessel

TODAY = date(2026, 9, 16)


def test_country_lookups() -> None:
    panama = country("pan")
    assert panama is not None
    assert (panama.alpha2, panama.name) == ("PA", "Panama")
    assert country_by_name("PANAMA") == panama
    assert country("XXX") is None
    assert country_by_name(None) is None


@pytest.mark.parametrize(
    ("mmsi", "expected"),
    [
        ("353136000", "PAN"),
        ("538001234", "MHL"),
        ("477123456", "HKG"),
        ("003531360", None),  # coast station
        ("111353100", None),  # search and rescue aircraft
        ("35313600", None),
        (None, None),
    ],
)
def test_mmsi_country(mmsi: str | None, expected: str | None) -> None:
    result = mmsi_country(mmsi)
    assert (result.alpha3 if result else None) == expected


@pytest.mark.parametrize(
    ("reference", "months", "expected"),
    [
        (date(2026, 9, 16), 36, date(2023, 9, 16)),
        (date(2026, 3, 31), 1, date(2026, 2, 28)),
        (date(2024, 3, 31), 1, date(2024, 2, 29)),
        (date(2026, 1, 15), 12, date(2025, 1, 15)),
    ],
)
def test_months_before(reference: date, months: int, expected: date) -> None:
    assert months_before(reference, months) == expected


def test_indicators_for_a_vessel_with_red_flags() -> None:
    vessel = Vessel(
        imo="9999999",
        name="NEW NAME",
        flag="Cameroon",
        flag_code="CMR",
        mmsi="538001234",
        year_built=1996,
        status="In Service/Commission",
        flag_performance=FlagPerformance(
            paris_mou="Black", tokyo_mou="Grey", uscg_targeted=True, iacs_classed=False
        ),
        class_status=[
            ClassStatus(society="Some Register", status="Withdrawn", since=date(2025, 5, 1))
        ],
        name_history=[
            NameChange(name="NEW NAME", since=date(2026, 5, 1)),
            NameChange(name="MIDDLE", since=date(2024, 1, 1)),
            NameChange(name="ORIGINAL", since=date(2001, 1, 1)),
        ],
        flag_history=[
            FlagChange(flag="Cameroon", since=date(2026, 5, 1)),
            FlagChange(flag="Liberia", since=date(2001, 1, 1)),
        ],
        company_history=[
            CompanyChange(company="C", role="Registered owner", since=date(2026, 5, 1)),
            CompanyChange(company="B", role="Registered owner", since=date(2024, 1, 1)),
            CompanyChange(company="A", role="Registered owner", since=date(2001, 1, 1)),
        ],
        inspections=[
            Inspection(
                authority="Spain",
                port="Algeciras",
                date=date(2026, 6, 1),
                detained=True,
                reports=[InspectionReport(psc_organisation="Paris MoU", deficiencies=12)],
            ),
            Inspection(authority="Oman", port="Sohar", date=date(2019, 1, 1), detained=True),
        ],
    )

    indicators = compute_indicators(vessel, TODAY)

    assert indicators.age_years == 30
    assert indicators.name_changes_12_months == 1
    assert indicators.name_changes_36_months == 2
    assert indicators.flag_changes_12_months == 1
    assert indicators.management_changes_36_months == 2
    assert indicators.inspections_36_months == 1
    assert indicators.detentions_36_months == 1
    assert indicators.deficiencies_36_months == 12
    assert indicators.last_detention == date(2026, 6, 1)
    assert indicators.flag_on_paris_mou_grey_or_black_list is True
    assert indicators.flag_on_tokyo_mou_grey_or_black_list is True
    assert indicators.class_withdrawn_or_suspended_36_months == ["Some Register: Withdrawn"]
    assert indicators.mmsi_country == "Marshall Islands"
    assert indicators.mmsi_matches_flag is False
    assert indicators.observations == [
        "Renamed 2 times in the last 36 months",
        "Changed flag 1 time in the last 36 months",
        "2 changes of owner or manager in the last 36 months",
        "Detained 1 time in the last 36 months",
        "Flag is on the grey or black list of the Paris MoU and Tokyo MoU",
        "Flag is targeted by the US Coast Guard",
        "Not classed by an IACS member society",
        "Class withdrawn in the last 36 months (Some Register)",
        "MMSI 538001234 is allocated to Marshall Islands, not the flag state (Cameroon)",
        "No P&I insurer recorded in Equasis",
    ]


def test_indicators_for_a_quiet_vessel() -> None:
    vessel = Vessel(
        imo="9811000",
        name="QUIET",
        flag_code="PAN",
        mmsi="353136000",
        status="In Service/Commission",
        pandi=[PandIInsurer(name="UK P&I Club")],
        flag_performance=FlagPerformance(paris_mou="White", tokyo_mou="White", iacs_classed=True),
        inspections=[Inspection(authority="x", port="y", date=date(2026, 1, 1), detained=False)],
    )
    indicators = compute_indicators(vessel, TODAY)
    assert indicators.mmsi_matches_flag is True
    assert indicators.observations == []


def test_indicators_from_recorded_vessels() -> None:
    kavita = compute_indicators(fixture_vessel("9074729"), TODAY)
    assert kavita.age_years == 31
    assert kavita.management_changes_36_months == 1
    assert kavita.last_inspection == date(2025, 1, 8)
    assert "Flag is on the grey or black list of the Paris MoU and Tokyo MoU" in kavita.observations

    ever_given = compute_indicators(fixture_vessel("9811000"), TODAY)
    assert ever_given.mmsi_matches_flag is True
    assert ever_given.observations == ["Flag is targeted by the US Coast Guard"]
