"""Command-line interface.

Data goes to stdout (or ``--output-file``); progress, warnings and errors go to
stderr. The exit status tells scripts what happened (see :class:`ExitCode`).
"""

from __future__ import annotations

import argparse
import enum
import getpass
import logging
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import IO, Any, NoReturn

from . import output
from ._version import __version__
from .banner import DISCLAIMER
from .client import DEFAULT_SEARCH_PAGES, EquasisClient
from .console import Console
from .credentials import CredentialStore
from .exceptions import (
    AuthenticationError,
    ConfigurationError,
    EquasisError,
    InvalidInputError,
    LayoutChangedError,
    NetworkError,
    NotFoundError,
)
from .models import BatchItem, CompanySummary, ItemStatus
from .service import (
    LARGE_BATCH_WARNING_THRESHOLD,
    Resolution,
    describe_candidates,
    imo_warnings,
    is_company_id,
    iter_fleets,
    iter_vessels,
    resolve_company,
)
from .transport import Transport
from .validation import normalize_company_id, normalize_imo, parse_list, split_values

logger = logging.getLogger("equasis_cli")


class ExitCode(enum.IntEnum):
    OK = 0
    ERROR = 1
    USAGE = 2
    AUTHENTICATION = 3
    NOT_FOUND = 4
    PARTIAL_FAILURE = 5
    LAYOUT_CHANGED = 6
    INTERRUPTED = 130


EXAMPLES = """\
examples:
  equasis vessel 9811000
  equasis vessel --imo-file imos.txt -o vessels.csv
  equasis search "EVER GIVEN"
  equasis search --mmsi 353136000 --format json
  equasis fleet "TORM A/S" --format csv -o torm.csv
  equasis configure --setup

exit status:
  0 success, 1 error, 2 invalid usage, 3 authentication failed, 4 not found,
  5 some batch items failed, 6 Equasis page layout changed, 130 interrupted
"""


# ------------------------------------------------------------------------- arguments


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(ExitCode.USAGE, f"{self.prog}: error: {message}\n")


def _add_common_options(parser: argparse.ArgumentParser, *, subcommand: bool) -> None:
    """Options accepted both before and after the command name.

    On subcommands the defaults are suppressed, so a value given after the command
    overrides one given before it without resetting it when omitted.
    """

    def default(value: Any) -> Any:
        return argparse.SUPPRESS if subcommand else value

    group = parser.add_argument_group("output options")
    group.add_argument(
        "-f",
        "--format",
        choices=output.FORMATS,
        default=default(None),
        help="output format (default: inferred from --output-file, otherwise table)",
    )
    group.add_argument(
        "--output",
        dest="format",
        choices=output.FORMATS,
        default=default(None),
        help=argparse.SUPPRESS,  # pre-3.0 name for --format
    )
    group.add_argument(
        "-o",
        "--output-file",
        metavar="PATH",
        default=default(None),
        help="write results to PATH instead of stdout",
    )
    group.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        default=default(False),
        help="only print results and errors",
    )
    group.add_argument(
        "--no-color", action="store_true", default=default(False), help="disable colored messages"
    )

    connection = parser.add_argument_group("connection options")
    connection.add_argument(
        "--username", default=default(None), help="Equasis username (e-mail address)"
    )
    connection.add_argument(
        "--password",
        default=default(None),
        help="Equasis password; prefer 'equasis configure --setup' or EQUASIS_PASSWORD",
    )
    connection.add_argument(
        "--delay",
        type=float,
        metavar="SECONDS",
        default=default(1.0),
        help="minimum pause between requests to Equasis (default: 1.0)",
    )
    connection.add_argument(
        "--debug", action="store_true", default=default(False), help="log HTTP activity to stderr"
    )
    connection.add_argument(
        "--save-html",
        metavar="DIR",
        type=Path,
        default=default(None),
        help="save every Equasis page to DIR for troubleshooting (pages include your account name)",
    )
    connection.add_argument(
        "--no-banner", action="store_true", default=default(False), help=argparse.SUPPRESS
    )


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="equasis",
        description="Look up vessels, PSC inspections, ownership history and fleets in Equasis.",
        epilog=f"{EXAMPLES}\n{DISCLAIMER}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="start the interactive shell (default with no command)",
    )
    _add_common_options(parser, subcommand=False)

    commands = parser.add_subparsers(dest="command", metavar="COMMAND", parser_class=_Parser)

    vessel = commands.add_parser(
        "vessel",
        help="full vessel profile by IMO number",
        description=(
            "Retrieve vessel particulars, management, classification, PSC inspections and "
            "name, flag and company history. Several IMO numbers produce a batch report."
        ),
    )
    vessel.add_argument("imos", nargs="*", metavar="IMO", help="IMO number(s)")
    vessel.add_argument(
        "--imo", nargs="+", action="extend", default=[], metavar="IMO", help=argparse.SUPPRESS
    )
    vessel.add_argument(
        "--imo-file",
        metavar="FILE",
        help="read IMO numbers from FILE ('-' for stdin); one per line, '#' starts a comment",
    )
    vessel.add_argument(
        "--fail-fast", action="store_true", help="stop a batch at the first failed lookup"
    )
    vessel.add_argument("--continue-on-error", action="store_true", help=argparse.SUPPRESS)
    vessel.add_argument("--progress", action="store_true", help=argparse.SUPPRESS)
    _add_common_options(vessel, subcommand=True)

    search = commands.add_parser(
        "search",
        help="search ships and companies",
        description=(
            "Search by name (partial matches, ships and companies) or look up ships by an "
            "exact IMO number, MMSI or call sign."
        ),
    )
    search.add_argument("query", nargs="?", help="name to search for")
    search.add_argument("--name", help=argparse.SUPPRESS)
    search.add_argument("--imo", help="find a ship by IMO number")
    search.add_argument("--mmsi", help="find a ship by MMSI")
    search.add_argument("--call-sign", help="find a ship by call sign")
    search.add_argument(
        "--type",
        choices=("all", "ships", "companies"),
        default="all",
        help="which results to include for name searches (default: all)",
    )
    pages = search.add_mutually_exclusive_group()
    pages.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_SEARCH_PAGES,
        metavar="N",
        help=f"result pages to fetch, 100 results each (default: {DEFAULT_SEARCH_PAGES})",
    )
    pages.add_argument(
        "--all-pages", action="store_const", dest="max_pages", const=None, help="fetch every page"
    )
    _add_common_options(search, subcommand=True)

    fleet = commands.add_parser(
        "fleet",
        help="vessels associated with a company",
        description=(
            "Retrieve the fleet of a company, given its name or 7-digit Equasis company "
            "number. Several companies produce a batch report."
        ),
    )
    fleet.add_argument("companies", nargs="*", metavar="COMPANY", help="company name or number")
    fleet.add_argument(
        "--company", nargs="+", action="extend", default=[], metavar="NAME", help=argparse.SUPPRESS
    )
    fleet.add_argument(
        "--company-id",
        nargs="+",
        action="extend",
        default=[],
        metavar="NUMBER",
        help="Equasis company number(s)",
    )
    fleet.add_argument(
        "--company-file",
        metavar="FILE",
        help="read company names or numbers from FILE ('-' for stdin), one per line",
    )
    fleet.add_argument(
        "--first-match",
        action="store_true",
        help="when a name matches several companies, use the best match instead of stopping",
    )
    fleet.add_argument(
        "--max-pages", type=int, metavar="N", help="limit fleet pages (100 vessels each)"
    )
    fleet.add_argument(
        "--fail-fast", action="store_true", help="stop a batch at the first failed lookup"
    )
    fleet.add_argument("--continue-on-error", action="store_true", help=argparse.SUPPRESS)
    fleet.add_argument("--progress", action="store_true", help=argparse.SUPPRESS)
    _add_common_options(fleet, subcommand=True)

    configure = commands.add_parser(
        "configure",
        help="manage stored credentials",
        description=f"Credentials are stored in {CredentialStore().path} with owner-only access.",
    )
    action = configure.add_mutually_exclusive_group()
    action.add_argument("--setup", action="store_true", help="store credentials interactively")
    action.add_argument("--show", action="store_true", help="show where credentials come from")
    action.add_argument("--test", action="store_true", help="check that the credentials work")
    action.add_argument("--clear", action="store_true", help="delete stored credentials")
    _add_common_options(configure, subcommand=True)

    commands.add_parser("interactive", help="start the interactive shell")
    return parser


# ----------------------------------------------------------------------------- runner


class Runner:
    """Executes a parsed command and maps failures to exit codes."""

    def __init__(
        self,
        args: argparse.Namespace,
        *,
        console: Console,
        stdout: IO[str],
        stdin: IO[str],
        store: CredentialStore,
        client_factory: Callable[[str, str, Transport], EquasisClient],
    ) -> None:
        self.args = args
        self.console = console
        self.stdout = stdout
        self.stdin = stdin
        self.store = store
        self.client_factory = client_factory

    # ---------------------------------------------------------------- helpers

    def client(self) -> EquasisClient:
        args = self.args
        if args.password and args.username:
            self.console.warn(
                "--password is visible in shell history and process listings; "
                "prefer 'equasis configure --setup' or EQUASIS_PASSWORD"
            )
        credentials = self.store.resolve(args.username, args.password)
        if credentials is None:
            raise ConfigurationError("no Equasis credentials found")
        transport = Transport(min_interval=max(0.0, args.delay), save_html_dir=args.save_html)
        return self.client_factory(credentials.username, credentials.password, transport)

    @property
    def format(self) -> str:
        return output.resolve_format(self.args.format, self.args.output_file)

    def emit(self, text: str) -> None:
        if self.args.output_file:
            path = output.write_output(text, self.args.output_file)
            self.console.success(f"Saved to {path}")
        else:
            self.stdout.write(text)
            self.stdout.flush()

    def read_list(self, path: str) -> list[str]:
        if path == "-":
            return parse_list(self.stdin)
        try:
            with open(path, encoding="utf-8") as handle:
                return parse_list(handle)
        except OSError as exc:
            raise InvalidInputError(f"cannot read {path}: {exc.strerror or exc}") from exc

    def interactive_terminal(self) -> bool:
        return self.console.is_terminal and bool(getattr(self.stdin, "isatty", lambda: False)())

    # --------------------------------------------------------------- commands

    def run(self) -> int:
        command = self.args.command
        handler = {
            "vessel": self.vessel,
            "search": self.search,
            "fleet": self.fleet,
            "configure": self.configure,
        }[command]
        return handler()

    def vessel(self) -> int:
        args = self.args
        queries = split_values([*args.imos, *args.imo])
        from_file = bool(args.imo_file)
        if from_file:
            queries += [q for q in self.read_list(args.imo_file) if q not in queries]
        if not queries:
            raise InvalidInputError("provide at least one IMO number or --imo-file")

        if len(queries) == 1 and not from_file:
            imo = normalize_imo(queries[0])
            for warning in imo_warnings(imo):
                self.console.warn(warning)
            with self.client() as client:
                self.console.progress(f"Retrieving IMO {imo}...")
                vessel = client.get_vessel(imo)
            for warning in vessel.warnings:
                self.console.warn(warning)
            self.emit(output.render(vessel, self.format))
            return ExitCode.OK

        return self._batch("vessels", queries)

    def search(self) -> int:
        args = self.args
        query = args.query or args.name
        identifiers = (args.imo, args.mmsi, args.call_sign)
        if query and any(identifiers):
            raise InvalidInputError("search by name or by identifier, not both")
        with self.client() as client:
            if any(identifiers):
                self.console.progress("Searching Equasis...")
                results = client.search_ships(
                    imo=args.imo, mmsi=args.mmsi, call_sign=args.call_sign
                )
            elif query:
                if args.max_pages is not None and args.max_pages < 1:
                    raise InvalidInputError("--max-pages must be at least 1")
                self.console.progress(f"Searching Equasis for '{query}'...")
                results = client.search(
                    query,
                    max_pages=args.max_pages,
                    ships=args.type in ("all", "ships"),
                    companies=args.type in ("all", "companies"),
                )
            else:
                raise InvalidInputError(
                    "provide a name to search for, or --imo, --mmsi or --call-sign"
                )

        if results.total_ships and results.total_ships > len(results.ships):
            self.console.warn(
                f"showing {len(results.ships)} of {results.total_ships} ships; "
                "use --max-pages or --all-pages for more"
            )
        self.emit(output.render(results, self.format))
        if not results.ships and not results.companies:
            self.console.info("No matches found.")
            return ExitCode.NOT_FOUND
        return ExitCode.OK

    def fleet(self) -> int:
        args = self.args
        queries = [*args.companies, *args.company]
        queries += [normalize_company_id(c) for c in args.company_id]
        from_file = bool(args.company_file)
        if from_file:
            queries += self.read_list(args.company_file)
        queries = parse_list(queries)
        if not queries:
            raise InvalidInputError("provide a company name, --company-id, or --company-file")
        if args.max_pages is not None and args.max_pages < 1:
            raise InvalidInputError("--max-pages must be at least 1")

        if len(queries) > 1 or from_file:
            return self._batch("fleets", queries)

        query = queries[0]
        with self.client() as client:
            if is_company_id(query):
                company_id = query
            else:
                self.console.progress(f"Looking up companies matching '{query}'...")
                company_id = self._choose_company(client, query).company_id
            self.console.progress(f"Retrieving fleet of company {company_id}...")
            fleet = client.get_fleet(company_id, max_pages=args.max_pages)
        self.emit(output.render(fleet, self.format))
        return ExitCode.OK

    def _choose_company(self, client: EquasisClient, query: str) -> CompanySummary:
        match = resolve_company(client, query)
        if match.resolution is Resolution.NOT_FOUND:
            raise NotFoundError(f"no company matches '{query}'")
        if match.resolution is Resolution.RESOLVED and match.company is not None:
            return match.company
        candidates = match.candidates
        if self.args.first_match:
            chosen = candidates[0]
            self.console.warn(
                f"'{query}' matched {len(candidates)} companies; using {chosen.name} "
                f"({chosen.company_id})"
            )
            return chosen
        if not self.interactive_terminal():
            raise NotFoundError(
                f"'{query}' matches {len(candidates)} companies: "
                f"{describe_candidates(candidates)}. "
                "Pass a company number (--company-id) or --first-match"
            )
        self.console.info(f"'{query}' matches {len(candidates)} companies:")
        self.console.info(output.render_company_choices(candidates))
        while True:
            self.console.stream.write(f"Choose 1-{len(candidates)} (or q to cancel): ")
            self.console.stream.flush()
            answer = self.stdin.readline().strip().lower()
            if answer in ("", "q", "quit"):
                raise KeyboardInterrupt
            if answer.isdigit() and 1 <= int(answer) <= len(candidates):
                return candidates[int(answer) - 1]

    def _batch(self, kind: str, queries: list[str]) -> int:
        args = self.args
        fmt = self.format
        noun = "vessels" if kind == "vessels" else "companies"
        if len(queries) > LARGE_BATCH_WARNING_THRESHOLD:
            self.console.warn(
                f"processing {len(queries)} {noun}; very large batches can lead Equasis to "
                "restrict your account. Consider splitting the work across days."
            )
        self.console.info(f"Processing {len(queries)} {noun}...")

        def on_start(position: int, total: int, query: str) -> None:
            self.console.progress(f"[{position}/{total}] {query}")

        report = output.BatchReport(kind="vessels" if kind == "vessels" else "fleets")
        stream: IO[str] | None = None
        if fmt == "jsonl":
            if args.output_file:
                target = Path(args.output_file).expanduser()
                target.parent.mkdir(parents=True, exist_ok=True)
                stream = open(target, "w", encoding="utf-8", newline="")  # noqa: SIM115
            else:
                stream = self.stdout

        try:
            with self.client() as client:
                items: Any
                if kind == "vessels":
                    items = iter_vessels(
                        client, queries, fail_fast=args.fail_fast, on_start=on_start
                    )
                else:
                    items = iter_fleets(
                        client,
                        queries,
                        first_match=args.first_match,
                        fail_fast=args.fail_fast,
                        max_pages=args.max_pages,
                        on_start=on_start,
                    )
                for item in items:
                    self._report_item(item)
                    report.items.append(item)
                    if stream is not None:
                        stream.write(output.render_batch_item_jsonl(report.kind, item))
                        stream.flush()
        finally:
            if stream is not None and stream is not self.stdout:
                stream.close()

        if stream is None:
            self.emit(output.render(report, fmt))
        elif args.output_file:
            self.console.success(f"Saved to {Path(args.output_file).expanduser()}")

        summary = f"{report.succeeded} of {len(report.items)} {noun} retrieved"
        if report.failed:
            self.console.warn(summary)
            return ExitCode.PARTIAL_FAILURE
        self.console.success(summary)
        return ExitCode.OK

    def _report_item(self, item: BatchItem[Any]) -> None:
        for warning in item.warnings:
            self.console.warn(f"{item.query}: {warning}")
        if item.status is not ItemStatus.OK:
            self.console.warn(f"{item.query}: {item.error}")

    def configure(self) -> int:
        args = self.args
        store = self.store
        if args.clear:
            if store.clear():
                self.console.success(f"Removed {store.path}")
            else:
                self.console.info(f"No stored credentials at {store.path}")
            return ExitCode.OK
        if args.show:
            info = store.describe()
            lines = [
                "Credential sources (highest priority first):",
                "  1. --username / --password options",
                "  2. environment variables: "
                + ", ".join(
                    f"{k} {'set' if v else 'not set'}" for k, v in info["environment"].items()
                ),
                f"  3. credentials file: {info['file']['path']}",
                f"     {'present' if info['file']['complete'] else 'not configured'}"
                + (f" (username {info['file']['username']})" if info["file"]["username"] else ""),
            ]
            self.stdout.write("\n".join(lines) + "\n")
            return ExitCode.OK
        if args.test:
            credentials = store.resolve(args.username, args.password)
            if credentials is None:
                raise ConfigurationError("no Equasis credentials found")
            with self.client() as client:
                self.console.progress("Logging in to Equasis...")
                client.login()
            self.console.success(
                f"Logged in as {credentials.username} (from {credentials.source.value})"
            )
            return ExitCode.OK
        if args.setup:
            return self._setup()
        build_parser().parse_args(["configure", "--help"])
        return ExitCode.OK  # pragma: no cover - --help exits

    def _setup(self) -> int:
        store = self.store
        if not self.interactive_terminal():
            raise InvalidInputError("configure --setup needs an interactive terminal")
        self.console.info(f"Credentials will be stored in {store.path} (readable only by you).")
        self.console.stream.write("Equasis username (e-mail): ")
        self.console.stream.flush()
        username = self.stdin.readline().strip()
        password = getpass.getpass("Equasis password: ")
        if not username or not password:
            raise InvalidInputError("username and password must not be empty")

        transport = Transport(min_interval=0)
        try:
            self.console.progress("Checking the credentials with Equasis...")
            self.client_factory(username, password, transport).login()
            self.console.success("Login succeeded.")
        except AuthenticationError as exc:
            self.console.error(str(exc))
            self.console.stream.write("Save these credentials anyway? [y/N]: ")
            self.console.stream.flush()
            if self.stdin.readline().strip().lower() not in ("y", "yes"):
                self.console.info("Nothing saved.")
                return ExitCode.AUTHENTICATION
        except NetworkError as exc:
            self.console.warn(f"could not verify the credentials: {exc}")
        finally:
            transport.close()

        path = store.save(username, password)
        self.console.success(f"Saved credentials to {path}")
        return ExitCode.OK


# ------------------------------------------------------------------------------ entry


def _configure_logging(debug: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
        force=True,
    )
    if not debug:
        logging.getLogger("urllib3").setLevel(logging.WARNING)


def _start_interactive() -> int:
    from .tui import InteractiveShell

    InteractiveShell().start()
    return ExitCode.OK


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: IO[str] | None = None,
    stdin: IO[str] | None = None,
    stderr: IO[str] | None = None,
    store: CredentialStore | None = None,
    client_factory: Callable[[str, str, Transport], EquasisClient] | None = None,
) -> int:
    """Run the CLI and return the exit status."""
    stdout = stdout or sys.stdout
    stdin = stdin or sys.stdin
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()

    if not argv:
        if stdin.isatty() and stdout.isatty():
            return _start_interactive()
        parser.print_help(stderr or sys.stderr)
        return ExitCode.USAGE

    args = parser.parse_args(argv)
    console = Console(stderr, quiet=args.quiet, color=False if args.no_color else None)
    if args.interactive or args.command == "interactive":
        return _start_interactive()
    if args.command is None:
        parser.print_help(stdout)
        return ExitCode.USAGE

    _configure_logging(args.debug)
    runner = Runner(
        args,
        console=console,
        stdout=stdout,
        stdin=stdin,
        store=store or CredentialStore(),
        client_factory=client_factory
        or (
            lambda username, password, transport: EquasisClient(
                username, password, transport=transport
            )
        ),
    )
    try:
        return runner.run()
    except KeyboardInterrupt:
        console.error("interrupted")
        return ExitCode.INTERRUPTED
    except ConfigurationError as exc:
        console.error(
            str(exc),
            hint="run 'equasis configure --setup' or set EQUASIS_USERNAME and EQUASIS_PASSWORD",
        )
        return ExitCode.AUTHENTICATION
    except AuthenticationError as exc:
        console.error(str(exc), hint="check your details with 'equasis configure --test'")
        return ExitCode.AUTHENTICATION
    except InvalidInputError as exc:
        console.error(str(exc))
        return ExitCode.USAGE
    except NotFoundError as exc:
        console.error(str(exc))
        return ExitCode.NOT_FOUND
    except LayoutChangedError as exc:
        console.error(
            f"could not read the Equasis page: {exc}",
            hint=(
                "Equasis may have changed its website. Re-run with --save-html DIR and "
                "report it at https://github.com/rhinonix/equasis-cli/issues "
                "(remove your name from saved pages)"
            ),
        )
        return ExitCode.LAYOUT_CHANGED
    except EquasisError as exc:
        console.error(str(exc))
        return ExitCode.ERROR
    except OSError as exc:
        console.error(f"{exc.strerror or exc}: {exc.filename}" if exc.filename else str(exc))
        return ExitCode.ERROR


def run() -> NoReturn:
    """Console script entry point."""
    sys.exit(main())
