"""Command parsing and execution for the interactive shell.

This module has no terminal user interface code, so every command can be tested
directly. The shell application (``tui.app``) only handles display and input.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import output
from ..cache import PageCache
from ..client import DEFAULT_SEARCH_PAGES, EquasisClient
from ..credentials import CredentialStore
from ..exceptions import (
    AuthenticationError,
    EquasisError,
    InvalidInputError,
    LayoutChangedError,
)
from ..models import BatchItem, Fleet, ItemStatus, SearchResults, Vessel
from ..service import (
    LARGE_BATCH_WARNING_THRESHOLD,
    Resolution,
    imo_warnings,
    is_company_id,
    iter_fleets,
    iter_vessels,
    resolve_company,
)
from ..validation import normalize_company_id, normalize_imo, parse_list, split_values

Writer = Callable[[str], None]
StatusUpdater = Callable[[str], None]
ClientFactory = Callable[[], EquasisClient]

_QUOTES = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})


class CommandError(Exception):
    """A problem with how a command was typed."""


# ------------------------------------------------------------------------ specification


@dataclass(frozen=True)
class Param:
    name: str
    help: str
    takes_value: bool = True


@dataclass(frozen=True)
class CommandSpec:
    name: str
    summary: str
    usage: str
    params: tuple[Param, ...] = ()
    details: tuple[str, ...] = ()

    def param(self, name: str) -> Param | None:
        return next((p for p in self.params if p.name == name), None)


FORMAT = Param("format", "output format: table, json, jsonl, csv")
OUTPUT = Param("output", "save to a file (format from the extension)")
FIRST = Param("first", "use the best match when a name matches several companies", False)
PAGES = Param("pages", "result pages to fetch (100 results each)")
REFRESH = Param("refresh", "ignore cached pages and fetch fresh data", False)

COMMANDS: dict[str, CommandSpec] = {
    spec.name: spec
    for spec in (
        CommandSpec(
            "vessel",
            "Full vessel profile by IMO number",
            "vessel /imo IMO [/format FORMAT] [/output FILE]",
            (Param("imo", "IMO number (required)"), REFRESH, FORMAT, OUTPUT),
            ("Includes management, classification, PSC inspections and history.",),
        ),
        CommandSpec(
            "search",
            "Search ships and companies",
            "search /name NAME | /imo IMO | /mmsi MMSI | /callsign CALLSIGN "
            "[/type all|ships|companies] [/pages N] [/format FORMAT] [/output FILE]",
            (
                Param("name", "name to search for (partial matches)"),
                Param("imo", "exact IMO number"),
                Param("mmsi", "exact MMSI"),
                Param("callsign", "exact call sign"),
                Param("type", "all, ships, or companies (name searches)"),
                PAGES,
                REFRESH,
                FORMAT,
                OUTPUT,
            ),
        ),
        CommandSpec(
            "fleet",
            "Vessels associated with a company",
            "fleet /company NAME | /id NUMBER [/first] [/pages N] [/format FORMAT] [/output FILE]",
            (
                Param("company", "company name"),
                Param("id", "7-digit Equasis company number"),
                FIRST,
                PAGES,
                REFRESH,
                FORMAT,
                OUTPUT,
            ),
            (
                "When a name matches several companies the matches are listed; repeat "
                "the command with /id NUMBER or add /first.",
            ),
        ),
        CommandSpec(
            "batch",
            "Look up many vessels or companies",
            'batch /imos "IMO,IMO" | /file FILE | /companies "NAME,NAME" | /company-file FILE '
            "[/fail-fast] [/first] [/format FORMAT] [/output FILE]",
            (
                Param("imos", "comma-separated IMO numbers"),
                Param("file", "file with one IMO number per line"),
                Param("companies", "comma-separated company names or numbers"),
                Param("company-file", "file with one company per line"),
                Param("fail-fast", "stop at the first failed lookup", False),
                FIRST,
                REFRESH,
                FORMAT,
                OUTPUT,
            ),
            ("Files may contain blank lines and # comments.",),
        ),
        CommandSpec("format", "Set the default output format", "format table|json|jsonl|csv"),
        CommandSpec(
            "cache",
            "Show or clear cached Equasis pages",
            "cache [info|clear]",
            details=("Pages are reused for 24 hours; add /refresh to a command to bypass them.",),
        ),
        CommandSpec("status", "Show session status", "status"),
        CommandSpec("clear", "Clear the output", "clear"),
        CommandSpec("help", "Show help for all or one command", "help [COMMAND]"),
        CommandSpec("exit", "Leave the interactive shell", "exit"),
    )
}
ALIASES = {"quit": "exit"}


# ------------------------------------------------------------------------------ parsing


@dataclass
class ParsedCommand:
    name: str
    params: dict[str, str | bool] = field(default_factory=dict)
    arguments: list[str] = field(default_factory=list)

    def text(self, name: str) -> str | None:
        value = self.params.get(name)
        return value if isinstance(value, str) else None

    def flag(self, name: str) -> bool:
        return self.params.get(name) is True


def parse_command(line: str) -> ParsedCommand | None:
    """Parse ``command /param value /flag``.

    Values may be quoted with straight or typographic quotes. Parameters that take a
    value consume the next word even if it starts with ``/`` (for example a file path).

    Raises:
        CommandError: for unknown commands or parameters and missing values.
    """
    text = line.translate(_QUOTES).strip()
    if not text:
        return None
    try:
        lexer = shlex.shlex(text, posix=True)
        lexer.whitespace_split = True
        lexer.escape = ""  # keep backslashes literal, as in Windows paths
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError as exc:
        raise CommandError(f"could not read the command: {exc}") from None

    name = tokens[0].lower().lstrip("/")
    name = ALIASES.get(name, name)
    spec = COMMANDS.get(name)
    if spec is None:
        raise CommandError(f"unknown command '{tokens[0]}'; type 'help' for commands")

    parsed = ParsedCommand(name=name)
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token.startswith("/") and spec.params:
            param = spec.param(token[1:].lower())
            if param is None:
                known = ", ".join(f"/{p.name}" for p in spec.params)
                raise CommandError(f"'{name}' has no parameter {token}; use {known}")
            if not param.takes_value:
                parsed.params[param.name] = True
                index += 1
                continue
            if index + 1 >= len(tokens):
                raise CommandError(f"{token} needs a value")
            parsed.params[param.name] = tokens[index + 1]
            index += 2
        else:
            parsed.arguments.append(token)
            index += 1
    return parsed


# ---------------------------------------------------------------------------- execution


@dataclass
class ShellState:
    output_format: str = "table"
    client: EquasisClient | None = None
    username: str | None = None


class CommandRunner:
    """Runs parsed commands and reports results through ``write`` and ``status``."""

    def __init__(
        self,
        write: Writer,
        status: StatusUpdater,
        *,
        state: ShellState | None = None,
        store: CredentialStore | None = None,
        client_factory: Callable[[str, str], EquasisClient] | None = None,
        cache: PageCache | None = None,
    ) -> None:
        self.write = write
        self.status = status
        self.refresh = False
        self.state = state or ShellState()
        self.store = store or CredentialStore()
        self.cache = cache if cache is not None else PageCache()
        self.client_factory = client_factory or (
            lambda username, password: EquasisClient(username, password, cache=self.cache)
        )

    # ------------------------------------------------------------------- helpers

    @property
    def connected(self) -> bool:
        return self.state.client is not None and self.state.client.logged_in

    def client(self) -> EquasisClient:
        if self.state.client is None:
            credentials = self.store.resolve()
            if credentials is None:
                raise CommandError(
                    "no Equasis credentials found; run 'equasis configure --setup' in a "
                    "terminal, or set EQUASIS_USERNAME and EQUASIS_PASSWORD"
                )
            self.state.client = self.client_factory(credentials.username, credentials.password)
            self.state.username = credentials.username
        self.state.client.refresh = self.refresh
        return self.state.client

    def close(self) -> None:
        if self.state.client is not None:
            self.state.client.close()

    def _format_and_target(self, command: ParsedCommand) -> tuple[str, str | None]:
        explicit = command.text("format")
        target = command.text("output")
        if target and target.lower() in output.FORMATS and not Path(target).suffix:
            explicit, target = target.lower(), None  # "/output json" selects a format
        if explicit and explicit.lower() not in output.FORMATS:
            raise CommandError(f"unknown format '{explicit}'; use {', '.join(output.FORMATS)}")
        fmt = output.resolve_format(
            explicit.lower() if explicit else None, target, default=self.state.output_format
        )
        return fmt, target

    def _emit(self, result: Vessel | SearchResults | Fleet, command: ParsedCommand) -> None:
        fmt, target = self._format_and_target(command)
        text = output.render(result, fmt)
        if target:
            path = output.write_output(text, target)
            self.write(f"Saved {fmt} output to {path}")
        else:
            self.write(text.rstrip("\n"))

    @staticmethod
    def _read_list(path: str) -> list[str]:
        try:
            with open(Path(path).expanduser(), encoding="utf-8") as handle:
                return parse_list(handle)
        except OSError as exc:
            raise CommandError(f"cannot read {path}: {exc.strerror or exc}") from None

    @staticmethod
    def _pages(command: ParsedCommand, default: int | None) -> int | None:
        value = command.text("pages")
        if value is None:
            return default
        if value.lower() == "all":
            return None
        if not value.isdigit() or int(value) < 1:
            raise CommandError("/pages must be a positive number or 'all'")
        return int(value)

    # ------------------------------------------------------------------ dispatch

    def run(self, line: str) -> bool:
        """Execute one line. Returns ``False`` when the shell should exit."""
        try:
            command = parse_command(line)
            if command is None:
                return True
            if command.name == "exit":
                return False
            handler: Callable[[ParsedCommand], None] = getattr(self, f"_cmd_{command.name}")
            self.refresh = command.flag("refresh")
            try:
                handler(command)
            finally:
                self.refresh = False
        except CommandError as exc:
            self.write(f"Error: {exc}")
        except AuthenticationError as exc:
            self.state.client = None
            self.write(f"Login failed: {exc}")
        except InvalidInputError as exc:
            self.write(f"Error: {exc}")
        except LayoutChangedError as exc:
            self.write(
                f"Error: could not read the Equasis page ({exc}). Equasis may have changed "
                "its website; please report it at https://github.com/rhinonix/equasis-cli/issues"
            )
        except EquasisError as exc:
            self.write(f"Error: {exc}")
        except OSError as exc:
            self.write(f"Error: {exc}")
        return True

    # ------------------------------------------------------------------ commands

    def _cmd_vessel(self, command: ParsedCommand) -> None:
        value = command.text("imo") or (command.arguments[0] if command.arguments else None)
        if not value:
            raise CommandError(f"missing /imo\nUsage: {COMMANDS['vessel'].usage}")
        imo = normalize_imo(value)
        self._format_and_target(command)  # validate before making requests
        for warning in imo_warnings(imo):
            self.write(f"Warning: {warning}")
        client = self.client()
        self.status(f"Retrieving IMO {imo}...")
        vessel = client.get_vessel(imo)
        for warning in vessel.warnings:
            self.write(f"Warning: {warning}")
        self._emit(vessel, command)

    def _cmd_search(self, command: ParsedCommand) -> None:
        name = command.text("name") or " ".join(command.arguments) or None
        identifiers = {k: command.text(k) for k in ("imo", "mmsi", "callsign")}
        if name and any(identifiers.values()):
            raise CommandError("search by /name or by an identifier, not both")
        if not name and not any(identifiers.values()):
            raise CommandError(f"missing search terms\nUsage: {COMMANDS['search'].usage}")
        kind = (command.text("type") or "all").lower()
        if kind not in ("all", "ships", "companies"):
            raise CommandError("/type must be all, ships, or companies")
        pages = self._pages(command, DEFAULT_SEARCH_PAGES)
        self._format_and_target(command)

        client = self.client()
        if name:
            self.status(f"Searching for '{name}'...")
            results = client.search(
                name,
                max_pages=pages,
                ships=kind in ("all", "ships"),
                companies=kind in ("all", "companies"),
            )
        else:
            self.status("Searching...")
            results = client.search_ships(
                imo=identifiers["imo"], mmsi=identifiers["mmsi"], call_sign=identifiers["callsign"]
            )
        if results.total_ships and results.total_ships > len(results.ships):
            self.write(
                f"Note: showing {len(results.ships)} of {results.total_ships} ships; "
                "add /pages N or /pages all for more"
            )
        self._emit(results, command)

    def _cmd_fleet(self, command: ParsedCommand) -> None:
        company_id = command.text("id")
        name = command.text("company") or " ".join(command.arguments) or None
        if company_id and name:
            raise CommandError("use either /company or /id, not both")
        if not company_id and not name:
            raise CommandError(f"missing /company or /id\nUsage: {COMMANDS['fleet'].usage}")
        pages = self._pages(command, None)
        self._format_and_target(command)

        client = self.client()
        if name and is_company_id(name):
            company_id = name
        if company_id:
            company_id = normalize_company_id(company_id)
        elif name:
            self.status(f"Looking up companies matching '{name}'...")
            match = resolve_company(client, name)
            if match.resolution is Resolution.NOT_FOUND:
                self.write(f"No company matches '{name}'.")
                return
            if match.resolution is Resolution.AMBIGUOUS and not command.flag("first"):
                self.write(f"'{name}' matches {len(match.candidates)} companies:")
                self.write(output.render_company_choices(match.candidates))
                self.write("Run 'fleet /id NUMBER' with the company number, or add /first.")
                return
            chosen = match.company or match.candidates[0]
            if match.resolution is Resolution.AMBIGUOUS:
                self.write(
                    f"Using {chosen.name} ({chosen.company_id}), the best of "
                    f"{len(match.candidates)} matches."
                )
            company_id = chosen.company_id

        if company_id is None:
            return
        self.status(f"Retrieving fleet of company {company_id}...")
        fleet = client.get_fleet(company_id, max_pages=pages)
        self._emit(fleet, command)

    def _cmd_batch(self, command: ParsedCommand) -> None:
        sources = {key: command.text(key) for key in ("imos", "file", "companies", "company-file")}
        given = [key for key, value in sources.items() if value]
        if len(given) != 1:
            raise CommandError(
                "use exactly one of /imos, /file, /companies, or /company-file\n"
                f"Usage: {COMMANDS['batch'].usage}"
            )
        source = given[0]
        value = sources[source] or ""
        if source == "imos":
            kind, queries = "vessels", split_values([value])
        elif source == "file":
            kind, queries = "vessels", self._read_list(value)
        elif source == "companies":
            kind, queries = "fleets", split_values([value])
        else:
            kind, queries = "fleets", self._read_list(value)
        if not queries:
            raise CommandError("the batch is empty")

        fmt, target = self._format_and_target(command)
        noun = "vessels" if kind == "vessels" else "companies"
        if len(queries) > LARGE_BATCH_WARNING_THRESHOLD:
            self.write(
                f"Warning: {len(queries)} {noun} is a large batch; very large batches can lead "
                "Equasis to restrict your account."
            )
        self.write(f"Processing {len(queries)} {noun}...")

        def on_start(position: int, total: int, query: str) -> None:
            self.status(f"[{position}/{total}] {query}")

        client = self.client()
        items: Any
        if kind == "vessels":
            items = iter_vessels(
                client, queries, fail_fast=command.flag("fail-fast"), on_start=on_start
            )
        else:
            items = iter_fleets(
                client,
                queries,
                first_match=command.flag("first"),
                fail_fast=command.flag("fail-fast"),
                on_start=on_start,
            )

        report = output.BatchReport(kind="vessels" if kind == "vessels" else "fleets")
        for item in items:
            report.items.append(item)
            self._report_item(item)

        text = output.render(report, fmt)
        if target:
            path = output.write_output(text, target)
            self.write(f"Saved {fmt} output to {path}")
        else:
            self.write(text.rstrip("\n"))
        self.write(f"{report.succeeded} of {len(report.items)} {noun} retrieved.")

    def _report_item(self, item: BatchItem[Any]) -> None:
        mark = "ok" if item.status is ItemStatus.OK else item.status.value.replace("_", " ")
        line = f"  {item.query}: {mark}"
        if item.error:
            line += f" - {item.error}"
        self.write(line)
        for warning in item.warnings:
            self.write(f"    warning: {warning}")

    def _cmd_format(self, command: ParsedCommand) -> None:
        if not command.arguments:
            self.write(f"Default output format: {self.state.output_format}")
            return
        choice = command.arguments[0].lower()
        if choice not in output.FORMATS:
            raise CommandError(f"unknown format '{choice}'; use {', '.join(output.FORMATS)}")
        self.state.output_format = choice
        self.write(f"Default output format set to {choice}")

    def _cmd_status(self, command: ParsedCommand) -> None:
        credentials = self.store.resolve()
        account = self.state.username or (credentials.username if credentials else None)
        lines = [
            "Session status",
            f"  Connected:      {'yes' if self.connected else 'no'}",
            f"  Account:        {account or 'not configured'}",
            f"  Credentials:    {credentials.source.value if credentials else 'not found'}",
            f"  Default format: {self.state.output_format}",
        ]
        self.write("\n".join(lines))

    def _cmd_cache(self, command: ParsedCommand) -> None:
        action = command.arguments[0].lower() if command.arguments else "info"
        if action == "clear":
            removed = self.cache.clear()
            self.write(f"Removed {removed} cached page{'s' if removed != 1 else ''}.")
            return
        if action != "info":
            raise CommandError("use 'cache info' or 'cache clear'")
        stats = self.cache.stats()
        self.write(
            f"Cache: {stats.entries} pages ({stats.size_bytes / 1_048_576:.1f} MB) in "
            f"{stats.directory}"
        )

    def _cmd_clear(self, command: ParsedCommand) -> None:  # handled by the application
        pass

    def _cmd_help(self, command: ParsedCommand) -> None:
        self.write(help_text(command.arguments[0] if command.arguments else None))


def help_text(topic: str | None = None) -> str:
    """Help for all commands, or detailed help for one."""
    if topic:
        name = ALIASES.get(topic.lower().lstrip("/"), topic.lower().lstrip("/"))
        spec = COMMANDS.get(name)
        if spec is None:
            return f"No help for '{topic}'. Commands: {', '.join(COMMANDS)}"
        lines = [f"{spec.name}: {spec.summary}", "", f"Usage: {spec.usage}"]
        if spec.params:
            lines.append("")
            width = max(len(p.name) for p in spec.params) + 1
            lines += [f"  /{p.name.ljust(width)} {p.help}" for p in spec.params]
        if spec.details:
            lines += ["", *spec.details]
        return "\n".join(lines)

    width = max(len(name) for name in COMMANDS)
    lines = ["Commands:"]
    lines += [f"  {spec.name.ljust(width)}  {spec.summary}" for spec in COMMANDS.values()]
    lines += [
        "",
        "Type 'help COMMAND' for parameters, for example 'help batch'.",
        'Values with spaces need quotes: search /name "EVER GIVEN"',
        "/output FILE saves results; the format follows the extension (.json, .jsonl, .csv).",
    ]
    return "\n".join(lines)


def split_words(line: str) -> Sequence[str]:
    """Whitespace-separated words, used for menus and completion."""
    return re.split(r"\s+", line.strip()) if line.strip() else []
