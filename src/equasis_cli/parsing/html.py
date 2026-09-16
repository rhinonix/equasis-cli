"""Low-level HTML helpers shared by the page parsers."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date

from bs4 import BeautifulSoup, Tag

from ..exceptions import LayoutChangedError

_WHITESPACE = re.compile(r"\s+")
_DMY = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_MY = re.compile(r"\b(\d{1,2})/(\d{4})\b")
_MOBILE_ONLY = {"hidden-lg", "hidden-md"}


def make_soup(html: str) -> BeautifulSoup:
    """Parse HTML with the standard library parser (no optional dependencies)."""
    return BeautifulSoup(html, "html.parser")


def clean(text: str | None) -> str | None:
    """Collapse whitespace; return ``None`` for empty strings."""
    if text is None:
        return None
    collapsed = _WHITESPACE.sub(" ", text).strip()
    return collapsed or None


def text_of(tag: Tag | None, separator: str = " ") -> str | None:
    """Return the normalized text content of ``tag``."""
    if tag is None:
        return None
    return clean(tag.get_text(separator))


def parse_int(text: str | None) -> int | None:
    """Parse an integer such as ``"219079"`` or ``"1,234"``; ``None`` if absent."""
    if not text:
        return None
    digits = re.sub(r"[,\s]", "", text)
    return int(digits) if digits.isdigit() else None


def parse_float(text: str | None) -> float | None:
    """Parse the first decimal number in ``text`` (for example ``"0.0%"``)."""
    if not text:
        return None
    match = re.search(r"\d+(?:\.\d+)?", text)
    return float(match.group()) if match else None


def parse_date(text: str | None) -> date | None:
    """Parse the date formats Equasis uses.

    Supports ``DD/MM/YYYY`` (optionally prefixed with "since"), ``YYYY-MM-DD``, and
    month precision ``MM/YYYY`` ("during 09/2024"), which maps to the first day of
    that month.
    """
    if not text:
        return None
    try:
        if match := _DMY.search(text):
            day, month, year = (int(g) for g in match.groups())
            return date(year, month, day)
        if match := _ISO.search(text):
            year, month, day = (int(g) for g in match.groups())
            return date(year, month, day)
        if match := _MY.search(text):
            month, year = (int(g) for g in match.groups())
            return date(year, month, 1)
    except ValueError:
        return None
    return None


def is_mobile_only(tag: Tag) -> bool:
    """True for elements Equasis renders only on small screens (duplicates)."""
    return _MOBILE_ONLY.issubset(set(class_list(tag)))


def class_list(tag: Tag) -> list[str]:
    """The CSS classes of ``tag`` as a list."""
    value = tag.get("class")
    if value is None:
        return []
    return [value] if isinstance(value, str) else list(value)


def paragraph_texts(tag: Tag) -> list[str]:
    """Non-empty, normalized text of every ``<p>`` inside ``tag``."""
    return [text for p in tag.find_all("p") if (text := clean(p.get_text(" ")))]


def normalize_header(text: str | None) -> str:
    return (clean(text) or "").lower()


@dataclass
class TableRow:
    """A table row with cells keyed by normalized header text.

    ``continuation`` is true when the row inherited cells from a ``rowspan`` in a
    previous row (for example an inspection reported to a second PSC regime).
    """

    cells: dict[str, Tag]
    own_cells: dict[str, Tag]
    continuation: bool

    def text(self, header: str) -> str | None:
        return text_of(self.cells.get(header))

    def own_text(self, header: str) -> str | None:
        return text_of(self.own_cells.get(header))


def table_headers(table: Tag) -> list[str]:
    head = table.find("thead")
    header_row = head if isinstance(head, Tag) else table
    return [normalize_header(th.get_text(" ")) for th in header_row.find_all("th")]


def iter_rows(table: Tag, *, required: Iterable[str] = ()) -> Iterator[TableRow]:
    """Yield desktop rows of ``table`` keyed by header, expanding ``rowspan`` cells.

    Equasis emits invalid markup where a row spanned by ``rowspan`` is nested
    inside the previous ``<tr>``, so rows are collected recursively and only their
    direct ``<td>`` children are used.

    Raises:
        LayoutChangedError: if any ``required`` header is missing.
    """
    headers = table_headers(table)
    missing = [h for h in required if h not in headers]
    if missing:
        raise LayoutChangedError(
            f"table is missing expected columns {missing}; found {headers or 'no headers'}"
        )

    body = table.find("tbody")
    container = body if isinstance(body, Tag) else table
    pending: dict[int, tuple[Tag, int]] = {}

    for tr in container.find_all("tr"):
        if not isinstance(tr, Tag) or is_mobile_only(tr):
            continue
        own = [c for c in tr.find_all(["td", "th"], recursive=False) if isinstance(c, Tag)]
        if all(cell.name == "th" for cell in own) and not pending:
            continue  # header row, or a row with no cells

        cells: dict[str, Tag] = {}
        own_cells: dict[str, Tag] = {}
        continuation = False
        own_iter = iter(own)
        for index, header in enumerate(headers):
            if index in pending:
                cell, remaining = pending[index]
                cells[header] = cell
                continuation = True
                if remaining <= 1:
                    del pending[index]
                else:
                    pending[index] = (cell, remaining - 1)
                continue
            td = next(own_iter, None)
            if td is None:
                break
            cells[header] = td
            own_cells[header] = td
            span = parse_int(str(td.get("rowspan", "1"))) or 1
            if span > 1:
                pending[index] = (td, span - 1)

        if own_cells:
            yield TableRow(cells=cells, own_cells=own_cells, continuation=continuation)


def find_panel(soup: BeautifulSoup, title_prefix: str) -> Tag | None:
    """Find a collapsible panel by the text of the link that toggles it.

    Panel ids (``collapse3``...) are positional and differ between pages, so the
    visible title is the stable key.
    """
    wanted = title_prefix.lower()
    for link in soup.find_all("a", href=re.compile(r"^#collapse")):
        title = normalize_header(link.get_text(" "))
        if title.startswith(wanted):
            panel = soup.find(id=str(link["href"])[1:])
            if isinstance(panel, Tag):
                return panel
    return None


def desktop_table(panel: Tag | None) -> Tag | None:
    """Return the first table inside ``panel``, if any."""
    if panel is None:
        return None
    table = panel.find("table")
    return table if isinstance(table, Tag) else None
