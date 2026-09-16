"""Checks against the real Equasis website.

These tests are skipped unless ``EQUASIS_LIVE_TESTS=1`` is set and credentials are
available. They make a handful of rate-limited requests and exist to detect
changes to the Equasis website early.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from equasis_cli.client import EquasisClient
from equasis_cli.credentials import CredentialStore
from equasis_cli.exceptions import NotFoundError

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def client() -> Iterator[EquasisClient]:
    credentials = CredentialStore().resolve()
    if credentials is None:
        pytest.skip("no Equasis credentials configured")
    with EquasisClient(credentials.username, credentials.password) as live_client:
        yield live_client


def test_vessel_profile(client: EquasisClient) -> None:
    vessel = client.get_vessel("9811000")
    assert vessel.name == "EVER GIVEN"
    assert vessel.flag_code
    assert vessel.gross_tonnage
    assert vessel.management
    assert vessel.inspections
    assert vessel.name_history
    assert vessel.warnings == []


def test_unknown_vessel(client: EquasisClient) -> None:
    with pytest.raises(NotFoundError):
        client.get_vessel("1234567")


def test_search(client: EquasisClient) -> None:
    results = client.search("TORM", max_pages=1)
    assert results.ships
    assert any(c.company_id == "0310062" for c in results.companies)


def test_fleet(client: EquasisClient) -> None:
    fleet = client.get_fleet("0310062")
    assert fleet.company.name == "TORM A/S"
    assert len(fleet.vessels) > 10
