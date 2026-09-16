"""Classify Equasis responses before parsing them.

Equasis answers almost everything with HTTP 200, so the page body is the only
reliable signal for an expired session, a missing record, or an error page.
"""

from __future__ import annotations

import enum

from bs4 import BeautifulSoup, Tag

from ..exceptions import EquasisError, NotFoundError, SessionExpiredError
from .html import clean, make_soup


class PageKind(enum.Enum):
    """What kind of page Equasis returned."""

    LOGIN = "login"
    """The login form: the session is missing, expired, or credentials were rejected."""
    NOT_FOUND = "not_found"
    """The general error page reporting that nothing matched."""
    ERROR = "error"
    """Any other general error page."""
    CONTENT = "content"
    """A regular page."""


def page_title(soup: BeautifulSoup) -> str:
    title = soup.find("title")
    return (clean(title.get_text()) if isinstance(title, Tag) else None) or ""


def classify(html: str, soup: BeautifulSoup | None = None) -> PageKind:
    """Classify an Equasis response body."""
    soup = soup if soup is not None else make_soup(html)
    if soup.find("input", attrs={"name": "j_password"}) is not None:
        return PageKind.LOGIN
    if "CtrlGeneralError" in page_title(soup):
        text = (clean(soup.get_text(" ")) or "").lower()
        if "has been found" in text:
            return PageKind.NOT_FOUND
        return PageKind.ERROR
    return PageKind.CONTENT


def is_logged_in(html: str) -> bool:
    """True if the page was rendered for an authenticated user."""
    soup = make_soup(html)
    return classify(html, soup) is not PageKind.LOGIN and "Logout" in html


def require_content(soup: BeautifulSoup, html: str, *, page: str) -> None:
    """Raise a specific error unless ``html`` is a regular content page."""
    kind = classify(html, soup)
    if kind is PageKind.LOGIN:
        raise SessionExpiredError(f"Equasis returned the login page instead of {page}")
    if kind is PageKind.NOT_FOUND:
        raise NotFoundError(f"Equasis found no record for the {page} request")
    if kind is PageKind.ERROR:
        raise EquasisError(f"Equasis returned an error page for the {page} request")
