# Development guide

## Setup

```bash
git clone https://github.com/rhinonix/equasis-cli.git
cd equasis-cli
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
```

## Checks

```bash
ruff check .            # lint
ruff format .           # format
mypy                    # strict type checking of src/
pytest                  # offline test suite
pytest --cov            # with coverage
```

CI runs the same checks on Python 3.10 to 3.14 on Linux, and on 3.10 and 3.14 on macOS and
Windows. It also builds the package and smoke-tests the wheel.

### Live tests

`tests/test_live.py` makes a handful of real requests to equasis.org to detect website
changes. The tests are skipped unless enabled:

```bash
EQUASIS_LIVE_TESTS=1 pytest tests/test_live.py -v
```

They use your configured credentials. The "Live canary" workflow runs them weekly when the
repository secrets `EQUASIS_USERNAME` and `EQUASIS_PASSWORD` are set.

## Project layout

```text
src/equasis_cli/
  cli.py              argument parsing, exit codes, command execution
  tui/app.py          interactive shell (prompt_toolkit layout and key bindings)
  tui/commands.py     interactive command parsing and execution, no terminal code
  service.py          batch processing and company resolution shared by both interfaces
  client.py           EquasisClient: login, session renewal, vessels, search, fleets
  transport.py        HTTP session, request pacing, retries, response capture
  cache.py            on-disk page cache
  parsing/            one parser per Equasis page type
    html.py           table and panel helpers (header lookup, rowspan handling)
    page.py           classifies login, not-found, and error pages
    ship.py           Ship Info, Inspections, Ship History
    search.py         search results
    fleet.py          Fleet info
  enrichment/         indicators and country and MID reference data
  models.py           dataclasses for all results
  output.py           table, JSON, JSON Lines, and CSV rendering; file writing
  credentials.py      credential resolution and storage
  validation.py       IMO, MMSI, and company number validation; list parsing
  exceptions.py       exception hierarchy
  console.py          stderr messages
tests/
  fixtures/           anonymized pages recorded from equasis.org
  tools/make_fixture.py
```

Requests flow through the layers in one direction: `cli.py` or `tui/commands.py` calls
`service.py` or `client.py`, which uses `transport.py` and `cache.py` to fetch pages and
`parsing/` to turn them into `models.py` objects. `output.py` renders the objects.

### Parsing principles

- Find panels by their visible title and table columns by their header text, never by
  position. Equasis reorders panels between pages.
- Ignore rows marked `hidden-lg hidden-md`, which duplicate content for small screens.
- Expand `rowspan` cells. Equasis nests the spanned row inside the previous `<tr>`, so
  rows are collected recursively.
- Raise `LayoutChangedError` when an expected heading or column is missing, so users get a
  clear message instead of silently wrong data.

## Test fixtures

Parser tests run against real pages stored in `tests/fixtures/`. To add or refresh one:

1. Capture the page: `equasis vessel 9811000 --save-html /tmp/pages --refresh`. Files are
   numbered in request order, for example `003-get-restricted-ShipInfo.html`.
2. Anonymize and minimize it:

   ```bash
   python tests/tools/make_fixture.py /tmp/pages/003-get-restricted-ShipInfo.html \
       tests/fixtures/ship_info_9811000.html
   ```

3. Check that parsing the fixture gives the same result as parsing the original page.
4. Run `pytest tests/test_parsing_pages.py`. It fails if any fixture still contains an
   account name.
5. Update `tests/fixtures/README.md`.

Never commit pages that have not been through `make_fixture.py`.

## Releasing

See [RELEASING.md](../RELEASING.md).
