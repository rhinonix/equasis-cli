"""Typed data structures for everything equasis-cli retrieves from Equasis.

Dates are :class:`datetime.date` objects and numeric fields are integers, so the
JSON output is unambiguous (ISO 8601 dates, numbers as numbers). Use
:func:`to_jsonable` to convert any model to plain JSON-compatible values.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import enum
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")

SCHEMA_VERSION = 1
"""Version of the JSON document layout; bumped on incompatible changes."""


# --------------------------------------------------------------------------- vessels


@dataclass(kw_only=True)
class FlagPerformance:
    """Flag-state ratings shown in the Ship Info overview panel."""

    paris_mou: str | None = None
    tokyo_mou: str | None = None
    uscg_targeted: bool | None = None
    iacs_classed: bool | None = None
    detention_rate_36_months: float | None = None
    """Percentage of inspections that led to a detention in the last 36 months."""


@dataclass(kw_only=True)
class CompanyRole:
    """A company currently associated with a vessel (Management detail panel)."""

    company_id: str | None
    name: str
    role: str
    address: str | None = None
    since: dt.date | None = None


@dataclass(kw_only=True)
class ClassStatus:
    """Classification society status (Classification panel)."""

    society: str
    status: str | None = None
    since: dt.date | None = None
    reason: str | None = None


@dataclass(kw_only=True)
class ClassSurvey:
    """Renewal surveys recorded by a classification society."""

    society: str
    last_renewal: dt.date | None = None
    next_renewal: dt.date | None = None


@dataclass(kw_only=True)
class SafetyCertificate:
    """Safety management certificate issued by a recognised organisation."""

    society: str
    survey_date: dt.date | None = None
    expiry_date: dt.date | None = None
    status_change_date: dt.date | None = None
    status: str | None = None
    reason: str | None = None
    convention: str | None = None


@dataclass(kw_only=True)
class PandIInsurer:
    """Protection and indemnity insurance."""

    name: str
    inception: dt.date | None = None


@dataclass(kw_only=True)
class Sighting:
    """Geographical area where the vessel was reported."""

    period: str
    areas: list[str] = field(default_factory=list)
    source: str | None = None


@dataclass(kw_only=True)
class InspectionReport:
    """One PSC regime's report of an inspection.

    The same inspection can be reported to several PSC regimes (MoUs), which may
    record different inspection types or deficiency counts.
    """

    psc_organisation: str | None
    inspection_type: str | None = None
    duration_days: int | None = None
    deficiencies: int | None = None
    inspection_id: str | None = None


@dataclass(kw_only=True)
class Inspection:
    """A port state control inspection."""

    authority: str | None
    port: str | None
    date: dt.date | None
    detained: bool | None
    reports: list[InspectionReport] = field(default_factory=list)

    @property
    def deficiencies(self) -> int | None:
        """Highest deficiency count reported for this inspection by any regime."""
        counts = [r.deficiencies for r in self.reports if r.deficiencies is not None]
        return max(counts) if counts else None


@dataclass(kw_only=True)
class HumanElementDeficiency:
    """Human element (ILO) deficiencies recorded during an inspection."""

    psc_organisation: str | None
    authority: str | None
    port: str | None
    inspection_type: str | None
    date: dt.date | None
    deficiencies: int | None


@dataclass(kw_only=True)
class NameChange:
    """A historical vessel name. ``until`` is derived from the next newer record."""

    name: str
    since: dt.date | None
    until: dt.date | None = None
    source: str | None = None


@dataclass(kw_only=True)
class FlagChange:
    """A historical flag registration."""

    flag: str
    since: dt.date | None
    until: dt.date | None = None
    source: str | None = None


@dataclass(kw_only=True)
class ClassChange:
    """A historical classification society survey."""

    society: str
    survey_date: dt.date | None
    source: str | None = None


@dataclass(kw_only=True)
class CompanyChange:
    """A historical company role (owner, ship manager, ISM manager, ...)."""

    company: str
    role: str
    since: dt.date | None
    until: dt.date | None = None
    source: str | None = None


@dataclass(kw_only=True)
class Vessel:
    """A complete vessel profile assembled from the Ship Info, Inspections and
    Ship History pages."""

    imo: str
    name: str
    flag: str | None = None
    flag_code: str | None = None
    call_sign: str | None = None
    mmsi: str | None = None
    gross_tonnage: int | None = None
    deadweight: int | None = None
    ship_type: str | None = None
    year_built: int | None = None
    status: str | None = None
    status_since: dt.date | None = None
    particulars_updated: dt.date | None = None

    flag_performance: FlagPerformance = field(default_factory=FlagPerformance)
    management: list[CompanyRole] = field(default_factory=list)
    class_status: list[ClassStatus] = field(default_factory=list)
    class_surveys: list[ClassSurvey] = field(default_factory=list)
    safety_certificates: list[SafetyCertificate] = field(default_factory=list)
    pandi: list[PandIInsurer] = field(default_factory=list)
    sightings: list[Sighting] = field(default_factory=list)

    inspections: list[Inspection] = field(default_factory=list)
    human_element_deficiencies: list[HumanElementDeficiency] = field(default_factory=list)

    name_history: list[NameChange] = field(default_factory=list)
    flag_history: list[FlagChange] = field(default_factory=list)
    class_history: list[ClassChange] = field(default_factory=list)
    company_history: list[CompanyChange] = field(default_factory=list)

    warnings: list[str] = field(default_factory=list)
    """Problems that left parts of the profile incomplete (for example an
    Inspections page that could not be parsed)."""

    retrieved_at: dt.datetime | None = None
    """When the underlying Equasis pages were fetched (earlier if served from cache)."""


# --------------------------------------------------------------------- search and fleet


@dataclass(kw_only=True)
class ShipSummary:
    """A vessel as listed in search results."""

    imo: str
    name: str
    gross_tonnage: int | None = None
    ship_type: str | None = None
    year_built: int | None = None
    flag: str | None = None


@dataclass(kw_only=True)
class CompanySummary:
    """A company as listed in search results."""

    company_id: str
    name: str
    address: str | None = None


@dataclass(kw_only=True)
class SearchResults:
    """Ships and companies matching a search."""

    query: str
    ships: list[ShipSummary] = field(default_factory=list)
    companies: list[CompanySummary] = field(default_factory=list)
    total_ships: int | None = None
    """Total ship matches reported by Equasis (may exceed ``len(ships)`` if truncated)."""
    retrieved_at: dt.datetime | None = None


@dataclass(kw_only=True)
class RoleSince:
    """A role a company holds for a fleet vessel."""

    role: str
    since: dt.date | None = None


@dataclass(kw_only=True)
class FleetVessel:
    """A vessel in a company's fleet."""

    imo: str
    name: str
    gross_tonnage: int | None = None
    ship_type: str | None = None
    year_built: int | None = None
    flag: str | None = None
    class_societies: list[str] = field(default_factory=list)
    detentions_as_ism_manager_3y: int | None = None
    detentions_all_companies_3y: int | None = None
    roles: list[RoleSince] = field(default_factory=list)


@dataclass(kw_only=True)
class Company:
    """Company details shown at the top of the Fleet info page."""

    company_id: str
    name: str
    address: str | None = None
    status: str | None = None
    last_update: dt.date | None = None


@dataclass(kw_only=True)
class Fleet:
    """A company and the vessels it is associated with."""

    company: Company
    vessels: list[FleetVessel] = field(default_factory=list)
    total_vessels: int | None = None
    """Total reported by Equasis (may exceed ``len(vessels)`` if truncated)."""
    retrieved_at: dt.datetime | None = None


# ------------------------------------------------------------------------------- batch


class ItemStatus(str, enum.Enum):
    """Outcome of one item in a batch operation."""

    OK = "ok"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"
    ERROR = "error"


@dataclass(kw_only=True)
class BatchItem(Generic[T]):
    """Result for one input of a batch operation."""

    query: str
    status: ItemStatus
    result: T | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0


# ------------------------------------------------------------------------ serialization


def to_jsonable(value: Any) -> Any:
    """Convert models (and containers of them) into JSON-compatible values."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        data = {f.name: to_jsonable(getattr(value, f.name)) for f in dataclasses.fields(value)}
        if isinstance(value, Inspection):
            data["deficiencies"] = value.deficiencies
        return data
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, dt.datetime):
        return value.isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    return value
