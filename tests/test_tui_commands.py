"""Tests for interactive shell command parsing and execution."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from equasis_cli.credentials import CredentialStore
from equasis_cli.models import CompanySummary
from equasis_cli.tui.commands import CommandError, CommandRunner, help_text, parse_command
from tests.fakes import FakeClient, fixture_fleet

TORM = CompanySummary(company_id="0310062", name="TORM A/S", address="Hellerup")
TORM_NORWAY = CompanySummary(company_id="5313763", name="TORM NORWAY AS")


# ------------------------------------------------------------------------------ parsing


def test_parse_quoted_values_and_flags() -> None:
    command = parse_command('batch /companies "TORM A/S,0152944" /first /output out.csv')
    assert command is not None
    assert command.name == "batch"
    assert command.text("companies") == "TORM A/S,0152944"
    assert command.flag("first")
    assert command.text("output") == "out.csv"


def test_parse_typographic_quotes_and_hyphenated_parameters() -> None:
    command = parse_command("batch /company-file “my companies.txt”")
    assert command is not None
    assert command.text("company-file") == "my companies.txt"


def test_parameter_values_may_start_with_a_slash() -> None:
    command = parse_command("vessel /imo 9811000 /output /data/vessel.json")
    assert command is not None
    assert command.text("output") == "/data/vessel.json"


def test_backslashes_in_windows_paths_are_kept() -> None:
    command = parse_command(r'batch /file C:\Users\me\imos.txt /output "C:\My Data\out #1.csv"')
    assert command is not None
    assert command.text("file") == r"C:\Users\me\imos.txt"
    assert command.text("output") == r"C:\My Data\out #1.csv"


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ("launch /imo 1", "unknown command"),
        ("vessel /name X", "has no parameter /name"),
        ("vessel /imo", "needs a value"),
        ('search /name "unterminated', "could not read"),
    ],
)
def test_parse_errors(line: str, message: str) -> None:
    with pytest.raises(CommandError, match=message):
        parse_command(line)


def test_aliases_and_blank_lines() -> None:
    assert parse_command("   ") is None
    command = parse_command("quit")
    assert command is not None
    assert command.name == "exit"


def test_help_text() -> None:
    assert "batch" in help_text()
    assert "/company-file" in help_text("batch")
    assert "No help for" in help_text("nothing")


# ---------------------------------------------------------------------------- execution


class Recorder:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.statuses: list[str] = []

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CredentialStore:
    monkeypatch.delenv("EQUASIS_USERNAME", raising=False)
    monkeypatch.delenv("EQUASIS_PASSWORD", raising=False)
    credential_store = CredentialStore(tmp_path / "config")
    credential_store.save("user@example.com", "secret")
    return credential_store


@pytest.fixture
def fake() -> FakeClient:
    return FakeClient(companies=[TORM, TORM_NORWAY], fleets={"0310062": fixture_fleet()})


@pytest.fixture
def recorder() -> Recorder:
    return Recorder()


@pytest.fixture
def runner(store: CredentialStore, fake: FakeClient, recorder: Recorder) -> CommandRunner:
    return CommandRunner(
        recorder.lines.append,
        recorder.statuses.append,
        store=store,
        client_factory=lambda username, password: fake,  # type: ignore[arg-type,return-value]
    )


def test_exit_returns_false(runner: CommandRunner) -> None:
    assert runner.run("exit") is False
    assert runner.run("help") is True


def test_vessel_table(runner: CommandRunner, recorder: Recorder) -> None:
    runner.run("vessel /imo 9074729")
    assert "KAVITA (IMO 9074729)" in recorder.text
    assert "Retrieving IMO 9074729..." in recorder.statuses
    assert runner.connected


@pytest.mark.parametrize(("extension", "reader"), [("json", "json"), ("csv", "csv")])
def test_vessel_output_file_uses_the_extension_format(
    runner: CommandRunner, recorder: Recorder, tmp_path: Path, extension: str, reader: str
) -> None:
    """Regression test for issue #17: files were written as table text."""
    target = tmp_path / f"vessel_data.{extension}"
    runner.run(f"vessel /imo 9074729 /output {target}")

    content = target.read_text(encoding="utf-8")
    if reader == "json":
        assert json.loads(content)["vessel"]["name"] == "KAVITA"
    else:
        assert next(csv.DictReader(io.StringIO(content)))["name"] == "KAVITA"
    assert f"Saved {extension} output to {target}" in recorder.text


def test_output_with_a_format_name_selects_the_format(
    runner: CommandRunner, recorder: Recorder
) -> None:
    runner.run("vessel /imo 9074729 /output json")
    assert json.loads(recorder.lines[-1])["vessel"]["imo"] == "9074729"


def test_default_format_command(runner: CommandRunner, recorder: Recorder) -> None:
    runner.run("format csv")
    runner.run("vessel 9074729")
    assert recorder.lines[-1].startswith("imo,name,flag")
    runner.run("format xml")
    assert "unknown format 'xml'" in recorder.lines[-1]


def test_batch_imos(runner: CommandRunner, recorder: Recorder) -> None:
    """Regression test for issue #16: batch was not implemented."""
    runner.run('batch /imos "9074729, 1234567"')

    assert "Processing 2 vessels..." in recorder.text
    assert "9074729: ok" in recorder.text
    assert "1234567: not found" in recorder.text
    assert "1 of 2 vessels retrieved." in recorder.text
    assert "[2/2] 1234567" in recorder.statuses


def test_batch_file_to_json(runner: CommandRunner, recorder: Recorder, tmp_path: Path) -> None:
    imo_file = tmp_path / "fleet.txt"
    imo_file.write_text("# list\n9074729 # KAVITA\n", encoding="utf-8")
    target = tmp_path / "results.json"

    runner.run(f"batch /file {imo_file} /output {target}")

    document = json.loads(target.read_text(encoding="utf-8"))
    assert document["summary"]["succeeded"] == 1


def test_batch_companies(runner: CommandRunner, recorder: Recorder) -> None:
    runner.run('batch /companies "TORM A/S,TORM" /format csv')
    assert "TORM A/S: ok" in recorder.text
    assert "TORM: ambiguous" in recorder.text


def test_batch_argument_errors(runner: CommandRunner, recorder: Recorder, tmp_path: Path) -> None:
    runner.run("batch")
    assert "use exactly one of" in recorder.lines[-1]
    runner.run(f"batch /file {tmp_path / 'missing.txt'}")
    assert "cannot read" in recorder.lines[-1]


def test_fleet_by_name(runner: CommandRunner, recorder: Recorder) -> None:
    """Regression test for issue #18: fleet was not implemented."""
    runner.run('fleet /company "TORM A/S"')
    assert "TORM A/S (company no. 0310062)" in recorder.text


def test_ambiguous_fleet_lists_candidates_then_accepts_id(
    runner: CommandRunner, recorder: Recorder
) -> None:
    runner.run("fleet /company TORM")
    assert "'TORM' matches 2 companies" in recorder.text
    assert "fleet /id NUMBER" in recorder.text

    runner.run("fleet /id 0310062 /format json")
    assert json.loads(recorder.lines[-1])["fleet"]["company"]["name"] == "TORM A/S"


def test_ambiguous_fleet_with_first(runner: CommandRunner, recorder: Recorder) -> None:
    runner.run("fleet /company TORM /first")
    assert "Using TORM A/S (0310062)" in recorder.text


def test_search_commands(runner: CommandRunner, recorder: Recorder) -> None:
    runner.run('search /name "kavita"')
    assert "Ships matching 'kavita'" in recorder.text
    runner.run("search /imo 9074729 /name kavita")
    assert "not both" in recorder.lines[-1]
    runner.run("search /name x /type boats")
    assert "/type must be" in recorder.lines[-1]


def test_missing_credentials(
    runner: CommandRunner, recorder: Recorder, store: CredentialStore
) -> None:
    store.clear()
    runner.run("vessel /imo 9074729")
    assert "no Equasis credentials found" in recorder.lines[-1]


def test_rejected_login_resets_the_client(
    runner: CommandRunner, recorder: Recorder, fake: FakeClient
) -> None:
    fake.reject_login = True
    runner.run("vessel /imo 9074729")
    assert recorder.lines[-1].startswith("Login failed")
    assert runner.state.client is None


def test_invalid_imo_and_status(runner: CommandRunner, recorder: Recorder) -> None:
    runner.run("vessel /imo EVERGIVEN")
    assert "not a valid IMO number" in recorder.lines[-1]
    runner.run("status")
    assert "Account:        user@example.com" in recorder.lines[-1]
