# Development Guide

## One-time environment setup

The Census Data API requires an API key as of early 2026. Get one (free, instant) and add it to `.env`:

```bash
# Sign up: https://api.census.gov/data/key_signup.html
# (Census emails an activation link — click it before using the key)
echo 'CENSUS_API_KEY=your-40-char-key-here' >> .env
```

`mise` auto-loads `.env`, so any script run via `mise exec` or `mise run` will pick it up. Scripts will exit with a clear message if the key is missing.

---

## Adding a New State

### Prerequisites (manual, per-state)

1. Add to `scripts/state_configs.py`:
   ```python
   "va": {
       "fips": "51",
       "pull_from_census": ["places"],
       "scraper": va_scraper,
       "validation_sources": ["google"],
   }
   ```
2. Write a scraper in `scripts/scrapers/va.py`
3. Fetch Google Civic data for the state (the preflight check will tell you exactly what's missing)

### Dry run (recommended before full setup)

Smoke-test the scraper against a handful of jurisdictions first. Catches wrong `rows_to_skip`, broken infobox parsing, and other scraper bugs without waiting for hundreds of Wikipedia fetches.

`setup_local.py` needs `counties.geojson` to exist (it computes `county_ocdids` against county boundaries), so generate state + county data first:

```bash
# 1. State + county boundaries (no scraper involved; safe to run as-is)
uv run python scripts/setup_states.py va
uv run python scripts/setup_counties.py va

# 2. Dry-run the scraper against just a few jurisdictions
uv run python scripts/setup_local.py va --limit 10
```

`--limit` caps the number of Wikipedia infobox fetches (Census ACS still pulls every jurisdiction). After the run, inspect `data/va/local/` and skim the warnings — if more than a few entries log `no_wiki_match`, the scraper's `table_index` / `rows_to_skip` / `entry_column` are probably off. Cached infobox results live in `scripts/scrapers/cache/va_wikipedia.json` so reruns are cheap.

### Run setup

```bash
mise run setup-state -- --state va
```

This runs all steps in order:
1. State boundary + jurisdiction data (Census TIGER + state YAML)
2. County boundaries + jurisdiction data (Census TIGER + county YAML)
3. Local jurisdiction data (Census ACS + scraper + validation sources)
4. Uploads GeoJSONs to R2 (also computes `county_ocdids` per locality)
5. Generates PMTile and uploads to R2

### Finish up

```bash
# Rebuild national states overview (includes the new state)
mise run generate-pmtiles

# Push open-data changes, then trigger OD sync on civicpatch.org
POST /admin/od_sync
```

---

## Regenerating PMTiles

When a jurisdiction name changes or a new jurisdiction is added:

```bash
# Regenerate one state (fast)
mise run generate-pmtiles -- --state co

# Regenerate all states + national overview
mise run generate-pmtiles
```

When Census TIGER boundaries change (annually) or you need to refresh geographic data:

```bash
# Refresh maps for one state, then regenerate tiles
mise run setup-maps -- --state co
mise run generate-pmtiles -- --state co

# Refresh all states
mise run setup-maps
mise run generate-pmtiles
```

---

## Task Reference

| Task | When to run |
|------|-------------|
| `mise run setup-state -- --state {code}` | Adding a new state |
| `mise run setup-maps [-- --state {code}]` | Census boundaries changed |
| `mise run generate-pmtiles [-- --state {code}]` | Jurisdiction names/data changed |
| `mise run readme` | Refresh coverage report in README.md |

---

## R2 Structure

```
maps/
  states.pmtiles          ← national state boundaries (all active states)
  co.pmtiles              ← per-state PMTile (layers: states, counties, local)
  mi.pmtiles
  ...

  co/                     ← source GeoJSONs (enriched, uploaded by setup-maps)
    states.geojson
    counties.geojson
    local.geojson
  mi/
    ...
```
