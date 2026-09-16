"""Operations shared by the command-line and interactive interfaces.

Both interfaces call these functions, so validation, batch behaviour and company
disambiguation are identical whichever way equasis-cli is used.
"""

from __future__ import annotations

import enum
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field

from .client import EquasisClient
from .exceptions import (
    AuthenticationError,
    EquasisError,
    InvalidInputError,
    NotFoundError,
)
from .models import BatchItem, CompanySummary, Fleet, ItemStatus, Vessel
from .validation import imo_check_digit_valid, normalize_company_id, normalize_imo

LARGE_BATCH_WARNING_THRESHOLD = 100
"""Batches larger than this trigger a reminder about Equasis usage limits."""

StartCallback = Callable[[int, int, str], None]
"""Called as ``callback(position, total, query)`` before each batch item starts."""


def imo_warnings(imo: str) -> list[str]:
    """Non-fatal problems with a well-formed IMO number."""
    if imo_check_digit_valid(imo):
        return []
    return [f"IMO {imo} fails the IMO check digit; it may contain a typo"]


# ----------------------------------------------------------------------------- vessels


def iter_vessels(
    client: EquasisClient,
    queries: Sequence[str],
    *,
    fail_fast: bool = False,
    on_start: StartCallback | None = None,
) -> Iterator[BatchItem[Vessel]]:
    """Look up vessels one at a time, yielding a result for every query.

    Invalid IMO numbers and missing vessels are reported per item rather than
    stopping the batch, unless ``fail_fast`` is set. Authentication failures
    always stop the batch because every later lookup would fail too.
    """
    total = len(queries)
    for position, query in enumerate(queries, start=1):
        if on_start:
            on_start(position, total, query)
        started = time.monotonic()
        item: BatchItem[Vessel]
        warnings: list[str] = []
        try:
            imo = normalize_imo(query)
            warnings = imo_warnings(imo)
            vessel = client.get_vessel(imo)
            item = BatchItem(query=query, status=ItemStatus.OK, result=vessel)
            warnings += vessel.warnings
        except AuthenticationError:
            raise
        except NotFoundError as exc:
            item = BatchItem(query=query, status=ItemStatus.NOT_FOUND, error=str(exc))
        except EquasisError as exc:
            item = BatchItem(query=query, status=ItemStatus.ERROR, error=str(exc))
        item.warnings = warnings
        item.elapsed_seconds = time.monotonic() - started
        yield item
        if fail_fast and item.status is not ItemStatus.OK:
            return


# ---------------------------------------------------------------------------- companies


class Resolution(enum.Enum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"


@dataclass
class CompanyMatch:
    """Outcome of turning a company name into an Equasis company number."""

    query: str
    resolution: Resolution
    company: CompanySummary | None = None
    candidates: list[CompanySummary] = field(default_factory=list)


def is_company_id(query: str) -> bool:
    try:
        normalize_company_id(query)
    except InvalidInputError:
        return False
    return True


def resolve_company(client: EquasisClient, query: str) -> CompanyMatch:
    """Find the company a user means.

    A case-insensitive exact name match wins, as does a search with a single
    result. Otherwise the match is ambiguous and ``candidates`` lists the options,
    exact matches first.
    """
    query = query.strip()
    if not query:
        raise InvalidInputError("company name must not be empty")
    companies = client.search(query, max_pages=None, ships=False).companies
    if not companies:
        return CompanyMatch(query=query, resolution=Resolution.NOT_FOUND)

    wanted = query.casefold()
    exact = [c for c in companies if c.name.casefold() == wanted]
    if len(exact) == 1:
        return CompanyMatch(query, Resolution.RESOLVED, company=exact[0], candidates=companies)
    if len(companies) == 1:
        return CompanyMatch(query, Resolution.RESOLVED, company=companies[0], candidates=companies)
    ordered = exact + [c for c in companies if c not in exact]
    return CompanyMatch(query=query, resolution=Resolution.AMBIGUOUS, candidates=ordered)


def describe_candidates(candidates: Sequence[CompanySummary], limit: int = 5) -> str:
    shown = ", ".join(f"{c.name} ({c.company_id})" for c in candidates[:limit])
    more = len(candidates) - limit
    return shown + (f", and {more} more" if more > 0 else "")


def iter_fleets(
    client: EquasisClient,
    queries: Sequence[str],
    *,
    first_match: bool = False,
    fail_fast: bool = False,
    max_pages: int | None = None,
    on_start: StartCallback | None = None,
) -> Iterator[BatchItem[Fleet]]:
    """Retrieve fleets for company names or 7-digit company numbers.

    Ambiguous names are reported as ``ambiguous`` with the candidates listed in
    the error, unless ``first_match`` is set, in which case the best candidate is
    used and a warning is recorded.
    """
    total = len(queries)
    for position, query in enumerate(queries, start=1):
        if on_start:
            on_start(position, total, query)
        started = time.monotonic()
        item: BatchItem[Fleet]
        try:
            warnings: list[str] = []
            if is_company_id(query):
                company_id = normalize_company_id(query)
            else:
                match = resolve_company(client, query)
                if match.resolution is Resolution.NOT_FOUND:
                    raise NotFoundError(f"no company matches '{query}'")
                if match.resolution is Resolution.AMBIGUOUS:
                    if not first_match:
                        item = BatchItem(
                            query=query,
                            status=ItemStatus.AMBIGUOUS,
                            error=(
                                f"{len(match.candidates)} companies match '{query}': "
                                f"{describe_candidates(match.candidates)}; "
                                "use a company number or --first-match"
                            ),
                        )
                        item.elapsed_seconds = time.monotonic() - started
                        yield item
                        if fail_fast:
                            return
                        continue
                    chosen = match.candidates[0]
                    warnings.append(
                        f"'{query}' matched {len(match.candidates)} companies; "
                        f"using {chosen.name} ({chosen.company_id})"
                    )
                elif match.company is not None:
                    chosen = match.company
                else:  # pragma: no cover - RESOLVED always carries a company
                    raise EquasisError(f"could not resolve company '{query}'")
                company_id = chosen.company_id
            fleet = client.get_fleet(company_id, max_pages=max_pages)
            item = BatchItem(query=query, status=ItemStatus.OK, result=fleet, warnings=warnings)
        except AuthenticationError:
            raise
        except NotFoundError as exc:
            item = BatchItem(query=query, status=ItemStatus.NOT_FOUND, error=str(exc))
        except EquasisError as exc:
            item = BatchItem(query=query, status=ItemStatus.ERROR, error=str(exc))
        item.elapsed_seconds = time.monotonic() - started
        yield item
        if fail_fast and item.status is not ItemStatus.OK:
            return
