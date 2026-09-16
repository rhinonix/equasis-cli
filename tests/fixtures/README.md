# Test fixtures

Pages recorded from equasis.org on 2026-09-16 and processed with
`tests/tools/make_fixture.py`, which:

- removes scripts, styles, images (except flag images), select options, and comments
- replaces the logged-in account's display name with `Test User`
- collapses whitespace while keeping line breaks

Parsing a fixture gives the same result as parsing the original page; re-check
this whenever a fixture is regenerated.

| Fixture | Page |
| --- | --- |
| `ship_info_9811000.html`, `inspections_9811000.html`, `history_9811000.html` | EVER GIVEN: all Ship Info panels, including P&I and safety management certificates |
| `ship_info_9074729.html`, `inspections_9074729.html`, `history_9074729.html` | KAVITA: black-listed flag, withdrawn class, detentions, inspections reported to two PSC regimes, name and flag changes |
| `ship_not_found.html` | Error page for an IMO number that does not exist |
| `login_page.html` | Page returned for an expired session or rejected login |
| `home_logged_in.html` | Home page after a successful login |
| `search_torm_page1.html`, `search_torm_page2.html` | Name search with two pages of ship results and company results |
| `search_no_results.html` | Name search without matches |
| `search_by_mmsi.html` | Advanced search by MMSI |
| `fleet_torm.html` | Single-page fleet (94 vessels) |
| `fleet_msc_page1.html`, `fleet_msc_page2.html` | First two pages of a 443-vessel fleet, trimmed to 5 vessels each |
| `fleet_unknown_company.html` | Error page for a company number that does not exist |
