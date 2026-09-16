"""Keep the shell completion scripts in sync with the argument parser."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from equasis_cli.cli import build_parser

COMPLETIONS = Path(__file__).parent.parent / "completions"


def visible_options(parser: argparse.ArgumentParser) -> set[str]:
    options = set()
    for action in parser._actions:
        if action.help == argparse.SUPPRESS:
            continue
        options.update(o for o in action.option_strings if o.startswith("--"))
    return options


def parsers() -> dict[str, argparse.ArgumentParser]:
    root = build_parser()
    found = {"": root}
    for action in root._actions:
        if isinstance(action, argparse._SubParsersAction):
            found.update(action.choices)
    return found


@pytest.mark.parametrize("script", ["_equasis", "equasis.bash"])
def test_completion_scripts_cover_every_command_and_option(script: str) -> None:
    content = (COMPLETIONS / script).read_text(encoding="utf-8")
    for name, parser in parsers().items():
        if name:
            assert name in content, f"{script} is missing the '{name}' command"
        for option in visible_options(parser) - {"--help", "--version"}:
            assert option in content, f"{script} is missing {option} ({name or 'global'})"
