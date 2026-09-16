"""Turn raw Equasis HTML into a small, anonymized test fixture.

Raw pages can be captured with ``equasis --save-html DIR ...``. Captured pages
contain the logged-in account's display name, so they must never be committed
as-is. This tool removes everything the parsers do not need and replaces the
account name with a placeholder.

Usage::

    python tests/tools/make_fixture.py RAW.html tests/fixtures/NAME.html [--max-rows N]
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

PLACEHOLDER_NAME = "Test User"
REMOVED_TAGS = ("script", "style", "link", "meta", "noscript", "svg", "iframe", "img", "option")
WHITESPACE = re.compile(r"\s+")


def scrub(html: str, *, max_rows: int | None = None) -> str:
    """Return a minimized copy of ``html`` with account details removed."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all(REMOVED_TAGS):
        # Flag images carry the country code the parser needs; keep those.
        if tag.name == "img" and "/flags/" in str(tag.get("src", "")):
            del tag["class"]
            continue
        tag.decompose()
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()

    # The account display name is rendered in <h3 class="bleu-equasis"> blocks.
    for heading in soup.find_all("h3", class_="bleu-equasis"):
        heading.string = PLACEHOLDER_NAME

    for tag in soup.find_all(True):
        for attribute in ("style", "title", "data-toggle", "data-placement", "aria-hidden"):
            if isinstance(tag, Tag) and attribute in tag.attrs:
                del tag.attrs[attribute]

    if max_rows is not None:
        for tbody in soup.find_all("tbody"):
            desktop_rows = [
                row
                for row in tbody.find_all("tr", recursive=False)
                if "hidden-md" not in (row.get("class") or [])
            ]
            for row in desktop_rows[max_rows:]:
                row.decompose()

    for text in soup.find_all(string=True):
        if isinstance(text, NavigableString) and not isinstance(text, Comment):
            # Keep line breaks: parsers must cope with text that spans lines.
            collapsed = WHITESPACE.sub(lambda m: "\n" if "\n" in m.group() else " ", str(text))
            if collapsed != text:
                text.replace_with(collapsed)

    return str(soup)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--max-rows", type=int, help="keep at most N rows per table body")
    args = parser.parse_args()
    html = args.source.read_text(encoding="utf-8")
    args.destination.write_text(scrub(html, max_rows=args.max_rows), encoding="utf-8")


if __name__ == "__main__":
    main()
