"""High-level Equasis client: authentication, vessel lookups, search, and fleets."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from types import TracebackType

from .exceptions import (
    AuthenticationError,
    EquasisError,
    LayoutChangedError,
    NotFoundError,
    SessionExpiredError,
)
from .models import Fleet, SearchResults, Vessel
from .parsing import (
    PageKind,
    classify,
    is_logged_in,
    merge_vessel,
    parse_fleet,
    parse_history,
    parse_inspections,
    parse_search,
    parse_ship_info,
)
from .transport import Transport
from .validation import normalize_company_id, normalize_imo, normalize_mmsi

logger = logging.getLogger(__name__)

_LOGIN_PATH = "authen/HomePage?fs=HomePage"
_SEARCH_PATH = "restricted/Search?fs=Search"
_FLEET_PATH = "restricted/FleetInfo?fs=CompanyInfo"

DEFAULT_SEARCH_PAGES = 3
"""Search result pages fetched by default (Equasis shows 100 results per page)."""

MAX_FLEET_PAGES = 50
"""Safety limit for fleet pagination (5,000 vessels)."""


class EquasisClient:
    """Authenticated access to Equasis.

    The client logs in lazily on first use and transparently logs in again if
    the session expires. Use it as a context manager to release the HTTP session::

        with EquasisClient(username, password) as client:
            vessel = client.get_vessel("9811000")
    """

    def __init__(self, username: str, password: str, *, transport: Transport | None = None):
        if not username or not password:
            raise AuthenticationError("an Equasis username and password are required")
        self._username = username
        self._password = password
        self.transport = transport or Transport()
        self._logged_in = False

    # ------------------------------------------------------------------ lifecycle

    def __enter__(self) -> EquasisClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self.transport.close()

    @property
    def logged_in(self) -> bool:
        return self._logged_in

    def login(self) -> None:
        """Log in to Equasis.

        Raises:
            AuthenticationError: if Equasis rejects the credentials.
            NetworkError: if Equasis cannot be reached.
        """
        self._logged_in = False
        self.transport.get(_LOGIN_PATH)
        html = self.transport.post(
            _LOGIN_PATH,
            {"j_email": self._username, "j_password": self._password, "submit": "Login"},
        )
        if not is_logged_in(html):
            raise AuthenticationError(
                "Equasis rejected the login; check your username (e-mail) and password"
            )
        self._logged_in = True
        logger.info("logged in to Equasis")

    def _page(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        data: Mapping[str, str] | None = None,
    ) -> str:
        """Fetch an authenticated page, logging in again once if the session expired."""
        if not self._logged_in:
            self.login()
        html = self.transport.request(method, path, params=params, data=data)
        if classify(html) is PageKind.LOGIN:
            logger.info("Equasis session expired; logging in again")
            self.login()
            html = self.transport.request(method, path, params=params, data=data)
            if classify(html) is PageKind.LOGIN:
                self._logged_in = False
                raise SessionExpiredError("Equasis ended the session and it could not be renewed")
        return html

    # -------------------------------------------------------------------- vessels

    def get_vessel(self, imo: str) -> Vessel:
        """Retrieve a full vessel profile (Ship Info, Inspections and Ship History).

        If the Inspections or Ship History page cannot be parsed, the profile is
        still returned and the problem is recorded in ``Vessel.warnings``.

        Raises:
            InvalidInputError: if ``imo`` is not a 7-digit number.
            NotFoundError: if Equasis has no vessel with this IMO number.
            LayoutChangedError: if the Ship Info page cannot be parsed.
        """
        imo = normalize_imo(imo)
        params = {"fs": "ShipInfo", "P_IMO": imo}
        try:
            vessel = parse_ship_info(self._page("GET", "restricted/ShipInfo", params=params))
        except NotFoundError:
            raise NotFoundError(f"no vessel with IMO {imo} in Equasis") from None

        inspections = None
        try:
            inspections = parse_inspections(
                self._page("GET", "restricted/ShipInspection", params=params)
            )
        except LayoutChangedError as exc:
            vessel.warnings.append(f"inspections unavailable: {exc}")
            logger.warning("could not parse inspections for IMO %s: %s", imo, exc)

        history = None
        try:
            history = parse_history(self._page("GET", "restricted/ShipHistory", params=params))
        except LayoutChangedError as exc:
            vessel.warnings.append(f"ship history unavailable: {exc}")
            logger.warning("could not parse ship history for IMO %s: %s", imo, exc)

        return merge_vessel(vessel, inspections, history)

    # --------------------------------------------------------------------- search

    def search(
        self,
        query: str,
        *,
        max_pages: int | None = DEFAULT_SEARCH_PAGES,
        ships: bool = True,
        companies: bool = True,
    ) -> SearchResults:
        """Search ships and companies by name (partial matches).

        Args:
            query: Text to search for.
            max_pages: Maximum result pages to fetch per result type (100 results
                per page); ``None`` fetches every page.
            ships: Include ship results (and fetch their additional pages).
            companies: Include company results (and fetch their additional pages).
        """
        query = query.strip()
        if not query:
            raise EquasisError("search text must not be empty")
        first = parse_search(
            self._page(
                "POST",
                _SEARCH_PATH,
                data={
                    "P_PAGE": "1",
                    "P_PAGE_COMP": "1",
                    "P_PAGE_SHIP": "1",
                    "P_ENTREE_ENTETE": query,
                    "P_ENTREE_ENTETE_HIDDEN": query,
                },
            )
        )
        results = SearchResults(
            query=query,
            ships=list(first.ships) if ships else [],
            companies=list(first.companies) if companies else [],
            total_ships=first.total_ships if ships else None,
        )

        def follow_up(tab: str, page_number: int) -> dict[str, str]:
            return {
                "P_PAGE": "1",
                "P_PAGE_COMP": str(page_number) if tab == "comp" else "1",
                "P_PAGE_SHIP": str(page_number) if tab == "ship" else "1",
                "ongletActifSC": tab,
                "P_ENTREE_HOME_HIDDEN": query,
                "P_ENTREE": query,
                "checkbox-shipSearch": "Ship",
                "checkbox-companySearch": "Company",
            }

        ship_pages = _page_limit(first.last_ship_page, max_pages) if ships else 1
        for number in range(2, ship_pages + 1):
            page = parse_search(self._page("POST", _SEARCH_PATH, data=follow_up("ship", number)))
            new = [s for s in page.ships if s.imo not in {x.imo for x in results.ships}]
            if not new:
                break
            results.ships.extend(new)

        company_pages = _page_limit(first.last_company_page, max_pages) if companies else 1
        for number in range(2, company_pages + 1):
            page = parse_search(self._page("POST", _SEARCH_PATH, data=follow_up("comp", number)))
            known = {c.company_id for c in results.companies}
            new_companies = [c for c in page.companies if c.company_id not in known]
            if not new_companies:
                break
            results.companies.extend(new_companies)

        return results

    def search_ships(
        self,
        *,
        imo: str | None = None,
        mmsi: str | None = None,
        call_sign: str | None = None,
    ) -> SearchResults:
        """Look up ships by exact identifier using Equasis advanced search."""
        if not any((imo, mmsi, call_sign)):
            raise EquasisError("provide an IMO number, MMSI, or call sign")
        data = {
            "P_PAGE": "1",
            "P_PAGE_COMP": "1",
            "P_PAGE_SHIP": "1",
            "ongletActifSC": "ship",
            "P_ENTREE_HOME_HIDDEN": "",
            "P_IMO": normalize_imo(imo) if imo else "",
            "P_CALLSIGN": call_sign.strip().upper() if call_sign else "",
            "P_NAME": "",
            "P_MMSI": normalize_mmsi(mmsi) if mmsi else "",
            "buttonAdvancedSearch": "advancedOk",
        }
        page = parse_search(self._page("POST", _SEARCH_PATH, data=data))
        query = " ".join(
            f"{label}={value}"
            for label, value in (("imo", imo), ("mmsi", mmsi), ("call_sign", call_sign))
            if value
        )
        return SearchResults(query=query, ships=page.ships, total_ships=len(page.ships))

    # ---------------------------------------------------------------------- fleet

    def get_fleet(self, company_id: str, *, max_pages: int | None = None) -> Fleet:
        """Retrieve every vessel associated with an Equasis company number.

        Raises:
            InvalidInputError: if ``company_id`` is not a 7-digit number.
            NotFoundError: if Equasis has no company with this number.
        """
        company_id = normalize_company_id(company_id)

        def fetch(page_number: int) -> str:
            return self._page(
                "POST",
                _FLEET_PATH,
                data={"P_PAGE": str(page_number), "P_COMP": company_id, "ongletActifSC": "comp"},
            )

        html = fetch(1)
        if classify(html) in (PageKind.NOT_FOUND, PageKind.ERROR):
            raise NotFoundError(f"no company with number {company_id} in Equasis")
        first = parse_fleet(html)
        fleet = Fleet(
            company=first.company, vessels=list(first.vessels), total_vessels=first.total_vessels
        )

        last = min(_page_limit(first.last_page, max_pages), MAX_FLEET_PAGES)
        for number in range(2, last + 1):
            page = parse_fleet(fetch(number))
            known = {v.imo for v in fleet.vessels}
            new = [v for v in page.vessels if v.imo not in known]
            if not new:
                break
            fleet.vessels.extend(new)
        return fleet


def _page_limit(last_page: int, max_pages: int | None) -> int:
    return last_page if max_pages is None else max(1, min(last_page, max_pages))
