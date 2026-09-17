# Contributing

Thank you for helping improve equasis-cli. Bug reports, parser fixes for Equasis website
changes, and documentation improvements are especially welcome.

## Reporting problems

- **Equasis changed its website** (exit code 6, or missing or wrong data): use the
  "Equasis page changed" issue template. Re-run the command with `--save-html DIR` and
  attach the relevant page after removing your name from it. Your name appears in the
  "Welcome" section near the top of the page.
- **Other bugs**: use the bug report template and include `equasis --version`, your
  operating system, the exact command, and the output with `--debug`.
- **Security issues**: do not open a public issue; see [SECURITY.md](SECURITY.md).

Never post your Equasis password, the contents of your credentials file, or unredacted
pages saved with `--save-html`.

## Development setup

```bash
git clone https://github.com/rhinonix/equasis-cli.git
cd equasis-cli
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
```

See [docs/development.md](docs/development.md) for the project layout, tests, and test
fixtures.

## Pull requests

1. Open an issue first for larger changes so the approach can be agreed.
2. Keep each pull request focused, and write commit messages that explain what changed
   and why.
3. Add or update tests. Parser changes need a fixture recorded from the real page (see
   [docs/development.md](docs/development.md#test-fixtures)).
4. Update the documentation and add an entry under "Unreleased" in
   [CHANGELOG.md](CHANGELOG.md) for user-visible changes.
5. Make sure the checks pass:

   ```bash
   ruff check .
   ruff format --check .
   mypy
   pytest
   ```

## Licensing of contributions

equasis-cli is licensed under the PolyForm Noncommercial License 1.0.0, and commercial
licenses are available separately (see [LICENSING.md](LICENSING.md)). So that the project
can continue to offer both, contributions are accepted under the
[Contributor License Agreement](CLA.md). You keep the copyright to your contribution; the
agreement allows it to be distributed under both licenses.

To agree, tick the "I agree to the Contributor License Agreement" box in the pull request
description. Pull requests can only be merged once the box is ticked.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By participating you
agree to uphold it.
