"""Shared pytest configuration."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip tests marked ``live`` unless explicitly enabled."""
    if os.environ.get("EQUASIS_LIVE_TESTS") == "1":
        return
    skip_live = pytest.mark.skip(reason="set EQUASIS_LIVE_TESTS=1 to run live Equasis tests")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture
def fixture_html() -> Callable[[str], str]:
    """Return a loader for anonymized Equasis pages in ``tests/fixtures``."""

    def load(name: str) -> str:
        return (FIXTURES / f"{name}.html").read_text(encoding="utf-8")

    return load
