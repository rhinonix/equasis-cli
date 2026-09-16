"""Tests for page classification and fixture hygiene."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from equasis_cli.exceptions import NotFoundError, SessionExpiredError
from equasis_cli.parsing import PageKind, classify, is_logged_in, parse_ship_info
from tests.conftest import FIXTURES


@pytest.mark.parametrize(
    ("fixture", "kind"),
    [
        ("login_page", PageKind.LOGIN),
        ("ship_not_found", PageKind.NOT_FOUND),
        ("home_logged_in", PageKind.CONTENT),
        ("ship_info_9811000", PageKind.CONTENT),
        ("search_no_results", PageKind.CONTENT),
    ],
)
def test_classify(fixture_html: Callable[[str], str], fixture: str, kind: PageKind) -> None:
    assert classify(fixture_html(fixture)) is kind


def test_is_logged_in(fixture_html: Callable[[str], str]) -> None:
    assert is_logged_in(fixture_html("home_logged_in"))
    assert not is_logged_in(fixture_html("login_page"))


def test_parsers_raise_specific_errors(fixture_html: Callable[[str], str]) -> None:
    with pytest.raises(SessionExpiredError):
        parse_ship_info(fixture_html("login_page"))
    with pytest.raises(NotFoundError):
        parse_ship_info(fixture_html("ship_not_found"))


def test_fixtures_are_anonymized() -> None:
    from equasis_cli.parsing.html import make_soup

    for path in sorted(FIXTURES.glob("*.html")):
        soup = make_soup(path.read_text(encoding="utf-8"))
        names = {h.get_text(strip=True) for h in soup.find_all("h3", class_="bleu-equasis")}
        assert names <= {"Test User"}, f"{path.name} contains an account name"
        assert not soup.find_all("script"), f"{path.name} was not minimized"
