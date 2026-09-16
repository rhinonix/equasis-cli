"""Tests for the Equasis client against recorded pages."""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import parse_qs

import pytest
import responses

from equasis_cli.client import EquasisClient
from equasis_cli.exceptions import AuthenticationError, NotFoundError, SessionExpiredError
from equasis_cli.transport import BASE_URL, RetryPolicy, Transport

Loader = Callable[[str], str]
LOGIN_URL = BASE_URL + "authen/HomePage?fs=HomePage"
SEARCH_URL = BASE_URL + "restricted/Search?fs=Search"
FLEET_URL = BASE_URL + "restricted/FleetInfo?fs=CompanyInfo"


def ship_url(page: str, imo: str) -> str:
    return f"{BASE_URL}restricted/{page}?fs=ShipInfo&P_IMO={imo}"


@pytest.fixture
def client() -> EquasisClient:
    transport = Transport(min_interval=0, retry=RetryPolicy(max_retries=0), sleep=lambda _: None)
    return EquasisClient("user@example.com", "secret", transport=transport)


def mock_login(fixture_html: Loader, *, succeed: bool = True) -> None:
    responses.get(LOGIN_URL, body=fixture_html("login_page"))
    responses.post(LOGIN_URL, body=fixture_html("home_logged_in" if succeed else "login_page"))


def form(call_index: int) -> dict[str, str]:
    body = responses.calls[call_index].request.body
    text = body.decode() if isinstance(body, bytes) else str(body)
    return {key: values[0] for key, values in parse_qs(text).items()}


@responses.activate
def test_login_posts_credentials(client: EquasisClient, fixture_html: Loader) -> None:
    mock_login(fixture_html)
    client.login()
    assert client.logged_in
    assert form(1) == {"j_email": "user@example.com", "j_password": "secret", "submit": "Login"}


@responses.activate
def test_rejected_login_raises(client: EquasisClient, fixture_html: Loader) -> None:
    mock_login(fixture_html, succeed=False)
    with pytest.raises(AuthenticationError):
        client.login()
    assert not client.logged_in


def test_credentials_are_required() -> None:
    with pytest.raises(AuthenticationError):
        EquasisClient("", "")


@responses.activate
def test_get_vessel_combines_all_pages(client: EquasisClient, fixture_html: Loader) -> None:
    mock_login(fixture_html)
    responses.get(ship_url("ShipInfo", "9074729"), body=fixture_html("ship_info_9074729"))
    responses.get(ship_url("ShipInspection", "9074729"), body=fixture_html("inspections_9074729"))
    responses.get(ship_url("ShipHistory", "9074729"), body=fixture_html("history_9074729"))

    vessel = client.get_vessel("IMO 9074729")

    assert vessel.name == "KAVITA"
    assert len(vessel.inspections) == 83
    assert vessel.name_history[0].name == "KAVITA"
    assert vessel.company_history
    assert vessel.warnings == []


@responses.activate
def test_expired_session_is_renewed_transparently(
    client: EquasisClient, fixture_html: Loader
) -> None:
    mock_login(fixture_html)
    mock_login(fixture_html)
    responses.get(ship_url("ShipInfo", "9811000"), body=fixture_html("login_page"))
    responses.get(ship_url("ShipInfo", "9811000"), body=fixture_html("ship_info_9811000"))
    responses.get(ship_url("ShipInspection", "9811000"), body=fixture_html("inspections_9811000"))
    responses.get(ship_url("ShipHistory", "9811000"), body=fixture_html("history_9811000"))

    vessel = client.get_vessel("9811000")

    assert vessel.name == "EVER GIVEN"
    login_posts = [c for c in responses.calls if c.request.method == "POST"]
    assert len(login_posts) == 2


@responses.activate
def test_session_that_cannot_be_renewed_raises(client: EquasisClient, fixture_html: Loader) -> None:
    mock_login(fixture_html)
    mock_login(fixture_html)
    responses.get(ship_url("ShipInfo", "9811000"), body=fixture_html("login_page"))
    responses.get(ship_url("ShipInfo", "9811000"), body=fixture_html("login_page"))

    with pytest.raises(SessionExpiredError):
        client.get_vessel("9811000")


@responses.activate
def test_unknown_vessel_raises_not_found(client: EquasisClient, fixture_html: Loader) -> None:
    mock_login(fixture_html)
    responses.get(ship_url("ShipInfo", "1234567"), body=fixture_html("ship_not_found"))

    with pytest.raises(NotFoundError, match="1234567"):
        client.get_vessel("1234567")


@responses.activate
def test_unparseable_secondary_page_becomes_a_warning(
    client: EquasisClient, fixture_html: Loader
) -> None:
    mock_login(fixture_html)
    broken = fixture_html("inspections_9811000").replace("Date of report", "Reported")
    responses.get(ship_url("ShipInfo", "9811000"), body=fixture_html("ship_info_9811000"))
    responses.get(ship_url("ShipInspection", "9811000"), body=broken)
    responses.get(ship_url("ShipHistory", "9811000"), body=fixture_html("history_9811000"))

    vessel = client.get_vessel("9811000")

    assert vessel.inspections == []
    assert vessel.flag_history
    assert len(vessel.warnings) == 1
    assert "inspections unavailable" in vessel.warnings[0]


@responses.activate
def test_search_follows_ship_pagination(client: EquasisClient, fixture_html: Loader) -> None:
    mock_login(fixture_html)
    responses.post(SEARCH_URL, body=fixture_html("search_torm_page1"))
    responses.post(SEARCH_URL, body=fixture_html("search_torm_page2"))

    results = client.search("TORM")

    assert len(results.ships) == 105
    assert results.total_ships == 105
    assert len(results.companies) == 8
    assert form(2)["P_ENTREE_ENTETE"] == "TORM"
    follow_up = form(3)
    assert follow_up["P_PAGE_SHIP"] == "2"
    assert follow_up["P_ENTREE"] == "TORM"
    assert follow_up["ongletActifSC"] == "ship"


@responses.activate
def test_search_respects_max_pages(client: EquasisClient, fixture_html: Loader) -> None:
    mock_login(fixture_html)
    responses.post(SEARCH_URL, body=fixture_html("search_torm_page1"))

    results = client.search("TORM", max_pages=1)

    assert len(results.ships) == 100
    assert results.total_ships == 105


@responses.activate
def test_company_only_search_skips_ship_pages(client: EquasisClient, fixture_html: Loader) -> None:
    mock_login(fixture_html)
    responses.post(SEARCH_URL, body=fixture_html("search_torm_page1"))

    results = client.search("TORM", max_pages=None, ships=False)

    assert results.ships == []
    assert len(results.companies) == 8
    assert len(responses.calls) == 3


@responses.activate
def test_search_ships_by_mmsi(client: EquasisClient, fixture_html: Loader) -> None:
    mock_login(fixture_html)
    responses.post(SEARCH_URL, body=fixture_html("search_by_mmsi"))

    results = client.search_ships(mmsi="353136000")

    assert [s.name for s in results.ships] == ["EVER GIVEN"]
    sent = form(2)
    assert sent["P_MMSI"] == "353136000"
    assert sent["buttonAdvancedSearch"] == "advancedOk"


@responses.activate
def test_fleet_pagination_stops_when_pages_repeat(
    client: EquasisClient, fixture_html: Loader
) -> None:
    mock_login(fixture_html)
    responses.post(FLEET_URL, body=fixture_html("fleet_msc_page1"))
    responses.post(FLEET_URL, body=fixture_html("fleet_msc_page2"))
    responses.post(FLEET_URL, body=fixture_html("fleet_msc_page2"))

    fleet = client.get_fleet("0152944")

    assert fleet.company.name == "MSC MEDITERRANEAN SHIPPING CO"
    assert fleet.total_vessels == 443
    assert len(fleet.vessels) == 10
    assert [form(i)["P_PAGE"] for i in (2, 3, 4)] == ["1", "2", "3"]


@responses.activate
def test_fleet_max_pages(client: EquasisClient, fixture_html: Loader) -> None:
    mock_login(fixture_html)
    responses.post(FLEET_URL, body=fixture_html("fleet_msc_page1"))

    fleet = client.get_fleet("0152944", max_pages=1)

    assert len(fleet.vessels) == 5


@responses.activate
def test_unknown_company_raises_not_found(client: EquasisClient, fixture_html: Loader) -> None:
    mock_login(fixture_html)
    responses.post(FLEET_URL, body=fixture_html("fleet_unknown_company"))

    with pytest.raises(NotFoundError, match="9999999"):
        client.get_fleet("9999999")
