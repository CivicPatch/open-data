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

Run these steps in order. Steps 1–3 are manual, per-state prep; 4 is an optional smoke test; 5 is the full run; 6–7 finish up. The example uses `va` (Virginia, FIPS 51).


1. **Register the state** in `scripts/state_configs.py`:
   ```python
   "va": {
       "fips": "51",
       "pull_from_census": ["places"],
       "scraper": va_scraper,
       "validation_sources": ["google"],
   }
   ```

2. **Write a scraper** in `scripts/scrapers/<state>.py`.

3. **Fetch Google Civic data** for the state from the team Drive folder:
   **https://drive.google.com/drive/u/0/folders/1A3qFX-UELHoNp27QyBt2edWQOkHPDbjY**
   Save it as `scripts/track_progress/google_data/{state}_all_raw.json` (e.g. `va_all_raw.json`).
   The preflight check in step 5 prints this same link and the exact path it expects if the file is missing.
   Note: you may not be able to access this file. Check with maintainers to get access.

4. **Dry-run the scraper** (recommended). Smoke-tests against a handful of jurisdictions to catch a wrong `rows_to_skip`, broken infobox parsing, or other scraper bugs — without waiting for hundreds of Wikipedia fetches. `setup_local.py` builds the local boundary map and, for every locality, **spatially joins the locality's centroid into the county polygons** (`maps/local.py:_add_county_ocdids`, an `sjoin … predicate="within"` in EPSG:5070) to tag it with `county_ocdids`. That join needs two artifacts from the earlier steps — `counties.geojson` (county geometry) and `data_source/<state>/counties/jurisdictions.yml` (county GEOID → OCD-ID) — and raises `FileNotFoundError` if they're missing. So generate state + county data first:
   ```bash
   # a. State + county boundaries (no scraper involved; safe to run as-is)
   uv run python scripts/setup_states.py <state ex: va>
   uv run python scripts/setup_counties.py <state ex: va>

   # b. Dry-run the scraper against just a few jurisdictions
   uv run python scripts/setup_local.py <state ex: nc> --limit 10
   ```
   `--limit` caps the number of Wikipedia infobox fetches (Census ACS still pulls every jurisdiction). After the run, inspect `data_source/va/local/jurisdictions.yml` and skim the warnings. Check that the properties look OK, and that we have at least a few url: <>
   fields that are populated (maximum of 10 will ever be filled out, because of the fetch limit)

   At this point, if everything looks good, go ahead and create a new pull request and contact a maintainer to get it looked at.

### Continued: Maintainers only

5. **Run the full setup:**
   ```bash
   mise run setup-state -- --state <state ex: va>
   ```
   This runs, in order:
   - State boundary + jurisdiction data (Census TIGER + state YAML)
   - County boundaries + jurisdiction data (Census TIGER + county YAML)
   - Local jurisdiction data (Census ACS + scraper + validation sources) — this step also computes `county_ocdids` per locality, via the centroid/county spatial join described in step 4
   - Uploads GeoJSONs to R2
   - Generates **this state's** per-state PMTile (`va.pmtiles`) and uploads it to R2 — it does **not** rebuild the national `states.pmtiles` (that's step 7)

6. **Validate jurisdiction OCD-IDs** (see [Validating jurisdiction OCD-IDs](#validating-jurisdiction-ocd-ids) below). `setup_local.py` builds OCD-IDs from Census names by lowercasing and swapping spaces for underscores; names with apostrophes, diacritics, slashes, or no LSAD suffix leak through as invalid IDs. Run the checker against the freshly generated file and fix anything it flags before pushing:
   ```bash
   uv run python scripts/fix_jurisdiction_ocdids.py --state <state ex: va>
   ```

7. **Rebuild the national states overview** (required — step 5 only builds the new state's own PMTile, not the national `states.pmtiles`; this no-arg run also purges the Cloudflare CDN cache):
   ```bash
   mise run generate-pmtiles
   ```

8. **Push** the open-data changes, then trigger OD sync on civicpatch.org:
   ```
   POST /admin/od_sync
   ```

---

## Validating jurisdiction OCD-IDs

Run this any time a state's `data_source/<state>/local/jurisdictions.yml` has been (re)generated — it catches OCD-IDs that the generator produced with illegal characters (apostrophes, diacritics, `/`) or an empty `place:` segment.

```bash
# Report problems for every state, change nothing:
uv run python scripts/fix_jurisdiction_ocdids.py --dry-run

# Interactively fix one state ([a]ccept / [e]dit / [s]kip per problem):
uv run python scripts/fix_jurisdiction_ocdids.py --state va

# Auto-accept every suggestion (skips any that would collide with an existing ID):
uv run python scripts/fix_jurisdiction_ocdids.py --state va --yes
```

For each invalid ID it prints the state, `file:line`, the specific problem(s), and a suggested canonical ID, and warns if a suggestion would collide with an existing or another suggested ID. Accepting a fix rewrites `jurisdictions.yml` and migrates any `data/<state>/local/*.yml` officials file that referenced the old ID. Structural validation is delegated to `shared`'s `parse_jurisdiction_ocdid`; the charset/empty checks layer on top.

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

### Cloudflare cache purge

`generate-pmtiles` automatically purges the Cloudflare edge cache for `cdn.civicpatch.org` after upload, so the new PMTiles are visible immediately. This requires two env vars:

- `CLOUDFLARE_PMTILES_BUST` — Cloudflare API token with `Zone.Cache Purge` permission, scoped to `civicpatch.org`
- `CLOUDFLARE_ZONE_ID` — the `civicpatch.org` zone ID (Cloudflare dashboard → zone Overview → API sidebar)

If either is unset (local dev), the script skips the purge with a log message and exits successfully.

The purge uses `{"hosts":["cdn.civicpatch.org"]}` rather than per-file URLs because Cloudflare keys cache entries by the `Origin` request header (R2 emits `Vary: Origin`), so per-URL purges leak stale variants. Hostname purge clears all variants in one call.

---

## Task Reference

| Task | When to run |
|------|-------------|
| `mise run setup-state -- --state {code}` | Adding a new state |
| `uv run python scripts/fix_jurisdiction_ocdids.py [--state {code}]` | After (re)generating `jurisdictions.yml` — validate/fix OCD-IDs |
| `mise run setup-maps [-- --state {code}]` | Census boundaries changed |
| `mise run generate-pmtiles [-- --state {code}]` | Jurisdiction names/data changed |

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
