"""Smoke tests for package metadata and the console entry point."""

from __future__ import annotations

import re
import subprocess
import sys
from importlib.metadata import version

import equasis_cli


def test_version_is_single_sourced() -> None:
    assert equasis_cli.__version__ == version("equasis-cli")
    assert re.fullmatch(r"\d+\.\d+\.\d+(\.dev\d+|rc\d+)?", equasis_cli.__version__)


def test_module_entry_point_reports_version() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "equasis_cli", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert equasis_cli.__version__ in result.stdout
