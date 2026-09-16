"""End-to-end tests of the command-line interface with a fake Equasis client."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from equasis_cli.cli import ExitCode, main
from equasis_cli.credentials import CredentialStore
from equasis_cli.models import CompanySummary
from equasis_cli.transport import Transport
from tests.fakes import FakeClient, fixture_fleet

TORM = CompanySummary(company_id="0310062", name="TORM A/S", address="Hellerup")
TORM_NORWAY = CompanySummary(company_id="5313763", name="TORM NORWAY AS")


@dataclass
class Result:
    code: int
    stdout: str
    stderr: str


class TTYStringIO(io.StringIO):
    def isatty(self) -> bool:
        return True


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CredentialStore:
    monkeypatch.delenv("EQUASIS_USERNAME", raising=False)
    monkeypatch.delenv("EQUASIS_PASSWORD", raising=False)
    monkeypatch.setenv("NO_COLOR", "1")
    credential_store = CredentialStore(tmp_path / "config")
    credential_store.save("user@example.com", "secret")
    return credential_store


@pytest.fixture
def fake() -> FakeClient:
    return FakeClient(companies=[TORM, TORM_NORWAY], fleets={"0310062": fixture_fleet()})


@pytest.fixture
def run(store: CredentialStore, fake: FakeClient):  # type: ignore[no-untyped-def]
    def invoke(*argv: str, stdin: str = "", tty: bool = False) -> Result:
        stdout = io.StringIO()
        stderr = TTYStringIO() if tty else io.StringIO()
        stdin_stream = TTYStringIO(stdin) if tty else io.StringIO(stdin)
        seen: list[Transport] = []

        def factory(username: str, password: str, transport: Transport) -> FakeClient:
            assert (username, password) == ("user@example.com", "secret")
            seen.append(transport)
            return fake

        code = main(
            list(argv),
            stdout=stdout,
            stderr=stderr,
            stdin=stdin_stream,
            store=store,
            client_factory=factory,  # type: ignore[arg-type]
        )
        return Result(int(code), stdout.getvalue(), stderr.getvalue())

    return invoke


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--version"])
    assert raised.value.code == 0
    assert capsys.readouterr().out.startswith("equasis ")


def test_no_arguments_without_terminal_prints_help() -> None:
    stderr = io.StringIO()
    code = main([], stdout=io.StringIO(), stdin=io.StringIO(), stderr=stderr)
    assert code == ExitCode.USAGE
    assert "usage: equasis" in stderr.getvalue()


def test_usage_errors_exit_2(run) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(SystemExit) as raised:
        run("vessel", "--bogus")
    assert raised.value.code == ExitCode.USAGE


def test_vessel_table_to_stdout_and_messages_to_stderr(run) -> None:  # type: ignore[no-untyped-def]
    result = run("vessel", "9074729")
    assert result.code == ExitCode.OK
    assert result.stdout.startswith("KAVITA (IMO 9074729)")
    assert "Retrieving IMO 9074729" in result.stderr


@pytest.mark.parametrize(
    "argv",
    [
        ("vessel", "9074729", "--format", "json"),
        ("--format", "json", "vessel", "9074729"),
        ("--output", "json", "vessel", "--imo", "9074729"),
        ("vessel", "-f", "json", "--imo", "9074729", "--quiet"),
    ],
)
def test_format_options_work_before_or_after_the_command(run, argv) -> None:  # type: ignore[no-untyped-def]
    result = run(*argv)
    assert result.code == ExitCode.OK
    assert json.loads(result.stdout)["vessel"]["imo"] == "9074729"


def test_output_file_format_is_inferred_from_extension(run, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    target = tmp_path / "out" / "vessel.csv"
    result = run("vessel", "9074729", "-o", str(target))

    assert result.code == ExitCode.OK
    assert result.stdout == ""
    rows = list(csv.DictReader(io.StringIO(target.read_text(encoding="utf-8"))))
    assert rows[0]["name"] == "KAVITA"
    assert f"Saved to {target}" in result.stderr


def test_vessel_not_found_and_invalid_input(run) -> None:  # type: ignore[no-untyped-def]
    missing = run("vessel", "1234567")
    assert missing.code == ExitCode.NOT_FOUND
    assert "no vessel with IMO 1234567" in missing.stderr

    invalid = run("vessel", "EVERGIVEN")
    assert invalid.code == ExitCode.USAGE
    assert "not a valid IMO number" in invalid.stderr


def test_missing_credentials(run, store: CredentialStore) -> None:  # type: ignore[no-untyped-def]
    store.clear()
    result = run("vessel", "9074729")
    assert result.code == ExitCode.AUTHENTICATION
    assert "equasis configure --setup" in result.stderr


def test_rejected_login(run, fake: FakeClient) -> None:  # type: ignore[no-untyped-def]
    fake.reject_login = True
    result = run("vessel", "9074729")
    assert result.code == ExitCode.AUTHENTICATION


def test_batch_from_file_reports_partial_failure(run, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    imo_file = tmp_path / "imos.txt"
    imo_file.write_text("# fleet\n9074729  # KAVITA\n\n1234567\nnot-an-imo\n", encoding="utf-8")

    result = run("vessel", "--imo-file", str(imo_file), "--format", "json")

    assert result.code == ExitCode.PARTIAL_FAILURE
    document = json.loads(result.stdout)
    assert [r["status"] for r in document["results"]] == ["ok", "not_found", "error"]
    assert "[2/3] 1234567" in result.stderr
    assert "1 of 3 vessels retrieved" in result.stderr


def test_batch_jsonl_streams_to_file(run, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    target = tmp_path / "results.jsonl"
    result = run("vessel", "9074729", "1234567", "-o", str(target))

    assert result.code == ExitCode.PARTIAL_FAILURE
    records = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
    assert [r["query"] for r in records] == ["9074729", "1234567"]
    assert records[0]["vessel"]["name"] == "KAVITA"


def test_batch_from_stdin_with_fail_fast(run) -> None:  # type: ignore[no-untyped-def]
    result = run(
        "vessel", "--imo-file", "-", "--fail-fast", "-f", "csv", stdin="1234567\n9074729\n"
    )
    assert result.code == ExitCode.PARTIAL_FAILURE
    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert [r["query"] for r in rows] == ["1234567"]


def test_unreadable_list_file(run, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    result = run("vessel", "--imo-file", str(tmp_path / "missing.txt"))
    assert result.code == ExitCode.USAGE
    assert "cannot read" in result.stderr


def test_search_by_name_and_identifier(run) -> None:  # type: ignore[no-untyped-def]
    by_name = run("search", "kavita", "-f", "json")
    assert by_name.code == ExitCode.OK
    assert json.loads(by_name.stdout)["search"]["ships"][0]["imo"] == "9074729"

    by_imo = run("search", "--imo", "9074729")
    assert by_imo.code == ExitCode.OK
    assert "KAVITA" in by_imo.stdout

    nothing = run("search", "zzz")
    assert nothing.code == ExitCode.NOT_FOUND

    both = run("search", "kavita", "--imo", "9074729")
    assert both.code == ExitCode.USAGE


def test_fleet_by_exact_name_and_company_id(run, fake: FakeClient) -> None:  # type: ignore[no-untyped-def]
    by_name = run("fleet", "TORM A/S", "-f", "csv")
    assert by_name.code == ExitCode.OK
    assert len(list(csv.DictReader(io.StringIO(by_name.stdout)))) == 94

    by_id = run("fleet", "--company-id", "0310062", "-f", "json")
    assert json.loads(by_id.stdout)["fleet"]["company"]["name"] == "TORM A/S"


def test_ambiguous_fleet_without_terminal_lists_candidates(run) -> None:  # type: ignore[no-untyped-def]
    result = run("fleet", "--company", "TORM")
    assert result.code == ExitCode.NOT_FOUND
    assert "TORM A/S (0310062)" in result.stderr
    assert "--first-match" in result.stderr


def test_ambiguous_fleet_first_match(run) -> None:  # type: ignore[no-untyped-def]
    result = run("fleet", "TORM", "--first-match", "-f", "json")
    assert result.code == ExitCode.OK
    assert "using TORM A/S (0310062)" in result.stderr


def test_ambiguous_fleet_prompts_on_a_terminal(run) -> None:  # type: ignore[no-untyped-def]
    result = run("fleet", "TORM", "-f", "json", stdin="9\n1\n", tty=True)
    assert result.code == ExitCode.OK
    assert "Choose 1-2" in result.stderr
    assert json.loads(result.stdout)["fleet"]["company"]["company_id"] == "0310062"


def test_fleet_batch(run) -> None:  # type: ignore[no-untyped-def]
    result = run("fleet", "0310062", "TORM", "-f", "json")
    assert result.code == ExitCode.PARTIAL_FAILURE
    statuses = [r["status"] for r in json.loads(result.stdout)["results"]]
    assert statuses == ["ok", "ambiguous"]


def test_configure_show_test_and_clear(run, store: CredentialStore) -> None:  # type: ignore[no-untyped-def]
    shown = run("configure", "--show")
    assert "username user@example.com" in shown.stdout
    assert "secret" not in shown.stdout

    tested = run("configure", "--test")
    assert tested.code == ExitCode.OK
    assert "Logged in as user@example.com" in tested.stderr

    cleared = run("configure", "--clear")
    assert cleared.code == ExitCode.OK
    assert not store.path.exists()


def test_password_option_warns(run) -> None:  # type: ignore[no-untyped-def]
    result = run("vessel", "9074729", "--username", "user@example.com", "--password", "secret")
    assert result.code == ExitCode.OK
    assert "visible in shell history" in result.stderr


def test_delay_and_save_html_reach_the_transport(
    store: CredentialStore, fake: FakeClient, tmp_path: Path
) -> None:
    seen: list[Transport] = []

    def factory(username: str, password: str, transport: Transport) -> FakeClient:
        seen.append(transport)
        return fake

    main(
        ["vessel", "9074729", "--delay", "2.5", "--save-html", str(tmp_path)],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        stdin=io.StringIO(),
        store=store,
        client_factory=factory,  # type: ignore[arg-type]
    )
    assert seen[0].min_interval == 2.5
    assert seen[0].save_html_dir == tmp_path
