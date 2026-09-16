"""Factual indicators derived from a vessel profile.

Indicators summarise signals that researchers commonly look at when assessing a
vessel: frequent changes of name, flag or management, recent detentions, flag
performance, classification problems, and whether the MMSI is consistent with
the flag. Each indicator is a plain fact taken from Equasis data. No score is
computed, because any weighting of these signals would be arbitrary.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date

from ..models import ClassStatus, CompanyChange, FlagChange, Inspection, NameChange, Vessel
from .reference import mmsi_country

RECENT_MONTHS = 12
WINDOW_MONTHS = 36
MANAGEMENT_ROLES = ("registered owner", "ship manager", "ism manager")
CONCERNING_LISTS = ("grey", "gray", "black")


@dataclass(kw_only=True)
class VesselIndicators:
    """Derived indicators for one vessel, relative to ``reference_date``."""

    reference_date: date
    age_years: int | None = None

    name_changes_12_months: int = 0
    name_changes_36_months: int = 0
    flag_changes_12_months: int = 0
    flag_changes_36_months: int = 0
    management_changes_36_months: int = 0
    """Changes of registered owner, ship manager, or ISM manager."""

    inspections_36_months: int = 0
    detentions_36_months: int = 0
    deficiencies_36_months: int = 0
    last_inspection: date | None = None
    last_detention: date | None = None

    flag_on_paris_mou_grey_or_black_list: bool | None = None
    flag_on_tokyo_mou_grey_or_black_list: bool | None = None
    uscg_targeted_flag: bool | None = None
    iacs_classed: bool | None = None
    class_withdrawn_or_suspended_36_months: list[str] = field(default_factory=list)
    has_pandi_insurance: bool = False

    mmsi_country: str | None = None
    """Country allocated the MMSI's Maritime Identification Digits."""
    mmsi_matches_flag: bool | None = None

    observations: list[str] = field(default_factory=list)
    """Plain-language summary of the notable indicators."""


def months_before(reference: date, months: int) -> date:
    """The same day ``months`` months earlier (clamped to the end of short months)."""
    total = reference.year * 12 + reference.month - 1 - months
    year, month = divmod(total, 12)
    month += 1
    for day in (reference.day, 30, 29, 28):
        try:
            return date(year, month, day)
        except ValueError:
            continue
    raise AssertionError("unreachable")  # pragma: no cover


def _changes_since(records: Sequence[NameChange | FlagChange], cutoff: date) -> int:
    """Records that started on or after ``cutoff``, excluding the first registration."""
    changes = records[:-1]  # the oldest record is the original name or flag, not a change
    return sum(1 for r in changes if r.since is not None and r.since >= cutoff)


def _management_changes(history: Sequence[CompanyChange], cutoff: date) -> int:
    count = 0
    for role in MANAGEMENT_ROLES:
        records = [c for c in history if c.role.lower().startswith(role)]
        count += sum(1 for c in records[:-1] if c.since is not None and c.since >= cutoff)
    return count


def _on_concerning_list(value: str | None) -> bool | None:
    if not value:
        return None
    return value.strip().lower() in CONCERNING_LISTS


def _recent_inspections(inspections: Sequence[Inspection], cutoff: date) -> list[Inspection]:
    return [i for i in inspections if i.date is not None and i.date >= cutoff]


def _class_problems(statuses: Sequence[ClassStatus], cutoff: date) -> list[str]:
    return [
        f"{s.society}: {s.status}"
        for s in statuses
        if (s.status or "").lower() in ("withdrawn", "suspended")
        and s.since is not None
        and s.since >= cutoff
    ]


def compute_indicators(vessel: Vessel, reference_date: date | None = None) -> VesselIndicators:
    """Derive indicators for ``vessel`` as of ``reference_date`` (default: today)."""
    today = reference_date or date.today()
    recent = months_before(today, RECENT_MONTHS)
    window = months_before(today, WINDOW_MONTHS)
    performance = vessel.flag_performance

    indicators = VesselIndicators(
        reference_date=today,
        age_years=today.year - vessel.year_built if vessel.year_built else None,
        name_changes_12_months=_changes_since(vessel.name_history, recent),
        name_changes_36_months=_changes_since(vessel.name_history, window),
        flag_changes_12_months=_changes_since(vessel.flag_history, recent),
        flag_changes_36_months=_changes_since(vessel.flag_history, window),
        management_changes_36_months=_management_changes(vessel.company_history, window),
        flag_on_paris_mou_grey_or_black_list=_on_concerning_list(performance.paris_mou),
        flag_on_tokyo_mou_grey_or_black_list=_on_concerning_list(performance.tokyo_mou),
        uscg_targeted_flag=performance.uscg_targeted,
        iacs_classed=performance.iacs_classed,
        class_withdrawn_or_suspended_36_months=_class_problems(vessel.class_status, window),
        has_pandi_insurance=bool(vessel.pandi),
    )

    recent_inspections = _recent_inspections(vessel.inspections, window)
    indicators.inspections_36_months = len(recent_inspections)
    indicators.detentions_36_months = sum(1 for i in recent_inspections if i.detained)
    indicators.deficiencies_36_months = sum(i.deficiencies or 0 for i in recent_inspections)
    dated = [i for i in vessel.inspections if i.date is not None]
    if dated:
        indicators.last_inspection = max(i.date for i in dated if i.date)
        detained = [i.date for i in dated if i.detained and i.date]
        indicators.last_detention = max(detained) if detained else None

    allocated = mmsi_country(vessel.mmsi)
    if allocated:
        indicators.mmsi_country = allocated.name
        if vessel.flag_code:
            indicators.mmsi_matches_flag = allocated.alpha3 == vessel.flag_code.upper()

    indicators.observations = _observations(vessel, indicators)
    return indicators


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


def _observations(vessel: Vessel, ind: VesselIndicators) -> list[str]:
    notes: list[str] = []
    if ind.name_changes_36_months:
        notes.append(f"Renamed {_plural(ind.name_changes_36_months, 'time')} in the last 36 months")
    if ind.flag_changes_36_months:
        notes.append(
            f"Changed flag {_plural(ind.flag_changes_36_months, 'time')} in the last 36 months"
        )
    if ind.management_changes_36_months >= 2:
        notes.append(
            f"{ind.management_changes_36_months} changes of owner or manager in the last 36 months"
        )
    if ind.detentions_36_months:
        notes.append(f"Detained {_plural(ind.detentions_36_months, 'time')} in the last 36 months")
    lists = [
        name
        for name, flagged in (
            ("Paris MoU", ind.flag_on_paris_mou_grey_or_black_list),
            ("Tokyo MoU", ind.flag_on_tokyo_mou_grey_or_black_list),
        )
        if flagged
    ]
    if lists:
        notes.append(f"Flag is on the grey or black list of the {' and '.join(lists)}")
    if ind.uscg_targeted_flag:
        notes.append("Flag is targeted by the US Coast Guard")
    if ind.iacs_classed is False:
        notes.append("Not classed by an IACS member society")
    for problem in ind.class_withdrawn_or_suspended_36_months:
        notes.append(
            f"Class {problem.split(': ', 1)[1].lower()} in the last 36 months "
            f"({problem.split(': ', 1)[0]})"
        )
    if ind.mmsi_matches_flag is False:
        notes.append(
            f"MMSI {vessel.mmsi} is allocated to {ind.mmsi_country}, not the flag state "
            f"({vessel.flag})"
        )
    if not ind.has_pandi_insurance and vessel.status and "service" in vessel.status.lower():
        notes.append("No P&I insurer recorded in Equasis")
    if ind.inspections_36_months == 0 and vessel.status and "service" in vessel.status.lower():
        notes.append("No port state control inspections recorded in the last 36 months")
    return notes
