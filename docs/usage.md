# Usage reference

This page covers every command and option. For a quick introduction see the
[README](../README.md); for output fields see [output-schema.md](output-schema.md).

- [Credentials](#credentials)
- [Global options](#global-options)
- [vessel](#vessel)
- [search](#search)
- [fleet](#fleet)
- [configure](#configure)
- [cache](#cache)
- [Interactive shell](#interactive-shell)
- [Batch input files](#batch-input-files)
- [Exit codes](#exit-codes)
- [Environment variables](#environment-variables)
- [Shell completion](#shell-completion)

## Credentials

equasis-cli logs in with your own Equasis account and looks for credentials in this order:

1. `--username` and `--password` options
2. `EQUASIS_USERNAME` and `EQUASIS_PASSWORD` environment variables
3. The credentials file written by `equasis configure --setup`

The credentials file is `$XDG_CONFIG_HOME/equasis-cli/credentials.json`
(`~/.config/equasis-cli/credentials.json` by default) on Linux and macOS, and
`%APPDATA%\equasis-cli\credentials.json` on Windows. It is created readable only by you,
and equasis-cli warns if its permissions allow other users to read it.

Avoid `--password` where possible: command-line arguments are visible in shell history and
process listings.

## Global options

These options work before or after the command name, so `equasis -f json vessel 9811000`
and `equasis vessel 9811000 -f json` are equivalent.

| Option | Description |
| --- | --- |
| `-f`, `--format {table,json,jsonl,csv}` | Output format. Defaults to the format implied by `--output-file`, otherwise `table`. |
| `-o`, `--output-file PATH` | Write results to `PATH` instead of standard output. Parent directories are created; the file is replaced atomically. |
| `-q`, `--quiet` | Print only results, warnings, and errors |
| `--no-color` | Disable colored messages (also honoured: `NO_COLOR`) |
| `--username USERNAME` | Equasis username (the e-mail address you registered with) |
| `--password PASSWORD` | Equasis password |
| `--delay SECONDS` | Minimum pause between requests to Equasis (default `1.0`) |
| `--no-cache` | Neither read nor write the page cache |
| `--refresh` | Fetch fresh pages even when cached copies exist (fresh pages are still cached) |
| `--debug` | Log HTTP requests, retries, and cache use to stderr |
| `--save-html DIR` | Save every page received from Equasis to `DIR`. Saved pages include your account name. |
| `--version` | Print the version and exit |

File extensions map to formats as follows: `.json` is JSON, `.jsonl` and `.ndjson` are
JSON Lines, `.csv` is CSV, and `.txt` is a table. An explicit `--format` always wins.

Results are written to standard output. Progress messages, warnings, and errors go to
standard error, so output can be piped safely.

## vessel

```text
equasis vessel [IMO ...] [--imo-file FILE] [--fail-fast]
```

Retrieves the full profile of a vessel from the Ship Info, Inspections, and Ship History
pages: particulars, flag performance, management, classification, safety management
certificates, P&I insurance, sightings, PSC inspections, and name, flag, class, and company
history, plus [indicators](output-schema.md#indicators).

IMO numbers may be written as `9811000` or `IMO 9811000`. A number that fails the IMO
check digit is still looked up, with a warning that it may contain a typo.

One IMO number produces a single vessel document. Several numbers, or any `--imo-file`,
produce a batch report:

- Every input appears in the report with a status of `ok`, `not_found`, or `error`.
- Processing continues after failures unless `--fail-fast` is given.
- With JSON Lines output, each result is written as soon as it is available.
- The exit code is `5` if any item failed.

If a secondary page (Inspections or Ship History) cannot be read, the profile is still
returned and the problem is listed under `warnings`.

## search

```text
equasis search QUERY [--type {all,ships,companies}] [--max-pages N | --all-pages]
equasis search --imo IMO | --mmsi MMSI | --call-sign CALL_SIGN
```

A name search matches partial names and returns both ships and companies. Equasis returns
100 results per page. equasis-cli fetches up to 3 pages by default; use `--max-pages` or
`--all-pages` for more. A warning is shown when results were truncated.

Identifier searches use Equasis advanced search and return ships whose IMO number, MMSI,
or call sign match exactly.

The exit code is `4` if nothing matched.

## fleet

```text
equasis fleet [COMPANY ...] [--company-id NUMBER ...] [--company-file FILE]
              [--first-match] [--max-pages N] [--fail-fast]
```

Retrieves every vessel associated with a company: particulars, current class, detention
counts for the last three years, and the roles the company holds (registered owner, ship
manager, ISM manager, and so on).

A company can be given by name or by its 7-digit Equasis company number (shown by
`equasis search NAME --type companies`). Names are resolved as follows:

1. A single case-insensitive exact name match is used.
2. A search that returns exactly one company is used.
3. Otherwise the name is ambiguous. In a terminal you are asked to choose; elsewhere the
   matches are listed and the command exits with code `4`. `--first-match` uses the best
   match instead.

Several companies, or any `--company-file`, produce a batch report as for `vessel`.
Ambiguous names in a batch are reported with status `ambiguous` unless `--first-match` is
set.

## configure

| Command | Description |
| --- | --- |
| `equasis configure --setup` | Prompt for credentials, check them against Equasis, and save them |
| `equasis configure --test` | Log in with the configured credentials |
| `equasis configure --show` | Show which credential sources are set (never the password) |
| `equasis configure --clear` | Delete the credentials file |

## cache

```text
equasis cache [info|clear]
```

Equasis pages are cached for 24 hours so repeated lookups do not send the same requests
again. This also means an interrupted batch can be re-run without fetching completed items
a second time. Login, error, and not-found pages are never cached.

The cache is stored in `$XDG_CACHE_HOME/equasis-cli` (`~/.cache/equasis-cli` by default),
or `%LOCALAPPDATA%\equasis-cli\Cache` on Windows. `EQUASIS_CACHE_DIR` overrides the
location. Cached pages contain your Equasis account name, so the directory is readable
only by you.

`equasis cache` shows the location, number of pages, and size; `equasis cache clear`
deletes the cached pages.

## Interactive shell

Start the shell by running `equasis` with no arguments (or `equasis interactive`). The
session stays logged in between commands.

| Command | Parameters |
| --- | --- |
| `vessel` | `/imo IMO`, `/refresh`, `/format FORMAT`, `/output FILE` |
| `search` | `/name NAME` or `/imo IMO` or `/mmsi MMSI` or `/callsign CALLSIGN`; `/type all\|ships\|companies`, `/pages N\|all`, `/refresh`, `/format`, `/output` |
| `fleet` | `/company NAME` or `/id NUMBER`; `/first`, `/pages N\|all`, `/refresh`, `/format`, `/output` |
| `batch` | `/imos "IMO,IMO"` or `/file FILE` or `/companies "NAME,NAME"` or `/company-file FILE`; `/fail-fast`, `/first`, `/refresh`, `/format`, `/output` |
| `format` | `table`, `json`, `jsonl`, or `csv`: sets the default format for the session |
| `cache` | `info` or `clear` |
| `status` | Connection, account, credential source, and default format |
| `help` | `help` lists commands; `help COMMAND` shows its parameters |
| `clear` | Clears the output |
| `exit`, `quit` | Leaves the shell |

Quote values that contain spaces: `search /name "EVER GIVEN"`. Straight and typographic
quotes both work. `/output FILE` picks the format from the file extension, and
`/output json` (a format name without an extension) sets the format for that command.

When a company name is ambiguous, `fleet` lists the matches with their company numbers.
Repeat the command with `/id NUMBER`, or add `/first`.

Keyboard shortcuts:

| Key | Action |
| --- | --- |
| `/` | Show commands, or the parameters of the current command |
| `Tab` | Insert the highlighted menu item, or complete a command name |
| `Up`, `Down` | Move through the menu, or recall previous commands |
| `Esc` | Close the menu; with no menu open, scroll the output (press `i`, `q`, or start typing to return) |
| `j`, `k`, arrows | Scroll one line while scrolling the output |
| `PgUp`, `PgDn`, `Shift+Up`, `Shift+Down`, `Ctrl+K`, `Ctrl+J` | Scroll the output |
| `?` | Show or hide the shortcut list (on an empty input line) |
| `Ctrl+C` | Clear the input line |
| `Ctrl+D` | Exit |

## Batch input files

`--imo-file`, `--company-file`, and the shell's `/file` and `/company-file` read one item
per line:

```text
# Comments start with '#', either on their own line
9811000     # or after a value
9074729

9321483
```

Blank lines are ignored and duplicates are removed. On the command line, `-` reads the
list from standard input:

```bash
cut -d, -f1 vessels.csv | tail -n +2 | equasis vessel --imo-file - -o results.jsonl
```

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success |
| `1` | Error (network failure, unexpected Equasis response) |
| `2` | Invalid usage or input (for example a malformed IMO number) |
| `3` | Missing credentials or authentication failed |
| `4` | Vessel, company, or search results not found; ambiguous company name |
| `5` | Batch completed, but at least one item failed |
| `6` | An Equasis page did not have the expected layout; please report it |
| `130` | Interrupted |

## Environment variables

| Variable | Purpose |
| --- | --- |
| `EQUASIS_USERNAME`, `EQUASIS_PASSWORD` | Credentials |
| `EQUASIS_CACHE_DIR` | Cache location |
| `XDG_CONFIG_HOME`, `XDG_CACHE_HOME` | Base directories for credentials and cache |
| `NO_COLOR` | Disable colored messages |

## Shell completion

Completion scripts for zsh and bash are in [`completions/`](../completions).

```bash
# zsh: copy to a directory on $fpath, then restart the shell
cp completions/_equasis ~/.zsh/completions/

# bash: source from ~/.bashrc
source /path/to/equasis-cli/completions/equasis.bash
```
