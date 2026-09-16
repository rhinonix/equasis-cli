"""Tests for the page cache and its use by the client."""

from __future__ import annotations

import os
import stat
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs

import pytest
import responses

from equasis_cli.cache import PageCache, default_cache_dir
from equasis_cli.client import EquasisClient
from equasis_cli.transport import BASE_URL, RetryPolicy, Transport

Loader = Callable[[str], str]
LOGIN_URL = BASE_URL + "authen/HomePage?fs=HomePage"
FLEET_URL = BASE_URL + "restricted/FleetInfo?fs=CompanyInfo"


class Clock:
    def __init__(self) -> None:
        self.now = 1_900_000_000.0

    def __call__(self) -> float:
        return self.now


def test_put_get_and_expiry(tmp_path: Path) -> None:
    clock = Clock()
    cache = PageCache(tmp_path, ttl=timedelta(hours=1), clock=clock)
    key = PageCache.key("GET", "restricted/ShipInfo", {"P_IMO": "9811000"})

    assert cache.get(key) is None
    cache.put(key, "<html>ship</html>")
    clock.now = os.stat(cache.pages_dir / f"{key}.html").st_mtime + 10
    page = cache.get(key)
    assert page is not None
    assert page.html == "<html>ship</html>"

    clock.now = os.stat(cache.pages_dir / f"{key}.html").st_mtime + 3601
    assert cache.get(key) is None


def test_keys_depend_on_every_request_detail() -> None:
    base = PageCache.key("POST", "restricted/Search", data={"P_ENTREE": "TORM", "P_PAGE": "1"})
    assert base == PageCache.key(
        "POST", "restricted/Search", data={"P_PAGE": "1", "P_ENTREE": "TORM"}
    )
    assert base != PageCache.key(
        "POST", "restricted/Search", data={"P_ENTREE": "TORM", "P_PAGE": "2"}
    )
    assert base != PageCache.key(
        "GET", "restricted/Search", data={"P_ENTREE": "TORM", "P_PAGE": "1"}
    )


def test_stats_and_clear(tmp_path: Path) -> None:
    cache = PageCache(tmp_path)
    assert cache.stats().entries == 0
    assert cache.clear() == 0
    cache.put("a", "one")
    cache.put("b", "two")
    stats = cache.stats()
    assert stats.entries == 2
    assert stats.size_bytes == 6
    assert cache.clear() == 2


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")
def test_cache_directory_is_private(tmp_path: Path) -> None:
    cache = PageCache(tmp_path / "cache")
    cache.put("a", "page")
    assert stat.S_IMODE(cache.directory.stat().st_mode) == 0o700


def test_default_cache_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EQUASIS_CACHE_DIR", str(tmp_path / "custom"))
    assert default_cache_dir() == tmp_path / "custom"
    monkeypatch.delenv("EQUASIS_CACHE_DIR")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert default_cache_dir() == tmp_path / "equasis-cli"


def make_client(cache: PageCache, *, refresh: bool = False) -> EquasisClient:
    transport = Transport(min_interval=0, retry=RetryPolicy(max_retries=0), sleep=lambda _: None)
    return EquasisClient(
        "user@example.com", "secret", transport=transport, cache=cache, refresh=refresh
    )


def ship_url(page: str) -> str:
    return f"{BASE_URL}restricted/{page}?fs=ShipInfo&P_IMO=9811000"


def mock_vessel(fixture_html: Loader) -> None:
    responses.get(LOGIN_URL, body=fixture_html("login_page"))
    responses.post(LOGIN_URL, body=fixture_html("home_logged_in"))
    responses.get(ship_url("ShipInfo"), body=fixture_html("ship_info_9811000"))
    responses.get(ship_url("ShipInspection"), body=fixture_html("inspections_9811000"))
    responses.get(ship_url("ShipHistory"), body=fixture_html("history_9811000"))


@responses.activate
def test_cached_vessel_needs_no_requests(tmp_path: Path, fixture_html: Loader) -> None:
    cache = PageCache(tmp_path)
    mock_vessel(fixture_html)
    first = make_client(cache).get_vessel("9811000")
    requests_made = len(responses.calls)

    second_client = make_client(cache)
    second = second_client.get_vessel("9811000")

    assert second.name == first.name == "EVER GIVEN"
    assert len(responses.calls) == requests_made
    assert not second_client.logged_in
    assert second.retrieved_at is not None
    assert first.retrieved_at is not None
    # The cached copy is dated by its file modification time, which some file systems
    # record slightly after the in-memory timestamp.
    assert abs((second.retrieved_at - first.retrieved_at).total_seconds()) < 2


@responses.activate
def test_refresh_bypasses_the_cache(tmp_path: Path, fixture_html: Loader) -> None:
    cache = PageCache(tmp_path)
    mock_vessel(fixture_html)
    make_client(cache).get_vessel("9811000")
    requests_made = len(responses.calls)

    make_client(cache, refresh=True).get_vessel("9811000")

    assert len(responses.calls) > requests_made


@responses.activate
def test_login_and_error_pages_are_not_cached(tmp_path: Path, fixture_html: Loader) -> None:
    cache = PageCache(tmp_path)
    responses.get(LOGIN_URL, body=fixture_html("login_page"))
    responses.post(LOGIN_URL, body=fixture_html("home_logged_in"))
    responses.post(FLEET_URL, body=fixture_html("fleet_unknown_company"))

    with pytest.raises(Exception, match="no company"):
        make_client(cache).get_fleet("9999999")

    assert cache.stats().entries == 0


@responses.activate
def test_uncached_fleet_page_reloads_page_one_first(tmp_path: Path, fixture_html: Loader) -> None:
    """Equasis serves later fleet pages only after page 1 in the same session."""
    cache = PageCache(tmp_path)
    page_one = PageCache.key(
        "POST",
        "restricted/FleetInfo?fs=CompanyInfo",
        data={"P_PAGE": "1", "P_COMP": "0152944", "ongletActifSC": "comp"},
    )
    cache.put(page_one, fixture_html("fleet_msc_page1"))
    responses.get(LOGIN_URL, body=fixture_html("login_page"))
    responses.post(LOGIN_URL, body=fixture_html("home_logged_in"))
    responses.post(FLEET_URL, body=fixture_html("fleet_msc_page1"))
    responses.post(FLEET_URL, body=fixture_html("fleet_msc_page2"))

    fleet = make_client(cache).get_fleet("0152944", max_pages=2)

    fleet_posts = [c for c in responses.calls if c.request.url == FLEET_URL]
    pages = [parse_qs(str(c.request.body))["P_PAGE"][0] for c in fleet_posts]
    assert pages == ["1", "2"]
    assert len(fleet.vessels) == 10
