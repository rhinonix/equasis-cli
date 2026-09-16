"""In-memory stand-ins for the Equasis client."""

from __future__ import annotations

import copy
from functools import lru_cache
from types import TracebackType

from equasis_cli.exceptions import AuthenticationError, NotFoundError
from equasis_cli.models import CompanySummary, Fleet, SearchResults, ShipSummary, Vessel
from equasis_cli.parsing import (
    merge_vessel,
    parse_fleet,
    parse_history,
    parse_inspections,
    parse_ship_info,
)
from equasis_cli.validation import normalize_imo
from tests.conftest import FIXTURES


def load(name: str) -> str:
    return (FIXTURES / f"{name}.html").read_text(encoding="utf-8")


def fixture_vessel(imo: str = "9074729") -> Vessel:
    return copy.deepcopy(_parsed_vessel(imo))


def fixture_fleet() -> Fleet:
    return copy.deepcopy(_parsed_fleet())


@lru_cache
def _parsed_vessel(imo: str) -> Vessel:
    return merge_vessel(
        parse_ship_info(load(f"ship_info_{imo}")),
        parse_inspections(load(f"inspections_{imo}")),
        parse_history(load(f"history_{imo}")),
    )


@lru_cache
def _parsed_fleet() -> Fleet:
    page = parse_fleet(load("fleet_torm"))
    return Fleet(company=page.company, vessels=page.vessels, total_vessels=page.total_vessels)


class FakeClient:
    """Serves vessels and fleets from fixtures and records calls."""

    def __init__(
        self,
        *,
        vessels: dict[str, Vessel] | None = None,
        companies: list[CompanySummary] | None = None,
        fleets: dict[str, Fleet] | None = None,
        reject_login: bool = False,
    ) -> None:
        self.vessels = vessels if vessels is not None else {"9074729": fixture_vessel()}
        self.companies = companies if companies is not None else []
        self.fleets = fleets if fleets is not None else {}
        self.reject_login = reject_login
        self.calls: list[tuple[str, object]] = []
        self.logged_in = False
        self.closed = False

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self.closed = True

    def login(self) -> None:
        self.calls.append(("login", None))
        if self.reject_login:
            raise AuthenticationError("Equasis rejected the login")
        self.logged_in = True

    def get_vessel(self, imo: str) -> Vessel:
        self.calls.append(("get_vessel", imo))
        if self.reject_login:
            raise AuthenticationError("Equasis rejected the login")
        imo = normalize_imo(imo)
        if imo not in self.vessels:
            raise NotFoundError(f"no vessel with IMO {imo} in Equasis")
        return self.vessels[imo]

    def search(
        self, query: str, *, max_pages: int | None = 3, ships: bool = True, companies: bool = True
    ) -> SearchResults:
        self.calls.append(("search", query))
        matching_ships = [
            ShipSummary(imo=v.imo, name=v.name, flag=v.flag)
            for v in self.vessels.values()
            if query.lower() in v.name.lower()
        ]
        matching_companies = [c for c in self.companies if query.lower() in c.name.lower()]
        return SearchResults(
            query=query,
            ships=matching_ships if ships else [],
            companies=matching_companies if companies else [],
            total_ships=len(matching_ships) if ships else None,
        )

    def search_ships(
        self, *, imo: str | None = None, mmsi: str | None = None, call_sign: str | None = None
    ) -> SearchResults:
        self.calls.append(("search_ships", imo or mmsi or call_sign))
        ships = [
            ShipSummary(imo=v.imo, name=v.name)
            for v in self.vessels.values()
            if v.imo == imo or (mmsi and v.mmsi == mmsi) or (call_sign and v.call_sign == call_sign)
        ]
        return SearchResults(query=str(imo or mmsi or call_sign), ships=ships)

    def get_fleet(self, company_id: str, *, max_pages: int | None = None) -> Fleet:
        self.calls.append(("get_fleet", company_id))
        if company_id not in self.fleets:
            raise NotFoundError(f"no company with number {company_id} in Equasis")
        return self.fleets[company_id]
