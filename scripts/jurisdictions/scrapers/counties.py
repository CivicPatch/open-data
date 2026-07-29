from typing import AbstractSet, Any, Dict, Tuple, List

from scripts.jurisdictions.scrapers import wikipedia_utils

# County list pages are uniform across states — one wikitable, one header row, the
# linked county name in column 0 and the bare 3-digit county FIPS in column 1 — so a
# single scraper serves every state. Unlike municipalities, county infoboxes carry no
# FIPS/GEOID row at all, which is why the GEOID comes from the table.
TABLE_INDEX = 0
ROWS_TO_SKIP = 1
ENTRY_COLUMN = 0
GEOID_COLUMN = 1


def scrape(
    census_data, state: str, state_name: str, fips: str, limit=None
) -> Tuple[Dict[str, Any], List[str]]:
    entries, table_names, warnings = wikipedia_utils.get_entries(
        title=f"List_of_counties_in_{state_name.replace(' ', '_')}",
        table_index=TABLE_INDEX,
        rows_to_skip=ROWS_TO_SKIP,
        entry_column=ENTRY_COLUMN,
        geoid_column=GEOID_COLUMN,
        geoid_prefix=fips,
        cache_key=f"{state}_counties",
        state=state,
        limit=limit,
    )

    census_data, match_warnings = wikipedia_utils.match_jurisdictions(
        census_data, entries, table_names
    )
    unknown_url_pages = {
        entry["wiki_url"] for entry in entries.values() if entry.get("url_unknown")
    }
    _flag_missing_urls(census_data, unknown_url_pages)
    return census_data, warnings + match_warnings


def _flag_missing_urls(census_data, unknown_url_pages: AbstractSet[str] = frozenset()) -> None:
    """Flag counties matched to a wiki page whose infobox listed no website.

    Distinguishes a county that genuinely has no official site from one the scrape
    failed to find. Massachusetts is the main case: 8 of its 14 county governments were
    abolished between 1997 and 2000, but the counties persist as Census and judicial
    entities, so they match a wiki page and have no government website.

    `unknown_url_pages` holds wiki URLs whose infobox was never read — a failed fetch or
    a run that hit its `--limit` budget. Those are skipped: an absent url there means
    "not checked", and flagging it would assert something we never verified.
    """
    for jurisdiction in census_data.values():
        if not jurisdiction.wiki_url or jurisdiction.url:
            continue
        if jurisdiction.wiki_url in unknown_url_pages:
            continue
        issues = list(jurisdiction.issues or [])
        if "no_official_url" not in issues:
            issues.append("no_official_url")
        jurisdiction.issues = issues
