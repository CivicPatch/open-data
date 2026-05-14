# open-data — Project Context

See root `AI_CONTEXT.md` for shared coding standards (via civicpatch-tools).

## What this is

The canonical data repository for CivicPatch. Contains YAML files for municipal government officials, organised by state and jurisdiction. Pull requests to this repo are the primary output of the `civicpatch` scraping pipeline.

## Project layout

```
data/
  <state>/
    local/
      <place_name>.yml    ← one file per jurisdiction; list of Official records
data_source/
  <state>/
    local/
      jurisdictions.yml         ← municipalities: list of known jurisdictions for the state
      jurisdictions_metadata.yml
      <place_name>/
        pipeline_run_context.json   ← pipeline config/state for the jurisdiction
    state/
      jurisdictions.yml         ← state government (one entry)
    counties/
      jurisdictions.yml         ← county governments for the state
schemas.py                      ← Pydantic models: Jurisdiction, Office, Official
scripts/
  github_actions/               ← run in CI on PRs and post-merge
    validate_jurisdiction.py    ← validates YAML against schemas.py
    update_jurisdiction_metadata.py
    get_jurisdiction_folder.py
    pull_request_body_markdown.py
    local/
      pull_request/             ← scripts run locally to generate PR content
      post_merge/               ← scripts run locally after a PR is merged
  scrapers/                     ← one-off scrapers for specific states/sources
  track_progress/               ← data quality dashboards and gap analysis
  maps/                         ← geo utilities (local.py, county.py)
  setup_local.py                ← fetch + enrich municipality jurisdictions for a state
  setup_counties.py             ← fetch county jurisdictions + map for a state
  setup_states.py               ← fetch state government jurisdiction + map for a state
  utils.py
```

## Data format

Each `data/<state>/local/<place_name>.yml` is a YAML list of `Official` records validated against `schemas.py`. Key fields:

- `name`, `other_names` — canonical name and aliases
- `office.name`, `office.division_ocdid` — role and OCD-ID for the division
- `phones`, `emails`, `urls` — contact info (format-validated by the schema)
- `start_date`, `end_date` — ISO 8601: `YYYY`, `YYYY-MM`, or `YYYY-MM-DD`
- `updated_at` — full ISO 8601 datetime with timezone offset
- `source_urls` — one or more URLs where the data was found
- `jurisdiction_ocdid` — OCD-ID for the jurisdiction

## Validation

- `schemas.py` is the source of truth for what a valid record looks like — all field validation lives there, not in scripts
- `scripts/github_actions/validate_jurisdiction.py` runs on every PR; do not bypass it
- All phone numbers must match `(XXX) XXX-XXXX` or `(XXX) XXX-XXXX ext. XXXX`

## Environment

- `shared` is imported directly from the civicpatch-tools repo (pinned to `main`)
- Scripts that call external services read credentials from env vars — never hardcode

## Before writing code

1. Read `schemas.py` before adding or changing any field — validation is centralised there
2. Check an existing YAML file in `data/` to understand the expected structure before generating new records
3. Read existing scripts in `scripts/github_actions/` before adding new CI steps — follow the established pattern
