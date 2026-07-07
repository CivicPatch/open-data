---
name: add-new-state
description: Register a new state and write its Wikipedia scraper (steps 1-4 of "Adding a New State" in DEVELOPMENT.md) — config entry, scraper implementation, Google Civic data fetch, and dry-run smoke test. Use when the user asks to set up, onboard, or add a new state to the pipeline.
tools: Read, Edit, Write, Bash, Glob, Grep
---

# Add a New State (steps 1-4)

Covers the manual prep before the full `mise run setup-state` run. Full reference: `DEVELOPMENT.md` → "Adding a New State". This skill only does steps 1-4; stop after the dry-run and hand back to the user for step 5 onward (they'll want to review results before the full run, county-conversion decisions, PMTile regen, etc.).

Ask the user for the two-letter state code and full name if not given (e.g. `va` / Virginia).

## Step 1 — Register the state

Read `scripts/state_configs.py` fully first. Determine `pull_from_census`:
- `["places"]` only — states where county subdivisions have no functioning government (statistical/MCD-less states). Most states default here.
- `["places", "county_subdivisions"]` — states with legally functioning MCDs (New England, NY, NJ, PA, MI, WI, MN, etc. — towns/townships that are themselves the unit of government, sometimes without a coextensive incorporated place).

If unsure which applies, say so and ask, or reason from Census Bureau MCD classification — don't guess silently.

Add the import (alphabetized) and the config block (match existing indentation/style exactly, including any quirks like extra leading spaces already present in neighboring entries):

```python
from scripts.scrapers import <state> as <state>_scraper
```
```python
"<state>": {
    "fips": "<fips>",
    "pull_from_census": [...],
    "scraper": <state>_scraper,
    "validation_sources": ["google"],
},
```

FIPS codes: look up the standard 2-digit state FIPS if not already known — don't guess.

## Step 2 — Write the scraper

**Before writing any code**, inspect the actual Wikipedia page structure — do not assume it matches another state's scraper. Page layouts vary:

- Single `wikitable` with one row per municipality (SC, TN, NH, NJ, ME pattern) — `table_index`/`rows_to_skip`/`entry_column` feed `wikipedia_utils.get_entries` directly.
- Multiple wikitables (e.g. incorporated + CDPs), needing GEOID-suffix fallback matching (CO, MI, WA pattern).
- **No wikitable at all** — per-letter A-Z bullet lists (`div.div-col > ul > li`) instead of a table (NC pattern). A "most populous" table may exist but is usually just a redundant top-N subset of the full A-Z list — verify by checking whether a large city from the table also appears in the letter sections before deciding to ignore it.

Inspect with a quick throwaway script, e.g.:

```bash
uv run python -c "
import requests
from bs4 import BeautifulSoup
url = 'https://en.wikipedia.org/w/api.php?action=parse&page=List_of_municipalities_in_<State>&format=json'
headers = {'User-Agent': 'CivicPatch/0.0 (https://civicpatch.org/; wiki@civicpatch.org)'}
data = requests.get(url, headers=headers).json()
soup = BeautifulSoup(data['parse']['text']['*'], 'html.parser')
tables = soup.find_all('table', {'class': 'wikitable'})
print('wikitables:', len(tables))
for i, t in enumerate(tables):
    rows = t.find_all('tr')
    print(i, len(rows), [c.get_text(strip=True) for c in rows[0].find_all(['td','th'])])
print('div-col sections (bullet-list format):', len(soup.find_all('div', {'class': 'div-col'})))
"
```

Then read 2-3 existing scrapers in `scripts/scrapers/` that match the discovered pattern (`sc.py`/`tn.py` for simple single-table, `co.py`/`mi.py`/`wa.py` for multi-table with GEOID fallback) and follow the same shape. Reuse `wikipedia_utils.get_entries` + `wikipedia_utils.match_jurisdictions` whenever the page has a real wikitable. Only write a custom entry-extraction loop (like the bullet-list case) when the page genuinely has no table — reuse `wikipedia_utils.get_entry_infobox`, `get_wiki_url`, `get_parse_url`, `_load_cache`/`_save_cache` rather than reimplementing caching or infobox parsing.

Smoke-test the new scraper directly against a couple of entries before wiring it into the full pipeline:

```bash
uv run python -c "
from scripts.scrapers import <state>
entries, table_names, warnings = <state>.scrape.__module__  # sanity import check
"
```

(or call the module's internal entry-fetch function with `limit=3` if it has one) — confirm GEOIDs and URLs come back populated, then delete any throwaway cache file it created under `scripts/scrapers/cache/`.

## Step 3 — Google Civic data

This is a manual download the user must do (team Drive access isn't available to you):
**https://drive.google.com/drive/u/0/folders/1A3qFX-UELHoNp27QyBt2edWQOkHPDbjY**

Tell the user to save it as `scripts/track_progress/google_data/<state>_all_raw.json`. Check whether the file already exists before telling them to fetch it again:

```bash
ls scripts/track_progress/google_data/<state>_all_raw.json
```

## Step 4 — Dry-run

Needs county + state boundaries first (the local step's county-OCDID spatial join depends on `counties.geojson` and `data_source/<state>/counties/jurisdictions.yml`):

```bash
uv run python scripts/setup_states.py <state>
uv run python scripts/setup_counties.py <state>
uv run python scripts/setup_local.py <state> --limit 10
```

Inspect `data_source/<state>/local/jurisdictions.yml` and the printed warnings. More than a handful of `no_wiki_match` entries means the scraper's table/column selection (or bullet-list parsing) is off — go back to step 2, not forward to step 5. `scripts/scrapers/cache/<state>_wikipedia.json` caches infobox fetches, so reruns after a fix are cheap.

## Handoff

Once the dry-run looks clean, summarize what was done (config entry, scraper file, dry-run warning count) and point the user at DEVELOPMENT.md step 5 (`mise run setup-state -- --state <state>`) for the full run — don't run it yourself as part of this skill.
