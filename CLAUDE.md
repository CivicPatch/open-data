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
    get_jurisdiction_folder.py
    local/
      pull_request/             ← scripts run locally to generate PR content
      post_merge/               ← scripts run locally after a PR is merged
  jurisdictions/                ← the pipeline that builds data_source/**/jurisdictions.yml
    config.py                   ← state registry: fips, name, census sources, scraper
    headers.py                  ← generates each jurisdictions.yml header (fields + provenance)
    yaml_io.py                  ← shared comment-preserving YAML load/dump
    states.py                   ← fetch state government jurisdiction for a state
    counties.py                 ← fetch + enrich county jurisdictions for a state
    local.py                    ← fetch + enrich municipality jurisdictions for a state
    run.py                      ← orchestrator: state → counties → local → maps → tiles
    scrapers/                   ← per-state Wikipedia scrapers + wikipedia_utils
    maps/                       ← geo utilities (local.py, county.py, state.py) + tiles
  ocdids/                       ← OCD-ID parsing (parse.py) and repair (fix.py)
  track_progress/               ← data quality dashboards and gap analysis
  one_off/                      ← completed migrations, kept for reference
  paths.py                      ← PROJECT_ROOT anchor; never recompute it from __file__
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
