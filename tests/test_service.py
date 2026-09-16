"""Tests for batch processing and company resolution shared by both interfaces."""

from __future__ import annotations

import pytest

from equasis_cli.exceptions import AuthenticationError
from equasis_cli.models import CompanySummary, ItemStatus
from equasis_cli.service import Resolution, iter_fleets, iter_vessels, resolve_company
from tests.fakes import FakeClient, fixture_fleet

TORM = CompanySummary(company_id="0310062", name="TORM A/S")
TORM_NORWAY = CompanySummary(company_id="5313763", name="TORM NORWAY AS")


def test_iter_vessels_reports_every_item() -> None:
    client = FakeClient()
    started: list[tuple[int, int, str]] = []

    items = list(
        iter_vessels(
            client,  # type: ignore[arg-type]
            ["9074729", "EVER GIVEN", "1234567", "9074728"],
            on_start=lambda *args: started.append(args),
        )
    )

    assert [i.status for i in items] == [
        ItemStatus.OK,
        ItemStatus.ERROR,
        ItemStatus.NOT_FOUND,
        ItemStatus.NOT_FOUND,
    ]
    assert items[0].result is not None
    assert items[0].result.name == "KAVITA"
    assert "not a valid IMO number" in (items[1].error or "")
    assert "may contain a typo" in items[3].warnings[0]  # explains the likely cause
    assert [s[0] for s in started] == [1, 2, 3, 4]


def test_iter_vessels_warns_about_check_digit() -> None:
    vessel = FakeClient().vessels["9074729"]
    client = FakeClient(vessels={"9074728": vessel})
    [item] = iter_vessels(client, ["9074728"])  # type: ignore[arg-type]
    assert item.status is ItemStatus.OK
    assert "check digit" in item.warnings[0]


def test_iter_vessels_fail_fast_stops_after_first_failure() -> None:
    items = list(iter_vessels(FakeClient(), ["1234567", "9074729"], fail_fast=True))  # type: ignore[arg-type]
    assert [i.query for i in items] == ["1234567"]


def test_authentication_failure_aborts_batch() -> None:
    with pytest.raises(AuthenticationError):
        list(iter_vessels(FakeClient(reject_login=True), ["9074729"]))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("query", "companies", "resolution", "company"),
    [
        ("torm a/s", [TORM, TORM_NORWAY], Resolution.RESOLVED, TORM),
        ("TORM NORWAY", [TORM_NORWAY], Resolution.RESOLVED, TORM_NORWAY),
        ("TORM", [TORM, TORM_NORWAY], Resolution.AMBIGUOUS, None),
        ("MAERSK", [TORM], Resolution.NOT_FOUND, None),
    ],
)
def test_resolve_company(
    query: str,
    companies: list[CompanySummary],
    resolution: Resolution,
    company: CompanySummary | None,
) -> None:
    match = resolve_company(FakeClient(companies=companies), query)  # type: ignore[arg-type]
    assert match.resolution is resolution
    assert match.company == company


def test_iter_fleets_handles_ids_names_and_ambiguity() -> None:
    client = FakeClient(companies=[TORM, TORM_NORWAY], fleets={"0310062": fixture_fleet()})

    items = list(iter_fleets(client, ["0310062", "TORM A/S", "TORM", "NOBODY"]))  # type: ignore[arg-type]

    assert [i.status for i in items] == [
        ItemStatus.OK,
        ItemStatus.OK,
        ItemStatus.AMBIGUOUS,
        ItemStatus.NOT_FOUND,
    ]
    assert "TORM A/S (0310062)" in (items[2].error or "")


def test_iter_fleets_first_match_records_warning() -> None:
    client = FakeClient(companies=[TORM, TORM_NORWAY], fleets={"0310062": fixture_fleet()})

    [item] = iter_fleets(client, ["TORM"], first_match=True)  # type: ignore[arg-type]

    assert item.status is ItemStatus.OK
    assert "using TORM A/S (0310062)" in item.warnings[0]
