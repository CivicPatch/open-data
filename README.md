# open-data

Data repo behind [CivicPatch](https://civicpatch.org). Contains YAML files for municipal government officials, organized by state and jurisdiction. Pull requests to this repo are the primary output of CivicPatch pipelines.

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
  scrapers/                     ← one-off scrapers for specific states/sources
  track_progress/               ← data quality comparison against external sources
  maps/                         ← geo utilities (local.py, county.py)
```

## Data format

Each `data/<state>/local/<place_name>.yml` is a YAML list of `Official` records validated against [`schemas.py`](schemas.py). Key fields:

- `name`, `other_names` — canonical name and aliases
- `office.name`, `office.division_ocdid` — role and OCD-ID for the division
- `phones`, `emails`, `urls` — contact info
- `start_date`, `end_date` — ISO 8601: `YYYY`, `YYYY-MM`, or `YYYY-MM-DD`
- `updated_at` — full ISO 8601 datetime with timezone offset
- `source_urls` — one or more URLs where the data was found
- `jurisdiction_ocdid` — OCD-ID for the jurisdiction

Every PR is validated against this schema before merge — see `scripts/github_actions/validate_jurisdiction.py`.

## Contributing / development

See [DEVELOPMENT.md](DEVELOPMENT.md) for environment setup and the workflow for adding a new state, and [CLAUDE.md](CLAUDE.md) for repo conventions used by AI coding assistants.

## License

See [LICENSE](LICENSE).
