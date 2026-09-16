"""Tests for output rendering and file writing."""

from __future__ import annotations

import csv
import io
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

import pytest

from equasis_cli import output
from equasis_cli.models import BatchItem, CompanySummary, ItemStatus, SearchResults, ShipSummary
from tests.fakes import fixture_fleet, fixture_vessel

MOMENT = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("out.json", "json"),
        ("OUT.CSV", "csv"),
        ("dir/out.jsonl", "jsonl"),
        ("x.ndjson", "jsonl"),
        ("x.txt", "table"),
        ("x.xlsx", None),
        (None, None),
    ],
)
def test_infer_format(path: str | None, expected: str | None) -> None:
    assert output.infer_format(path) == expected


def test_resolve_format_prefers_explicit_then_extension() -> None:
    assert output.resolve_format("csv", "out.json") == "csv"
    assert output.resolve_format(None, "out.json") == "json"
    assert output.resolve_format(None, None, default="json") == "json"


def test_vessel_json_envelope_is_valid_and_complete() -> None:
    fixture = fixture_vessel()
    fixture.retrieved_at = MOMENT
    document = json.loads(output.render(fixture, "json"))

    assert document["schema_version"] == 1
    assert document["type"] == "vessel"
    assert document["retrieved_at"] == "2026-09-16T12:00:00Z"
    vessel = document["vessel"]
    assert vessel["retrieved_at"] == "2026-09-16T12:00:00Z"
    assert vessel["imo"] == "9074729"
    assert vessel["gross_tonnage"] == 15899
    assert vessel["status_since"] == "2025-09-25"
    assert len(vessel["inspections"]) == 83
    assert vessel["inspections"][0]["deficiencies"] == 8
    assert vessel["inspections"][0]["detained"] is False
    assert vessel["name_history"][1]["until"] == "2022-02-01"


def test_vessel_jsonl_is_a_single_line() -> None:
    text = output.render(fixture_vessel(), "jsonl", retrieved_at=MOMENT)
    assert text.count("\n") == 1
    assert json.loads(text)["vessel"]["name"] == "KAVITA"


def test_vessel_csv_has_header_and_summary_row() -> None:
    rows = list(csv.DictReader(io.StringIO(output.render(fixture_vessel(), "csv"))))

    assert len(rows) == 1
    row = rows[0]
    assert row["imo"] == "9074729"
    assert row["flag"] == "Palau (Republic of)"
    assert row["registered_owner"] == "CASSINI SHIP OWNING CO"
    assert row["ism_manager"] == "COSTALINA SHIP MANAGEMENT FZC"
    assert row["inspections"] == "83"
    assert row["detentions"] == "4"
    assert row["last_inspection"] == "2025-01-08"
    assert row["uscg_targeted"] == "false"
    assert row["name_changes"] == "4"


def test_vessel_table_is_readable() -> None:
    text = output.render(fixture_vessel(), "table")
    assert text.startswith("KAVITA (IMO 9074729)\n")
    assert "PSC inspections (83 total, 4 with detention)" in text
    assert "73 older inspections" in text
    assert "Detention: N" not in text


def test_csv_quotes_values_containing_commas() -> None:
    results = SearchResults(
        query="x",
        companies=[CompanySummary(company_id="1", name="ACME, INC.", address='1 "Dock" Rd, Port')],
    )
    rows = list(csv.reader(io.StringIO(output.render(results, "csv"))))
    assert rows[1][3] == "ACME, INC."
    assert rows[1][8] == '1 "Dock" Rd, Port'


def test_search_jsonl_labels_record_kinds() -> None:
    results = SearchResults(
        query="TORM",
        ships=[ShipSummary(imo="9465992", name="TORM AGNES")],
        companies=[CompanySummary(company_id="0310062", name="TORM A/S")],
    )
    records = [json.loads(line) for line in output.render(results, "jsonl").splitlines()]
    assert [r["kind"] for r in records] == ["ship", "company"]


def test_search_table_without_results() -> None:
    assert "No ships or companies match" in output.render(SearchResults(query="zz"), "table")


def test_fleet_formats() -> None:
    fleet = fixture_fleet()
    rows = list(csv.DictReader(io.StringIO(output.render(fleet, "csv"))))
    assert len(rows) == 94
    assert rows[0]["company_name"] == "TORM A/S"
    assert "ISM Manager (since 2008-02-26)" in rows[0]["roles"]

    lines = output.render(fleet, "jsonl").splitlines()
    assert json.loads(lines[0])["company_id"] == "0310062"

    assert "TORM A/S (company no. 0310062)" in output.render(fleet, "table")


def test_batch_formats() -> None:
    report = output.BatchReport(
        kind="vessels",
        items=[
            BatchItem(query="9074729", status=ItemStatus.OK, result=fixture_vessel()),
            BatchItem(query="1234567", status=ItemStatus.NOT_FOUND, error="no vessel"),
        ],
    )
    document = json.loads(output.render(report, "json", retrieved_at=MOMENT))
    assert document["type"] == "batch_vessels"
    assert document["summary"] == {
        "total": 2,
        "succeeded": 1,
        "failed": 1,
        "started_at": output._timestamp(report.started_at),
    }
    assert document["results"][1] == {
        "query": "1234567",
        "status": "not_found",
        "error": "no vessel",
        "warnings": [],
        "elapsed_seconds": 0.0,
        "vessel": None,
        "indicators": None,
    }
    assert document["results"][0]["indicators"]["age_years"] == 31

    rows = list(csv.DictReader(io.StringIO(output.render(report, "csv"))))
    assert [(r["query"], r["lookup_status"], r["name"]) for r in rows] == [
        ("9074729", "ok", "KAVITA"),
        ("1234567", "not_found", ""),
    ]
    assert "1 of 2 vessel lookups succeeded" in output.render(report, "table")


def test_render_rejects_unknown_format() -> None:
    with pytest.raises(ValueError, match="unknown output format"):
        output.render(SearchResults(query="x"), "xml")


def test_write_output_is_atomic_and_utf8(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "out.json"
    output.write_output('{"name": "Ålesund"}', target)
    assert target.read_text(encoding="utf-8") == '{"name": "Ålesund"}\n'
    assert list(target.parent.iterdir()) == [target]


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")
def test_write_output_respects_umask(tmp_path: Path) -> None:
    previous = os.umask(0o022)
    try:
        target = output.write_output("x", tmp_path / "out.txt")
    finally:
        os.umask(previous)
    assert stat.S_IMODE(target.stat().st_mode) == 0o644
