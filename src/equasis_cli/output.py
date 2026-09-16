"""Render results as table, JSON, JSON Lines, or CSV, and write them to files.

Table output is meant for people; JSON, JSON Lines and CSV are stable,
machine-readable formats (see ``docs/output-schema.md``).
"""

from __future__ import annotations

import csv
import io
import json
import os
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal

from .enrichment import VesselIndicators, compute_indicators
from .models import (
    SCHEMA_VERSION,
    BatchItem,
    CompanySummary,
    Fleet,
    ItemStatus,
    SearchResults,
    Vessel,
    to_jsonable,
)

FORMATS = ("table", "json", "jsonl", "csv")
SOURCE = "https://www.equasis.org"
TABLE_INSPECTION_LIMIT = 10
TABLE_SIGHTING_LIMIT = 5

_EXTENSIONS = {
    ".json": "json",
    ".jsonl": "jsonl",
    ".ndjson": "jsonl",
    ".csv": "csv",
    ".txt": "table",
}


@dataclass(kw_only=True)
class BatchReport:
    """Results of a batch of vessel or fleet lookups."""

    kind: Literal["vessels", "fleets"]
    items: list[BatchItem[Any]] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def succeeded(self) -> int:
        return sum(1 for item in self.items if item.status is ItemStatus.OK)

    @property
    def failed(self) -> int:
        return len(self.items) - self.succeeded


Renderable = Vessel | SearchResults | Fleet | BatchReport


# ------------------------------------------------------------------------ public API


def infer_format(path: str | os.PathLike[str] | None) -> str | None:
    """Guess the output format from a file extension (``.json``, ``.csv``, ...)."""
    if not path:
        return None
    return _EXTENSIONS.get(Path(path).suffix.lower())


def resolve_format(
    explicit: str | None, output_file: str | os.PathLike[str] | None, default: str = "table"
) -> str:
    """Pick the output format: explicit choice, then file extension, then ``default``."""
    return explicit or infer_format(output_file) or default


def render(result: Renderable, fmt: str, *, retrieved_at: datetime | None = None) -> str:
    """Render ``result`` in format ``fmt`` (one of :data:`FORMATS`)."""
    if fmt not in FORMATS:
        raise ValueError(f"unknown output format {fmt!r}; choose from {', '.join(FORMATS)}")
    retrieved_at = retrieved_at or datetime.now(timezone.utc)
    if isinstance(result, Vessel):
        return _render_vessel(result, fmt, retrieved_at)
    if isinstance(result, SearchResults):
        return _render_search(result, fmt, retrieved_at)
    if isinstance(result, Fleet):
        return _render_fleet(result, fmt, retrieved_at)
    return _render_batch(result, fmt, retrieved_at)


def render_batch_item_jsonl(kind: str, item: BatchItem[Any], today: date | None = None) -> str:
    """Render one batch item as a JSON Lines record (for streaming output)."""
    return _dumps_line(_batch_item_record(kind, item, today or date.today()))


def write_output(text: str, path: str | os.PathLike[str]) -> Path:
    """Atomically write ``text`` to ``path`` as UTF-8, creating parent directories.

    The content is written to a temporary file that replaces the target only once
    complete, so an interrupted run never leaves a truncated file behind.
    """
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    if text and not text.endswith("\n"):
        text += "\n"
    # A uniquely named sibling opened with "x" honours the user's umask, unlike
    # tempfile.mkstemp, which always creates owner-only files.
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        with open(temporary, "x", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return target


# --------------------------------------------------------------------------- helpers


def _envelope(kind: str, retrieved_at: datetime, **payload: Any) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "type": kind,
        "retrieved_at": _timestamp(retrieved_at),
        "source": SOURCE,
        **{key: to_jsonable(value) for key, value in payload.items()},
    }


def _timestamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _dumps(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def _dumps_line(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"


def _csv(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow(["" if value is None else _csv_value(value) for value in row])
    return buffer.getvalue()


def _csv_value(value: Any) -> Any:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, date):
        return value.isoformat()
    return value


def _fmt(value: Any) -> str:
    """Human-friendly value for table output."""
    if value is None or value == "":
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _table(
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    *,
    max_widths: dict[int, int] | None = None,
    indent: str = "  ",
) -> list[str]:
    max_widths = max_widths or {}
    text_rows = [[_fmt(cell) for cell in row] for row in rows]
    for row in text_rows:
        for index, limit in max_widths.items():
            if len(row[index]) > limit:
                row[index] = row[index][: limit - 3] + "..."
    widths = [len(h) for h in headers]
    for row in text_rows:
        widths = [max(w, len(cell)) for w, cell in zip(widths, row, strict=True)]
    lines = [
        indent
        + "  ".join(h.upper().ljust(w) for h, w in zip(headers, widths, strict=True)).rstrip()
    ]
    for row in text_rows:
        lines.append(
            indent + "  ".join(c.ljust(w) for c, w in zip(row, widths, strict=True)).rstrip()
        )
    return lines


def _section(lines: list[str], title: str) -> None:
    lines.extend(["", title])


def _key_values(pairs: Sequence[tuple[str, Any]]) -> list[str]:
    width = max(len(label) for label, _ in pairs)
    return [f"  {label.ljust(width)}  {_fmt(value)}" for label, value in pairs]


# -------------------------------------------------------------------------- vessels

_VESSEL_CSV_HEADERS = (
    "imo",
    "name",
    "flag",
    "flag_code",
    "call_sign",
    "mmsi",
    "gross_tonnage",
    "deadweight",
    "ship_type",
    "year_built",
    "status",
    "status_since",
    "particulars_updated",
    "paris_mou",
    "tokyo_mou",
    "uscg_targeted",
    "registered_owner",
    "ship_manager",
    "ism_manager",
    "class_societies",
    "pandi",
    "inspections",
    "detentions",
    "last_inspection",
    "name_changes",
    "flag_changes",
    "age_years",
    "name_changes_36_months",
    "flag_changes_36_months",
    "management_changes_36_months",
    "inspections_36_months",
    "detentions_36_months",
    "mmsi_matches_flag",
    "observations",
    "warnings",
)


def _company_for_role(vessel: Vessel, role_prefix: str) -> str | None:
    names = [c.name for c in vessel.management if c.role.lower().startswith(role_prefix)]
    return "; ".join(dict.fromkeys(names)) or None


def _vessel_csv_row(vessel: Vessel, today: date) -> list[Any]:
    indicators = compute_indicators(vessel, today)
    dated = [i.date for i in vessel.inspections if i.date]
    return [
        vessel.imo,
        vessel.name,
        vessel.flag,
        vessel.flag_code,
        vessel.call_sign,
        vessel.mmsi,
        vessel.gross_tonnage,
        vessel.deadweight,
        vessel.ship_type,
        vessel.year_built,
        vessel.status,
        vessel.status_since,
        vessel.particulars_updated,
        vessel.flag_performance.paris_mou,
        vessel.flag_performance.tokyo_mou,
        vessel.flag_performance.uscg_targeted,
        _company_for_role(vessel, "registered owner"),
        _company_for_role(vessel, "ship manager"),
        _company_for_role(vessel, "ism manager"),
        "; ".join(s.society for s in vessel.class_status if s.status != "Withdrawn") or None,
        "; ".join(p.name for p in vessel.pandi) or None,
        len(vessel.inspections),
        sum(1 for i in vessel.inspections if i.detained),
        max(dated) if dated else None,
        max(0, len(vessel.name_history) - 1),
        max(0, len(vessel.flag_history) - 1),
        indicators.age_years,
        indicators.name_changes_36_months,
        indicators.flag_changes_36_months,
        indicators.management_changes_36_months,
        indicators.inspections_36_months,
        indicators.detentions_36_months,
        indicators.mmsi_matches_flag,
        "; ".join(indicators.observations) or None,
        "; ".join(vessel.warnings) or None,
    ]


def _render_vessel(vessel: Vessel, fmt: str, retrieved_at: datetime) -> str:
    today = retrieved_at.date()
    if fmt in ("json", "jsonl"):
        document = _envelope(
            "vessel",
            retrieved_at,
            vessel=vessel,
            indicators=compute_indicators(vessel, today),
        )
        return _dumps(document) if fmt == "json" else _dumps_line(document)
    if fmt == "csv":
        return _csv(_VESSEL_CSV_HEADERS, [_vessel_csv_row(vessel, today)])
    return "\n".join(_vessel_table(vessel, compute_indicators(vessel, today))) + "\n"


def _vessel_table(vessel: Vessel, indicators: VesselIndicators) -> list[str]:
    status = vessel.status
    if status and vessel.status_since:
        status = f"{status} (since {vessel.status_since.isoformat()})"
    flag = vessel.flag
    if flag and vessel.flag_code:
        flag = f"{flag} ({vessel.flag_code})"

    title = f"{vessel.name} (IMO {vessel.imo})"
    lines = [title, "=" * len(title)]
    lines += _key_values(
        [
            ("Flag", flag),
            ("Type", vessel.ship_type),
            ("Status", status),
            ("Year built", vessel.year_built and str(vessel.year_built)),
            ("Gross tonnage", vessel.gross_tonnage),
            ("Deadweight", vessel.deadweight),
            ("Call sign", vessel.call_sign),
            ("MMSI", vessel.mmsi),
            ("Particulars updated", vessel.particulars_updated),
        ]
    )

    _section(lines, "Indicators")
    if indicators.observations:
        lines += [f"  * {note}" for note in indicators.observations]
    else:
        lines.append("  No notable indicators")

    performance = vessel.flag_performance
    _section(lines, "Flag performance")
    lines += _key_values(
        [
            ("Paris MoU list", performance.paris_mou),
            ("Tokyo MoU list", performance.tokyo_mou),
            ("USCG targeted flag", performance.uscg_targeted),
            ("IACS classed", performance.iacs_classed),
            (
                "Detention rate (36 months)",
                None
                if performance.detention_rate_36_months is None
                else f"{performance.detention_rate_36_months:.1f}%",
            ),
        ]
    )

    if vessel.management:
        _section(lines, f"Management ({len(vessel.management)})")
        lines += _table(
            ("Role", "Company", "Company no.", "Since"),
            [(c.role, c.name, c.company_id, c.since) for c in vessel.management],
            max_widths={1: 45},
        )

    if vessel.class_status:
        _section(lines, "Classification")
        lines += _table(
            ("Society", "Status", "Since", "Reason"),
            [(c.society, c.status, c.since, c.reason) for c in vessel.class_status],
            max_widths={0: 45, 3: 45},
        )
    if vessel.class_surveys:
        _section(lines, "Class renewal surveys")
        lines += _table(
            ("Society", "Last renewal", "Next renewal"),
            [(s.society, s.last_renewal, s.next_renewal) for s in vessel.class_surveys],
        )
    if vessel.safety_certificates:
        _section(lines, "Safety management certificates")
        lines += _table(
            ("Society", "Status", "Surveyed", "Expires", "Type"),
            [
                (c.society, c.status, c.survey_date, c.expiry_date, c.convention)
                for c in vessel.safety_certificates
            ],
            max_widths={0: 45},
        )
    if vessel.pandi:
        _section(lines, "P&I insurance")
        lines += _table(("Insurer", "Inception"), [(p.name, p.inception) for p in vessel.pandi])

    if vessel.inspections:
        detentions = sum(1 for i in vessel.inspections if i.detained)
        shown = vessel.inspections[:TABLE_INSPECTION_LIMIT]
        _section(
            lines,
            f"PSC inspections ({len(vessel.inspections)} total, {detentions} with detention)",
        )
        lines += _table(
            ("Date", "Authority", "Port", "Detained", "Deficiencies", "Regime"),
            [
                (
                    i.date,
                    i.authority,
                    i.port,
                    i.detained,
                    i.deficiencies,
                    ", ".join(r.psc_organisation or "-" for r in i.reports),
                )
                for i in shown
            ],
            max_widths={2: 30},
        )
        if len(vessel.inspections) > len(shown):
            remaining = len(vessel.inspections) - len(shown)
            lines.append(f"  ... {remaining} older inspections (use --format json to see all)")

    if vessel.name_history:
        _section(lines, "Name history")
        lines += _table(
            ("Name", "Since", "Until"), [(n.name, n.since, n.until) for n in vessel.name_history]
        )
    if vessel.flag_history:
        _section(lines, "Flag history")
        lines += _table(
            ("Flag", "Since", "Until"), [(f.flag, f.since, f.until) for f in vessel.flag_history]
        )
    if vessel.company_history:
        _section(lines, "Company history")
        lines += _table(
            ("Role", "Company", "Since", "Until"),
            [(c.role, c.company, c.since, c.until) for c in vessel.company_history],
            max_widths={1: 45},
        )
    if vessel.sightings:
        _section(lines, "Recent sightings")
        lines += _table(
            ("Period", "Areas", "Source"),
            [
                (s.period, ", ".join(s.areas), s.source)
                for s in vessel.sightings[:TABLE_SIGHTING_LIMIT]
            ],
            max_widths={1: 60},
        )
    if vessel.warnings:
        _section(lines, "Warnings")
        lines += [f"  ! {warning}" for warning in vessel.warnings]
    return lines


# --------------------------------------------------------------------------- search


def _render_search(results: SearchResults, fmt: str, retrieved_at: datetime) -> str:
    if fmt == "json":
        return _dumps(_envelope("search", retrieved_at, search=results))
    if fmt == "jsonl":
        records = [{"kind": "ship", **to_jsonable(s)} for s in results.ships]
        records += [{"kind": "company", **to_jsonable(c)} for c in results.companies]
        return "".join(_dumps_line(r) for r in records)
    if fmt == "csv":
        headers = (
            "kind",
            "imo",
            "company_id",
            "name",
            "gross_tonnage",
            "ship_type",
            "year_built",
            "flag",
            "address",
        )
        rows: list[list[Any]] = [
            ["ship", s.imo, None, s.name, s.gross_tonnage, s.ship_type, s.year_built, s.flag, None]
            for s in results.ships
        ]
        rows += [
            ["company", None, c.company_id, c.name, None, None, None, None, c.address]
            for c in results.companies
        ]
        return _csv(headers, rows)

    lines: list[str] = []
    if results.ships:
        total = results.total_ships or len(results.ships)
        suffix = f", showing {len(results.ships)}" if total > len(results.ships) else ""
        lines.append(f"Ships matching '{results.query}' ({total}{suffix})")
        lines += _table(
            ("IMO", "Name", "Type", "Built", "Gross tonnage", "Flag"),
            [
                (
                    s.imo,
                    s.name,
                    s.ship_type,
                    s.year_built and str(s.year_built),
                    s.gross_tonnage,
                    s.flag,
                )
                for s in results.ships
            ],
            max_widths={2: 35},
        )
    if results.companies:
        if lines:
            lines.append("")
        lines.append(f"Companies matching '{results.query}' ({len(results.companies)})")
        lines += _companies_table(results.companies)
    if not lines:
        lines.append(f"No ships or companies match '{results.query}'")
    return "\n".join(lines) + "\n"


def _companies_table(companies: Sequence[CompanySummary]) -> list[str]:
    return _table(
        ("Company no.", "Name", "Address"),
        [(c.company_id, c.name, c.address) for c in companies],
        max_widths={1: 45, 2: 60},
    )


def render_company_choices(companies: Sequence[CompanySummary]) -> str:
    """Numbered list of companies for disambiguation prompts."""
    rows = [(str(n), c.company_id, c.name, c.address) for n, c in enumerate(companies, start=1)]
    return "\n".join(_table(("#", "Company no.", "Name", "Address"), rows, max_widths={3: 60}))


# ---------------------------------------------------------------------------- fleet

_FLEET_CSV_HEADERS = (
    "company_id",
    "company_name",
    "imo",
    "name",
    "gross_tonnage",
    "ship_type",
    "year_built",
    "flag",
    "class_societies",
    "detentions_as_ism_manager_3y",
    "detentions_all_companies_3y",
    "roles",
)


def _fleet_csv_rows(fleet: Fleet) -> list[list[Any]]:
    return [
        [
            fleet.company.company_id,
            fleet.company.name,
            v.imo,
            v.name,
            v.gross_tonnage,
            v.ship_type,
            v.year_built,
            v.flag,
            "; ".join(v.class_societies) or None,
            v.detentions_as_ism_manager_3y,
            v.detentions_all_companies_3y,
            "; ".join(
                f"{r.role} (since {r.since.isoformat()})" if r.since else r.role for r in v.roles
            )
            or None,
        ]
        for v in fleet.vessels
    ]


def _render_fleet(fleet: Fleet, fmt: str, retrieved_at: datetime) -> str:
    if fmt == "json":
        return _dumps(_envelope("fleet", retrieved_at, fleet=fleet))
    if fmt == "jsonl":
        owner = {"company_id": fleet.company.company_id, "company_name": fleet.company.name}
        return "".join(_dumps_line({**owner, **to_jsonable(v)}) for v in fleet.vessels)
    if fmt == "csv":
        return _csv(_FLEET_CSV_HEADERS, _fleet_csv_rows(fleet))

    company = fleet.company
    title = f"{company.name} (company no. {company.company_id})"
    lines = [title, "=" * len(title)]
    lines += _key_values(
        [
            ("Address", company.address),
            ("Status", company.status),
            ("Last update", company.last_update),
            ("Vessels", fleet.total_vessels or len(fleet.vessels)),
        ]
    )
    if fleet.total_vessels and fleet.total_vessels > len(fleet.vessels):
        lines.append(f"  (showing {len(fleet.vessels)} of {fleet.total_vessels})")
    if fleet.vessels:
        lines.append("")
        lines += _table(
            ("IMO", "Name", "Type", "Built", "Gross tonnage", "Flag", "Detentions (3y)", "Roles"),
            [
                (
                    v.imo,
                    v.name,
                    v.ship_type,
                    v.year_built and str(v.year_built),
                    v.gross_tonnage,
                    v.flag,
                    v.detentions_all_companies_3y,
                    ", ".join(r.role for r in v.roles),
                )
                for v in fleet.vessels
            ],
            max_widths={2: 30, 7: 50},
        )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------- batch


def _batch_item_record(kind: str, item: BatchItem[Any], today: date) -> dict[str, Any]:
    key = "vessel" if kind == "vessels" else "fleet"
    record: dict[str, Any] = {
        "query": item.query,
        "status": item.status.value,
        "error": item.error,
        "warnings": item.warnings,
        "elapsed_seconds": round(item.elapsed_seconds, 2),
        key: to_jsonable(item.result),
    }
    if kind == "vessels":
        record["indicators"] = (
            to_jsonable(compute_indicators(item.result, today))
            if isinstance(item.result, Vessel)
            else None
        )
    return record


def _render_batch(report: BatchReport, fmt: str, retrieved_at: datetime) -> str:
    kind = report.kind
    if fmt in ("json", "jsonl"):
        if fmt == "jsonl":
            return "".join(
                render_batch_item_jsonl(kind, item, retrieved_at.date()) for item in report.items
            )
        summary = {
            "total": len(report.items),
            "succeeded": report.succeeded,
            "failed": report.failed,
            "started_at": _timestamp(report.started_at),
        }
        return _dumps(
            {
                **_envelope(f"batch_{kind}", retrieved_at),
                "summary": summary,
                "results": [
                    _batch_item_record(kind, item, retrieved_at.date()) for item in report.items
                ],
            }
        )

    if fmt == "csv":
        if kind == "vessels":
            rows = []
            for item in report.items:
                vessel_row = (
                    _vessel_csv_row(item.result, retrieved_at.date())
                    if isinstance(item.result, Vessel)
                    else [None] * len(_VESSEL_CSV_HEADERS)
                )
                rows.append([item.query, item.status.value, item.error, *vessel_row])
            return _csv(("query", "lookup_status", "error", *_VESSEL_CSV_HEADERS), rows)
        fleet_rows: list[list[Any]] = []
        for item in report.items:
            if isinstance(item.result, Fleet) and item.result.vessels:
                fleet_rows += [
                    [item.query, item.status.value, item.error, *row]
                    for row in _fleet_csv_rows(item.result)
                ]
            else:
                fleet_rows.append(
                    [item.query, item.status.value, item.error] + [None] * len(_FLEET_CSV_HEADERS)
                )
        return _csv(("query", "lookup_status", "error", *_FLEET_CSV_HEADERS), fleet_rows)

    noun = "vessel" if kind == "vessels" else "company"
    lines = [f"Batch results: {report.succeeded} of {len(report.items)} {noun} lookups succeeded"]
    rows_table: list[tuple[Any, ...]]
    if kind == "vessels":
        rows_table = [
            (
                item.query,
                item.status.value,
                item.result.name if isinstance(item.result, Vessel) else None,
                item.result.flag if isinstance(item.result, Vessel) else None,
                item.result.ship_type if isinstance(item.result, Vessel) else item.error,
            )
            for item in report.items
        ]
        lines += _table(
            ("IMO", "Status", "Name", "Flag", "Type / error"), rows_table, max_widths={4: 60}
        )
    else:
        rows_table = [
            (
                item.query,
                item.status.value,
                item.result.company.name if isinstance(item.result, Fleet) else None,
                item.result.company.company_id if isinstance(item.result, Fleet) else None,
                len(item.result.vessels) if isinstance(item.result, Fleet) else item.error,
            )
            for item in report.items
        ]
        lines += _table(
            ("Query", "Status", "Company", "Company no.", "Vessels / error"),
            rows_table,
            max_widths={0: 30, 2: 40, 4: 60},
        )
    return "\n".join(lines) + "\n"
