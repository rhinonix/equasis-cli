# Changelog

All notable changes to equasis-cli are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- After `clear` in the interactive shell, the first lines of new output were shown in
  banner colors.

### Changed

- The README screenshot shows the 3.0 interactive shell.
- Contributions are accepted under a Contributor License Agreement (CLA.md), agreed to
  with a checkbox in the pull request template.

## [3.0.0] - 2026-09-17

A rebuild focused on reliability, correct data, and scripting. Existing users should read
**Upgrading from 2.x** below.

### Fixed

- Interactive `batch` did nothing ([#16](https://github.com/rhinonix/equasis-cli/issues/16)).
- Interactive `/output file.json` and `/output file.csv` wrote table text instead of JSON
  or CSV ([#17](https://github.com/rhinonix/equasis-cli/issues/17)).
- Interactive `fleet` did nothing ([#18](https://github.com/rhinonix/equasis-cli/issues/18)).
- An expired Equasis session was reported as "No vessel found". The session is now renewed
  automatically.
- An inspection reported to two PSC regimes produced an extra, garbled inspection record.
- Every inspection was flagged as a detention in table output.
- Tables were read by column position, so values could land in the wrong fields.
  Columns are now matched by their headers.
- Permanent HTTP errors such as 404 were retried, and `Retry-After` was ignored.
- Status messages were printed into JSON and CSV output, and every failure exited with
  status 0.
- CSV output did not quote values containing commas and had no header for single vessels.
- `--output` and `--output-file` only worked before the command name.
- `--debug` had no effect, and `--continue-on-error` did nothing.
- Batch files with inline `#` comments sent the comment to Equasis as part of the IMO number.
- Interactive log messages appeared twice, and typographic quotes and parameters such as
  `/company-file` were not recognized.
- Search and fleet results beyond the first page were missing.
- The Comoros flag was reported with the code `XCM` instead of `COM`.

### Added

- Indicators: name, flag, and management changes; recent inspections, detentions, and
  deficiencies; grey or black listed flags; USCG targeting; class withdrawals and
  suspensions; P&I insurance; and whether the MMSI matches the flag state.
- New vessel data: safety management certificates, P&I insurance, class renewal surveys,
  classification history, human element deficiencies, and company roles with dates.
- Fleet data: class, detention counts, and the roles the company holds for each vessel.
- `search --imo`, `--mmsi`, and `--call-sign` for exact lookups, plus `--type`,
  `--max-pages`, and `--all-pages`.
- `fleet` accepts company numbers (`--company-id`), prompts when a name is ambiguous, and
  supports `--first-match`.
- JSON Lines output (`-f jsonl`), which streams batch results as they complete.
- A 24-hour page cache with `--no-cache`, `--refresh`, and `equasis cache [info|clear]`
  ([#2](https://github.com/rhinonix/equasis-cli/issues/2)).
- `--delay`, `--save-html`, `--quiet`, `--no-color`, `configure --test`, and `--version`.
- Documented exit codes for scripting.
- Batch input from standard input (`--imo-file -`) and IMO check-digit warnings.
- Interactive `help COMMAND`, `cache`, `/refresh`, `/pages`, and `/first`.
- A typed Python API (`EquasisClient`, models, and `compute_indicators`).
- Tests with recorded Equasis pages, continuous integration on Linux, macOS, and Windows,
  and a weekly live check against equasis.org.

### Changed

- Relicensed from CC BY-NC-SA 4.0 to the PolyForm Noncommercial License 1.0.0, with an
  additional permission for journalism and nonprofit research (see LICENSING.md).
- Python 3.10 or later is required.
- JSON output uses a versioned envelope (`schema_version`, `type`, `retrieved_at`), ISO 8601
  dates, and integer tonnages. The layout is documented in docs/output-schema.md.
- CSV output was redesigned: one row per vessel with key facts and indicators, and batch
  files use a `lookup_status` column.
- Batches continue after failures by default; use `--fail-fast` to stop.
- Credentials are written atomically with owner-only permissions. A warning is shown if
  the credentials file is readable by others.
- `-f/--format` is the name of the format option (`--output` still works) and
  `-o/--output-file` sets the output file.
- Progress messages, warnings, and errors are written to stderr.

### Removed

- The `.env` file references (credentials come from `configure --setup` or environment
  variables) and the unused `python-dotenv` and `lxml` dependencies.
- The unused `--batch` option.
- The startup banner before command output. `--no-banner` is still accepted and has no
  effect.

### Upgrading from 2.x

- Update scripts that read JSON: vessel fields are under `.vessel` (for example
  `.vessel.name` instead of `.basic_info.name`), and dates are ISO 8601.
- Update scripts that read CSV to use the new column names.
- Scripts that relied on exit status 0 for failures should check for the new codes.
- The Python API changed: use `EquasisClient.get_vessel`, `search`, `search_ships`, and
  `get_fleet`.

## [2.0.0] - 2025-10-01

### Added

- Full-screen interactive shell with command menus, loading indicators, and scroll mode.
- Company search and fleet retrieval by company number.

## [1.0.0] - 2025-09-27

### Added

- First stable release: vessel lookup across the Ship Info, Inspections, and Ship History
  pages, vessel search, fleets, batch processing, retries, and credential management.

[Unreleased]: https://github.com/rhinonix/equasis-cli/compare/v3.0.0...HEAD
[3.0.0]: https://github.com/rhinonix/equasis-cli/compare/v2.0.0...v3.0.0
[2.0.0]: https://github.com/rhinonix/equasis-cli/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/rhinonix/equasis-cli/releases/tag/v1.0.0
