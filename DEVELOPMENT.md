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
    "scraper": va_scraper,
    "validation_sources": ["google"],
}
```

**2. Write a municipality scraper** at `scripts/jurisdictions/scrapers/va.py`. Copy the closest existing one — most are ~15 lines of table coordinates. Counties need no scraper; [scrapers/counties.py](scripts/jurisdictions/scrapers/counties.py) is generic and locates the county table by shape.

**3. Fetch Google Civic data** from the [team Drive folder](https://drive.google.com/drive/u/0/folders/1A3qFX-UELHoNp27QyBt2edWQOkHPDbjY) to `scripts/track_progress/google_data/va_all_raw.json`. Ask a maintainer if you lack access; step 5's preflight prints the expected path if it's missing.

**4. Smoke-test.** State and county data must exist first — the local run spatially joins each locality's centroid into the county polygons, and raises `FileNotFoundError` without `counties.geojson` and the county `jurisdictions.yml`.

```bash
uv run python scripts/jurisdictions/states.py va
uv run python scripts/jurisdictions/counties.py va
uv run python scripts/jurisdictions/local.py va --limit 10
```

Then check `data_source/va/local/jurisdictions.yml`: a handful of populated `url:` fields and few `no_wiki_match` entries. Many `no_wiki_match` means the scraper's table coordinates are wrong — fix step 2 before continuing.

`--limit` caps Wikipedia **infobox fetches**, not records; Census ACS still pulls every jurisdiction. Fetches are cached per state, so re-runs after a fix are cheap.

Open a PR here and ask a maintainer to review.

### Maintainers only

**5. Full run:**

```bash
mise run setup-state -- --state va
```

State → counties → local (ACS + scraper + validation, plus `county_ocdids`) → upload GeoJSONs to R2 → build and upload `va.pmtiles`. It does **not** rebuild the national `states.pmtiles` — that's step 7.

**6. Validate OCD-IDs** — generated from Census names, so apostrophes, diacritics, slashes and missing LSAD suffixes leak through:

```bash
uv run python scripts/ocdids/fix.py --state va
```

**7. Rebuild the national overview** (also purges the CDN cache):

```bash
mise run generate-pmtiles
```

**8. Push**, then trigger OD sync on civicpatch.org: `POST /admin/od_sync`.

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

### PMTiles

```bash
mise run generate-pmtiles -- --state co     # one state
mise run generate-pmtiles                   # all states + national overview

mise run setup-maps -- --state co            # first, if Census TIGER boundaries changed
```

`generate-pmtiles` purges the Cloudflare cache for `cdn.civicpatch.org` after upload, needing `CLOUDFLARE_PMTILES_BUST` (a token with `Zone.Cache Purge` on `civicpatch.org`) and `CLOUDFLARE_ZONE_ID`. Unset locally, it skips the purge and exits 0.

It purges by hostname rather than per-file URL because R2 emits `Vary: Origin` and Cloudflare keys entries by that header, so per-URL purges leave stale variants behind.

### Tasks

| Task | When |
|---|---|
| `mise run setup-state -- --state {code}` | adding a state |
| `uv run python scripts/ocdids/fix.py [--state {code}]` | after regenerating `jurisdictions.yml` |
| `mise run setup-maps [-- --state {code}]` | Census boundaries changed |
| `mise run generate-pmtiles [-- --state {code}]` | jurisdiction names or data changed |

### R2 layout

```
maps/
  states.pmtiles     ← national state boundaries
  co.pmtiles         ← per-state (layers: states, counties, local)
  co/                ← source GeoJSONs uploaded by setup-maps
    states.geojson  counties.geojson  local.geojson
```
