# Output formats and schema

equasis-cli writes four formats. `table` is for reading in a terminal and may change
between releases. `json`, `jsonl`, and `csv` are for programs, and changes to them follow
the rules below.

- [Conventions](#conventions)
- [JSON](#json)
- [JSON Lines](#json-lines)
- [CSV](#csv)
- [Vessel fields](#vessel-fields)
- [Indicators](#indicators)
- [Search fields](#search-fields)
- [Fleet fields](#fleet-fields)
- [Stability](#stability)

## Conventions

- Dates are ISO 8601 (`2026-09-15`). Timestamps are UTC (`2026-09-16T15:08:00Z`).
- Tonnages, years, and counts are integers.
- Values Equasis does not show are `null` in JSON and empty in CSV.
- Text is exactly as Equasis shows it, with whitespace normalized.
- Lists of history records are ordered newest first, as on Equasis.
- JSON and CSV files are UTF-8.

## JSON

Every JSON document has the same envelope:

| Field | Description |
| --- | --- |
| `schema_version` | Version of this layout (currently `1`) |
| `type` | `vessel`, `search`, `fleet`, `batch_vessels`, or `batch_fleets` |
| `retrieved_at` | When the Equasis pages were fetched. This is earlier than now if they came from the cache. |
| `source` | `https://www.equasis.org` |

The payload key depends on the type:

| `type` | Payload |
| --- | --- |
| `vessel` | `vessel` ([vessel fields](#vessel-fields)) and `indicators` ([indicators](#indicators)) |
| `search` | `search` ([search fields](#search-fields)) |
| `fleet` | `fleet` ([fleet fields](#fleet-fields)) |
| `batch_vessels`, `batch_fleets` | `summary` and `results` (see below) |

Example, with lists shortened to one entry:

```json
{
  "schema_version": 1,
  "type": "vessel",
  "retrieved_at": "2026-09-16T15:08:00Z",
  "source": "https://www.equasis.org",
  "vessel": {
    "imo": "9811000",
    "name": "EVER GIVEN",
    "flag": "Panama",
    "flag_code": "PAN",
    "call_sign": "H3RC",
    "mmsi": "353136000",
    "gross_tonnage": 219079,
    "deadweight": 199489,
    "ship_type": "Container Ship",
    "year_built": 2018,
    "status": "In Service/Commission",
    "status_since": "2021-11-14",
    "particulars_updated": "2026-09-15",
    "flag_performance": {
      "paris_mou": "White",
      "tokyo_mou": "White",
      "uscg_targeted": true,
      "iacs_classed": true,
      "detention_rate_36_months": 0.0
    },
    "management": [
      {
        "company_id": "1135348",
        "name": "BERNHARD SCHULTE-HKG LP",
        "role": "Ship manager/Commercial manager",
        "address": "Room 2602, K Wah Centre, 191, Java Road, North Point, Hong Kong, China.",
        "since": "2021-03-01"
      }
    ],
    "class_status": [
      {"society": "American Bureau of Shipping (IACS)", "status": "Delivered", "since": "2018-10-25", "reason": null}
    ],
    "class_surveys": [
      {"society": "American Bureau of Shipping (IACS)", "last_renewal": "2023-07-12", "next_renewal": "2028-09-24"}
    ],
    "safety_certificates": [
      {
        "society": "American Bureau of Shipping (IACS)",
        "survey_date": "2023-12-04",
        "expiry_date": "2029-01-31",
        "status_change_date": "2018-09-25",
        "status": "Delivered",
        "reason": null,
        "convention": "Convention"
      }
    ],
    "pandi": [{"name": "UK P&I Club", "inception": "2018-09-25"}],
    "sightings": [{"period": "September 2026", "areas": ["West Europe"], "source": "MarineTraffic"}],
    "inspections": [
      {
        "authority": "Greece",
        "port": "Piraeus",
        "date": "2026-04-29",
        "detained": false,
        "reports": [
          {
            "psc_organisation": "Paris MoU",
            "inspection_type": "Initial inspection",
            "duration_days": null,
            "deficiencies": null,
            "inspection_id": "6406427"
          }
        ],
        "deficiencies": null
      }
    ],
    "human_element_deficiencies": [],
    "name_history": [{"name": "EVER GIVEN", "since": "2018-09-01", "until": null, "source": "IHS Maritime"}],
    "flag_history": [{"flag": "Panama", "since": "2018-09-01", "until": null, "source": "IHS Maritime"}],
    "class_history": [
      {"society": "American Bureau of Shipping (IACS)", "survey_date": "2023-07-12", "source": "American Bureau of Shipping"}
    ],
    "company_history": [
      {
        "company": "BERNHARD SCHULTE-HKG LP",
        "role": "Ship manager/Commercial manager",
        "since": "2021-03-01",
        "until": null,
        "source": "IHS Maritime"
      }
    ],
    "warnings": [],
    "retrieved_at": "2026-09-16T15:08:00Z"
  },
  "indicators": {
    "reference_date": "2026-09-16",
    "age_years": 8,
    "name_changes_12_months": 0,
    "name_changes_36_months": 0,
    "flag_changes_12_months": 0,
    "flag_changes_36_months": 0,
    "management_changes_36_months": 0,
    "inspections_36_months": 6,
    "detentions_36_months": 0,
    "deficiencies_36_months": 19,
    "last_inspection": "2026-04-29",
    "last_detention": null,
    "flag_on_paris_mou_grey_or_black_list": false,
    "flag_on_tokyo_mou_grey_or_black_list": false,
    "uscg_targeted_flag": true,
    "iacs_classed": true,
    "class_withdrawn_or_suspended_36_months": [],
    "has_pandi_insurance": true,
    "mmsi_country": "Panama",
    "mmsi_matches_flag": true,
    "observations": ["Flag is targeted by the US Coast Guard"]
  }
}
```

### Batch documents

| Field | Description |
| --- | --- |
| `summary.total` | Number of inputs |
| `summary.succeeded`, `summary.failed` | Counts by outcome |
| `summary.started_at` | When the batch started |
| `results[]` | One record per input, in input order |

Each record in `results` has:

| Field | Description |
| --- | --- |
| `query` | The input as given (IMO number, company name, or company number) |
| `status` | `ok`, `not_found`, `ambiguous` (fleets only), or `error` |
| `error` | Explanation when `status` is not `ok` |
| `warnings` | Non-fatal problems, such as a failed IMO check digit |
| `elapsed_seconds` | Time spent on this item |
| `vessel` or `fleet` | The result, or `null` |
| `indicators` | Vessel batches only: [indicators](#indicators) for the vessel, or `null` |

## JSON Lines

JSON Lines output has one JSON object per line:

| Result | Lines |
| --- | --- |
| Vessel | One line containing the full JSON document |
| Search | One line per result, with `"kind": "ship"` or `"kind": "company"` added |
| Fleet | One line per vessel, with `company_id` and `company_name` added |
| Batch | One line per input with the fields of a batch record, written as soon as that item completes |

Because batch lines are streamed, a partially completed batch still leaves valid output.

## CSV

CSV files have a header row, quote values where needed, and use `true` and `false` for
booleans. Multiple values in one cell are separated by `; `.

**Vessels**: one row per vessel:

| Column | Description |
| --- | --- |
| `imo`, `name`, `flag`, `flag_code`, `call_sign`, `mmsi` | Identity |
| `gross_tonnage`, `deadweight`, `ship_type`, `year_built` | Particulars |
| `status`, `status_since`, `particulars_updated` | Status |
| `paris_mou`, `tokyo_mou`, `uscg_targeted` | Flag performance |
| `registered_owner`, `ship_manager`, `ism_manager` | Current companies in these roles |
| `class_societies` | Classification societies, excluding those with status `Withdrawn` |
| `pandi` | P&I insurers |
| `inspections`, `detentions`, `last_inspection` | All recorded PSC inspections |
| `name_changes`, `flag_changes` | All recorded changes |
| `age_years`, `name_changes_36_months`, `flag_changes_36_months`, `management_changes_36_months`, `inspections_36_months`, `detentions_36_months`, `mmsi_matches_flag`, `observations` | [Indicators](#indicators) |
| `warnings` | Parts of the profile that could not be read |

**Vessel batches** have the same columns, preceded by `query`, `lookup_status`, and
`error`.

**Search results**: `kind` (`ship` or `company`), `imo`, `company_id`, `name`,
`gross_tonnage`, `ship_type`, `year_built`, `flag`, `address`.

**Fleets**: one row per vessel: `company_id`, `company_name`, `imo`, `name`,
`gross_tonnage`, `ship_type`, `year_built`, `flag`, `class_societies`,
`detentions_as_ism_manager_3y`, `detentions_all_companies_3y`, `roles`.

**Fleet batches** have the fleet columns preceded by `query`, `lookup_status`, and
`error`, with one row per vessel. A failed company has a single row.

## Vessel fields

| Field | Description |
| --- | --- |
| `imo`, `name` | IMO number and current name |
| `flag`, `flag_code` | Flag state name and ISO 3166-1 alpha-3 code |
| `call_sign`, `mmsi` | Radio identifiers |
| `gross_tonnage`, `deadweight` | Tonnages |
| `ship_type`, `year_built` | Type and year of build |
| `status`, `status_since` | For example `In Service/Commission`, `Broken Up` |
| `particulars_updated` | When Equasis last updated the particulars |
| `flag_performance` | `paris_mou` and `tokyo_mou` list colour (`White`, `Grey`, `Black`), `uscg_targeted`, `iacs_classed`, `detention_rate_36_months` (percent) |
| `management[]` | Current companies: `company_id`, `name`, `role`, `address`, `since` |
| `class_status[]` | Classification status: `society`, `status`, `since`, `reason` |
| `class_surveys[]` | Renewal surveys: `society`, `last_renewal`, `next_renewal` |
| `safety_certificates[]` | `society`, `survey_date`, `expiry_date`, `status_change_date`, `status`, `reason`, `convention` |
| `pandi[]` | P&I insurers: `name`, `inception` |
| `sightings[]` | `period` (month), `areas`, `source` |
| `inspections[]` | PSC inspections: `authority` (port state), `port`, `date`, `detained`, `deficiencies`, `reports[]` |
| `inspections[].reports[]` | One entry per PSC regime the inspection was reported to: `psc_organisation`, `inspection_type`, `duration_days`, `deficiencies`, `inspection_id` |
| `human_element_deficiencies[]` | `psc_organisation`, `authority`, `port`, `inspection_type`, `date`, `deficiencies` |
| `name_history[]`, `flag_history[]` | `name` or `flag`, `since`, `until`, `source` |
| `class_history[]` | Class renewal surveys: `society`, `survey_date`, `source` |
| `company_history[]` | `company`, `role`, `since`, `until`, `source` |
| `warnings[]` | Parts of the profile that could not be read |
| `retrieved_at` | When the pages were fetched |

Notes:

- An inspection reported to more than one PSC regime appears once, with one entry per
  regime in `reports`. `inspections[].deficiencies` is the highest count any regime
  reported.
- A deficiency count of `null` means Equasis showed no number, which usually means none
  were recorded.
- `until` is not published by Equasis. It is derived from the `since` date of the next
  newer record (for companies, the next newer record with the same role).
- Dates Equasis gives only to the month (`during 09/2024`) use the first day of that month.

## Indicators

Indicators are computed from the vessel profile relative to `reference_date` (the
retrieval date). They are facts, not a risk score.

| Field | Description |
| --- | --- |
| `age_years` | Years since the year of build |
| `name_changes_12_months`, `name_changes_36_months` | Renames that took effect in the window |
| `flag_changes_12_months`, `flag_changes_36_months` | Flag changes that took effect in the window |
| `management_changes_36_months` | Changes of registered owner, ship manager, or ISM manager |
| `inspections_36_months`, `detentions_36_months`, `deficiencies_36_months` | PSC activity in the window |
| `last_inspection`, `last_detention` | Most recent dates on record |
| `flag_on_paris_mou_grey_or_black_list`, `flag_on_tokyo_mou_grey_or_black_list` | Flag performance list membership |
| `uscg_targeted_flag`, `iacs_classed` | As reported by Equasis |
| `class_withdrawn_or_suspended_36_months` | `"Society: Status"` entries whose status changed in the window |
| `has_pandi_insurance` | Whether any P&I insurer is recorded |
| `mmsi_country`, `mmsi_matches_flag` | Country allocated the MMSI's Maritime Identification Digits, and whether it is the flag state. `null` when either value is unavailable. |
| `observations` | Plain-language sentences describing the notable indicators |

## Search fields

| Field | Description |
| --- | --- |
| `query` | The search text, or the identifiers searched for |
| `ships[]` | `imo`, `name`, `gross_tonnage`, `ship_type`, `year_built`, `flag` |
| `companies[]` | `company_id`, `name`, `address` |
| `total_ships` | Total ship matches reported by Equasis; can exceed `len(ships)` when results were limited by `--max-pages` |
| `retrieved_at` | When the pages were fetched |

## Fleet fields

| Field | Description |
| --- | --- |
| `company` | `company_id`, `name`, `address`, `status`, `last_update` |
| `vessels[]` | `imo`, `name`, `gross_tonnage`, `ship_type`, `year_built`, `flag`, `class_societies`, `detentions_as_ism_manager_3y`, `detentions_all_companies_3y`, `roles[]` (`role`, `since`) |
| `total_vessels` | Total reported by Equasis; can exceed `len(vessels)` when limited by `--max-pages` |
| `retrieved_at` | When the pages were fetched |

## Stability

Within a `schema_version`:

- Fields and CSV columns are never removed or renamed, and their types do not change.
- New fields and CSV columns may be added. Read CSV files by column name, not position.

Incompatible changes increase `schema_version` and are listed in the
[changelog](../CHANGELOG.md).
