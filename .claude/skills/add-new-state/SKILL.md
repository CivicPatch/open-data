---
name: add-new-state
description: Register a new state and fit its Wikipedia list-page config (steps 1-4 of "Adding a new state" in DEVELOPMENT.md) — config entry, local_wiki coordinates, Google Civic data fetch, and dry-run smoke test. Use when the user asks to set up, onboard, or add a new state to the pipeline.
tools: Read, Edit, Write, Bash, Glob, Grep
---

# Add a New State (steps 1-4)

Covers the manual prep before the full `mise run setup-state` run. Full reference: `DEVELOPMENT.md` → "Adding a new state". This skill only does steps 1-4; stop after the dry-run and hand back to the user for step 5 onward (they'll want to review results before the full run, OCD-ID validation, the civicpatch.org map generation trigger, etc.).

Ask the user for the two-letter state code and full name if not given (e.g. `va` / Virginia).

## Step 1 — Register the state

Read `scripts/jurisdictions/config.py` fully first. Determine `pull_from_census`:
- `["places"]` only — states where county subdivisions have no functioning government (statistical/MCD-less states). Most states default here.
- `["places", "county_subdivisions"]` — states with legally functioning MCDs (New England, NY, NJ, PA, MI, WI, MN, etc. — towns/townships that are themselves the unit of government, sometimes without a coextensive incorporated place).

If unsure which applies, say so and ask, or reason from Census Bureau MCD classification — don't guess silently.

Add the config block (match existing indentation/style exactly, including any quirks like extra leading spaces already present in neighboring entries). There is no import to add — states are pure data now:

```python
"<state>": {
    "fips": "<fips>",
    "name": "<State Name>",
    "pull_from_census": [...],
    "local_wiki": {},          # filled in by step 2
    "validation_sources": ["google"],
},
```

FIPS codes: look up the standard 2-digit state FIPS if not already known — don't guess.

## Step 2 — Fit `local_wiki` to the list page

**There is no per-state scraper.** `scripts/jurisdictions/scrapers/municipalities.py` handles every state; `local_wiki` supplies only that state's deviations from the defaults. Read `municipalities.py` before doing anything here — it is ~60 lines and is the whole contract.

| key | default | set it when |
|---|---|---|
| `table_index` | `0` | the municipality table isn't the page's first wikitable |
| `rows_to_skip` | `1` | the header spans two rows (usually land area splitting into sq mi / km²) |
| `entry_column` | `0` | the place name isn't the first column |
| `title` | `List_of_municipalities_in_<State_Name>` | that title is a disambiguation page (Georgia: the country vs the U.S. state) |
| `parser` | `"table"` | `"bullet_list"` — the page has no wikitable, just per-letter `div.div-col > ul > li` bullets (North Carolina) |

`{}` means all defaults. Unknown keys raise a `ValueError` at run time rather than being silently ignored, so a typo surfaces immediately.

**Inspect the actual page before writing values** — do not assume it matches another state:

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
    print('   row1:', [c.get_text(strip=True) for c in rows[1].find_all(['td','th'])][:4])
print('div-col sections (bullet-list format):', len(soup.find_all('div', {'class': 'div-col'})))
"
```

Reading the output:
- The table whose row count ≈ the state's municipality count is the one — `table_index`. A short table (~50 rows) next to a long one is a "most populous" highlight subset; ignore it. Verify by checking that a large city in the short table also appears in the long one.
- If row 1 still looks like header text (`sq mi`, `km²`) rather than a place name, that's `rows_to_skip: 2`.
- If the first column is a rank or county name rather than the place, count over to set `entry_column`.
- `wikitables: 0` (or only a highlight table) with several `div-col` sections → `parser: "bullet_list"`.

If the page's shape fits none of these, stop and report it — a genuinely new layout means a new entry in `PARSERS`, which is a code change to hand back, not something to bolt on per-state.

## Step 3 — Google Civic data

This is a manual download the user must do (team Drive access isn't available to you):
**https://drive.google.com/drive/u/0/folders/1A3qFX-UELHoNp27QyBt2edWQOkHPDbjY**

Tell the user to save it as `scripts/track_progress/google_data/<state>_all_raw.json`. Check whether the file already exists before telling them to fetch it again:

```bash
ls scripts/track_progress/google_data/<state>_all_raw.json
```

## Step 4 — Dry-run

This repo no longer touches geometry at all — which counties contain a place is worked out by civicpatch.org's boundary overlay and stored there — so nothing here needs shapefiles or a prior county run. Still run the three levels in order; each writes its own `jurisdictions.yml`.

```bash
uv run python scripts/jurisdictions/states.py <state>
uv run python scripts/jurisdictions/counties.py <state>
uv run python scripts/jurisdictions/local.py <state> --limit 10
```

Inspect `data_source/<state>/local/jurisdictions.yml` and the printed warnings.

`local.py` calls `preflight_check` first and **exits** if step 3's file is missing, so the local run is blocked until the user provides it. `states.py` and `counties.py` are unaffected — run them anyway. To check the `local_wiki` fit while blocked, call the scraper directly:

```bash
uv run python -c "
from scripts.jurisdictions.scrapers import wikipedia_utils
from scripts.jurisdictions.scrapers.municipalities import DEFAULTS, default_title
from scripts.jurisdictions.config import state_configs
cfg = dict(state_configs['<state>']['local_wiki'])
title = cfg.pop('title', None) or default_title('<State Name>')
entries, table_names, warnings = wikipedia_utils.get_entries(
    title=title, state='<state>', limit=10, extract_refs=None, **{**DEFAULTS, **cfg})
print('names parsed:', len(table_names), list(table_names)[:12])
for k, v in list(entries.items())[:6]:
    print(' ', k, v.get('url'), v.get('wiki_url'))
print('warnings:', warnings or '(none)')
"
```

`table_names` is a dict keyed by name — `len()` it against the state's known municipality count, and confirm the fetched entries have both `url` and `wiki_url`. That settles step 2 on its own.

These commands assume mise's env (`PYTHONPATH=.` plus `.env`, which holds `CENSUS_API_KEY`). Outside a mise shell, prefix with `set -a && . ./.env && set +a && PYTHONPATH=.` — a bare `uv run` fails with `ModuleNotFoundError: No module named 'schemas'`.

**Do not read a high `no_wiki_match` count on a `--limit` run as a failure.** Municipality GEOIDs come from the infobox, so `get_entries` drops every row past the fetch budget before matching and each one lands as `no_wiki_match`. Roughly `total − limit` flagged entries is the expected result of `--limit 10`, and says nothing about whether `local_wiki` is right.

What to check instead:
- the first N entries (the ones actually fetched) have `url:` and `wiki_url:` populated — if even those are unmatched, `local_wiki` is wrong, go back to step 2;
- no `No Wikipedia URL found for:` warnings, which mean `entry_column` points at a cell with no link;
- the counties file, where a high `no_wiki_match` count *is* a real failure — county GEOIDs come from the table, so they are not subject to the limit artifact.

Only a run without `--limit` tells you the fit across the whole state.

`--limit` caps Wikipedia **infobox fetches**, not records — Census ACS still pulls every jurisdiction. `scripts/jurisdictions/scrapers/cache/<state>_wikipedia.json` caches those fetches, so reruns after a fix are cheap; delete it if a fix changes which entries get fetched. `counties.py` takes the same `--limit`, plus `--skip-wiki` to pull Census data only.

## Handoff

Once the dry-run looks clean, summarize what was done (config entry, `local_wiki` values and why, dry-run warning count) and point the user at DEVELOPMENT.md step 5 (`mise run setup-state -- --state <state>`) for the full run — don't run it yourself as part of this skill. Boundaries and pmtiles come later and elsewhere: after the full run syncs, a maintainer triggers `GenerateMapsWorkflow` on civicpatch.org.
