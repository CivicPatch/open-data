# Development Guide

## Setup

The Census Data API requires a key. Free and instant — [sign up](https://api.census.gov/data/key_signup.html), click the activation link in the email, then:

```bash
echo 'CENSUS_API_KEY=your-40-char-key-here' >> .env
```

`mise` auto-loads `.env`. Scripts exit with a clear message if the key is missing.

---

## Adding a new state

Steps 1–4 are open to anyone; 5–8 are maintainers only. Examples use `va` (FIPS 51).

**1. Register it** in [scripts/jurisdictions/config.py](scripts/jurisdictions/config.py):

```python
"va": {
    "fips": "51",
    "name": "Virginia",                  # builds Wikipedia page titles
    "pull_from_census": ["places"],      # add "county_subdivisions" for MCD/town states
    "local_wiki": {},                    # {} = all defaults; see step 2
    "validation_sources": ["google"],
}
```

**2. Fit the municipality list page.** There is no per-state scraper. [scrapers/municipalities.py](scripts/jurisdictions/scrapers/municipalities.py) reads every state's `List_of_municipalities_in_<State>` page, and `local_wiki` records only where that state deviates from the common shape — one wikitable whose first column is the linked place name:

| key | default | set it when |
|---|---|---|
| `table_index` | `0` | the municipality table isn't the page's first wikitable |
| `rows_to_skip` | `1` | the header spans two rows (usually land area splitting into sq mi / km²) |
| `entry_column` | `0` | the place name isn't the first column |
| `title` | `List_of_municipalities_in_Virginia` | that title is a disambiguation page (Georgia: the country vs the U.S. state) |
| `parser` | `"table"` | `"bullet_list"` — the page has no wikitable, just per-letter bullets (North Carolina) |

Open the page and count; these coordinates are declared rather than detected because municipality pages carry no FIPS column to identify the right table by. Unknown keys raise rather than being silently ignored.

Counties need nothing here — [scrapers/counties.py](scripts/jurisdictions/scrapers/counties.py) is generic and locates the county table by shape.

**3. Fetch Google Civic data** from the [team Drive folder](https://drive.google.com/drive/u/0/folders/1A3qFX-UELHoNp27QyBt2edWQOkHPDbjY) to `scripts/track_progress/google_data/va_all_raw.json`. Ask a maintainer if you lack access; step 5's preflight prints the expected path if it's missing.

**4. Smoke-test.** Run the three levels in order. This repo no longer touches geometry at all: which counties contain a place is worked out by civicpatch.org's boundary overlay and stored there, so nothing here needs shapefiles or a prior county run.

```bash
uv run python scripts/jurisdictions/states.py va
uv run python scripts/jurisdictions/counties.py va
uv run python scripts/jurisdictions/local.py va --limit 10
```

Then check `data_source/va/local/jurisdictions.yml`. **A `--limit N` run leaves most entries flagged `no_wiki_match` — that is the budget, not a fault.** Municipality GEOIDs come from the infobox, so rows past the budget are dropped before matching and every one of them gets flagged; expect roughly `total − N`. What you are checking is that the first N entries came back with `url:` and `wiki_url:` populated.

A wrong `table_index` or `entry_column` looks different: *every* entry unmatched including the first N, or `No Wikipedia URL found for:` warnings during the run. Counties are immune to the artifact — their GEOID comes from the table, so a high `no_wiki_match` count there is always a real failure. To confirm the fit across a whole state, re-run without `--limit`.

`--limit` caps Wikipedia **infobox fetches**, not records; Census ACS still pulls every jurisdiction. Fetches are cached per state under `scripts/jurisdictions/scrapers/cache/`, so re-runs after a fix are cheap. `counties.py` takes the same `--limit`, plus `--skip-wiki` to pull Census data only.

Open a PR here and ask a maintainer to review.

### Maintainers only

**5. Full run:**

```bash
mise run setup-state -- --state va
```

State → counties → local (ACS + scraper + validation).

**6. Validate OCD-IDs** — generated from Census names, so apostrophes, diacritics, slashes and missing LSAD suffixes leak through:

```bash
uv run python scripts/ocdids/fix.py --state va
```

**7. Push**, then trigger OD sync on civicpatch.org: `POST /admin/od_sync`.

**8. Generate the state's maps.** Everything geo moved to civicpatch.org — trigger
`GenerateMapsWorkflow` for `va` there (Temporal UI / a manual script; there is no admin-page
control). It is not optional: besides the pmtiles it is what fills `meta_parent_ocdids`, so
until it runs the state's municipalities have no containing county and the coverage map cannot
count them. Chains straight into rebuilding the national `states.pmtiles` overview, so there is
no separate "rebuild the overview" step.

---

## Reference

### OCD-ID validation

Run after any `jurisdictions.yml` is regenerated.

```bash
uv run python scripts/ocdids/fix.py --dry-run          # report every state, change nothing
uv run python scripts/ocdids/fix.py --state va         # fix one state, [a]ccept/[e]dit/[s]kip
uv run python scripts/ocdids/fix.py --state va --yes   # auto-accept, skipping collisions
```

Prints state, `file:line`, the problem, and a suggested canonical ID, warning on collisions. Accepting rewrites `jurisdictions.yml` and migrates any `data/<state>/local/*.yml` that referenced the old ID. Structural validation comes from `shared`'s `parse_jurisdiction_ocdid`; charset and empty-segment checks layer on top.

### Maps and boundaries

All of it lives in civicpatch.org as a manually-triggered Temporal workflow
(`GenerateMapsWorkflow`). It fetches Census TIGER geometry itself, builds and uploads
`{state}.pmtiles` in one pass, and runs the containing-county overlay into the
`meta_parent_ocdids` column. Nothing in this repo downloads shapefiles, writes GeoJSON or
records ancestry any more.

### Tasks

| Task | When |
|---|---|
| `mise run setup-state -- --state {code}` | adding a state |
| `uv run python scripts/ocdids/fix.py [--state {code}]` | after regenerating `jurisdictions.yml` |

### R2 layout

```
maps/
  states.pmtiles     ← national state boundaries, written by civicpatch.org
  co.pmtiles         ← per-state (layers: states, counties, local), written by civicpatch.org
```
