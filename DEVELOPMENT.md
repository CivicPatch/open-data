# Development Guide

## Adding a New State

### Prerequisites (manual, one-time)

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

### Run setup

```bash
mise run setup-state --state va
```

This runs all steps in order:
1. Downloads state + county boundaries from Census TIGER
2. Fetches local jurisdiction data (Census ACS + scraper + Google)
3. Computes `parent_ocdids` (which county each municipality belongs to)
4. Uploads GeoJSONs to R2
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
| `mise run setup-state --state {code}` | Adding a new state |
| `mise run setup-maps [--state {code}]` | Census boundaries changed |
| `mise run generate-pmtiles [--state {code}]` | Jurisdiction names/data changed |
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
