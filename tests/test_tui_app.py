"""Tests for the prompt_toolkit shell: menus, input handling, and command dispatch."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from prompt_toolkit.application import create_app_session
from prompt_toolkit.document import Document
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.input.base import PipeInput
from prompt_toolkit.output import DummyOutput

from equasis_cli.cache import PageCache
from equasis_cli.credentials import CredentialStore
from equasis_cli.tui.app import MAX_OUTPUT_LINES, PROMPT, InteractiveShell, OutputLexer
from equasis_cli.tui.commands import CommandRunner
from tests.fakes import FakeClient


@pytest.fixture
def pipe() -> Iterator[PipeInput]:
    with (
        create_pipe_input() as pipe_input,
        create_app_session(input=pipe_input, output=DummyOutput()),
    ):
        yield pipe_input


@pytest.fixture
def shell(pipe: PipeInput, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> InteractiveShell:
    monkeypatch.delenv("EQUASIS_USERNAME", raising=False)
    monkeypatch.delenv("EQUASIS_PASSWORD", raising=False)
    store = CredentialStore(tmp_path)
    store.save("user@example.com", "secret")
    fake = FakeClient()
    runner = CommandRunner(
        print,
        print,
        store=store,
        client_factory=lambda u, p: fake,  # type: ignore[arg-type,return-value]
        cache=PageCache(tmp_path / "cache"),
    )
    return InteractiveShell(runner=runner, input=pipe, output=DummyOutput())


def type_text(shell: InteractiveShell, text: str) -> None:
    shell.input_buffer.document = Document(text, len(text))


def test_banner_is_shown(shell: InteractiveShell) -> None:
    assert "Press ? for quick help." in shell.output_buffer.text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "/",
            [
                "vessel",
                "search",
                "fleet",
                "batch",
                "format",
                "cache",
                "status",
                "clear",
                "help",
                "exit",
            ],
        ),
        ("/ba", ["batch"]),
        ("batch /co", ["/companies", "/company-file"]),
        ("vessel /imo 1 /", ["/refresh", "/format", "/output"]),
        ("vessel ", []),
        ("ves", []),
    ],
)
def test_menu_items(shell: InteractiveShell, text: str, expected: list[str]) -> None:
    type_text(shell, text)
    assert [name for name, _ in shell.menu_items()] == expected


def test_accepting_menu_items(shell: InteractiveShell) -> None:
    type_text(shell, "/fl")
    assert shell.accept_menu_item()
    assert shell.input_buffer.text == "fleet "
    type_text(shell, "fleet /c")
    shell.accept_menu_item()
    assert shell.input_buffer.text == "fleet /company "


def test_tab_completes_command_names(shell: InteractiveShell) -> None:
    type_text(shell, "ba")
    shell.complete_command()
    assert shell.input_buffer.text == "batch "
    type_text(shell, "s")
    shell.complete_command()
    assert shell.input_buffer.text == "/s"


def test_clear_and_echo(shell: InteractiveShell) -> None:
    type_text(shell, "clear")
    shell.submit()
    assert shell.output_buffer.text == ""
    shell.write("Error: example")
    assert shell.output_buffer.text == "Error: example\n"


def test_output_is_capped(shell: InteractiveShell) -> None:
    shell.clear()
    shell.write("\n".join(str(n) for n in range(MAX_OUTPUT_LINES + 10)))
    assert len(shell.output_buffer.text.split("\n")) <= MAX_OUTPUT_LINES


def test_lexer_highlights_messages() -> None:
    lexer = OutputLexer(banner_lines=0, art_lines=0)
    document = Document(
        f"{PROMPT}vessel\nError: bad\nWarning: careful\nSaved json output to x\nplain"
    )
    styles = lexer.lex_document(document)
    assert [styles(n)[0][0] for n in range(5)] == [
        "class:echo",
        "class:error",
        "class:warning",
        "class:success",
        "",
    ]


def test_commands_run_through_the_application(shell: InteractiveShell, pipe: PipeInput) -> None:
    pipe.send_text("vessel /imo 9074729\r")

    async def exit_when_done() -> None:
        for _ in range(200):
            await asyncio.sleep(0.02)
            if "KAVITA (IMO 9074729)" in shell.output_buffer.text and not shell.busy:
                break
        shell.app.exit()

    shell.app.pre_run_callables.append(lambda: shell.app.create_background_task(exit_when_done()))
    shell.start()

    assert f"{PROMPT}vessel /imo 9074729" in shell.output_buffer.text
    assert "KAVITA (IMO 9074729)" in shell.output_buffer.text


def test_exit_command_stops_the_application(shell: InteractiveShell, pipe: PipeInput) -> None:
    pipe.send_text("exit\r")
    shell.start()
    assert f"{PROMPT}exit" in shell.output_buffer.text
