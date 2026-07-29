from typing import AbstractSet, Any, Dict, Tuple, List

from scripts.jurisdictions.scrapers import wikipedia_utils

# County list tables have the same shape in every state — one header row, the linked
# county name in column 0 and the bare 3-digit county FIPS in column 1 — so a single
# scraper serves every state. Unlike municipalities, county infoboxes carry no
# FIPS/GEOID row at all, which is why the GEOID comes from the table.
#
# Their *position* on the page is not uniform, though, so the table is located by that
# shape rather than by a fixed index. See _select_county_table.
ROWS_TO_SKIP = 1
ENTRY_COLUMN = 0
GEOID_COLUMN = 1
FALLBACK_TABLE_INDEX = 0


def scrape(
    census_data, state: str, state_name: str, fips: str, limit=None
) -> Tuple[Dict[str, Any], List[str]]:
    entries, table_names, warnings = wikipedia_utils.get_entries(
        title=f"List_of_counties_in_{state_name.replace(' ', '_')}",
        table_index=FALLBACK_TABLE_INDEX,
        select_table=_select_county_table,
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


def _select_county_table(tables) -> int:
    """Locate the county list table by its shape rather than its position.

    South Carolina is why: its page puts a county-name/abbreviation table (plain text,
    no links) at index 0 and the real counties table at index 1. Indexing blindly read
    the abbreviation table, found no links, and matched nothing.

    The county table is identified by its first data row having a linked name in
    ENTRY_COLUMN and a short numeric FIPS in GEOID_COLUMN. Falls back to
    FALLBACK_TABLE_INDEX so behaviour is unchanged on pages with a single table.
    """
    for index, table in enumerate(tables):
        rows = table.find_all("tr")
        if len(rows) <= ROWS_TO_SKIP:
            continue
        cells = rows[ROWS_TO_SKIP].find_all(["td", "th"])
        if len(cells) <= GEOID_COLUMN:
            continue
        if cells[ENTRY_COLUMN].find("a") is None:
            continue
        # Read without mutating the soup: tolerate a trailing reference like "001[13]"
        fips = cells[GEOID_COLUMN].get_text(strip=True).split("[")[0].strip()
        if fips.isdigit() and len(fips) <= 3:
            return index
    return FALLBACK_TABLE_INDEX


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
