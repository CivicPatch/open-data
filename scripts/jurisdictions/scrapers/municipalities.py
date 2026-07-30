from typing import Any, Dict, List, Optional, Tuple

from scripts.jurisdictions.scrapers import wikipedia_utils

# Municipality list pages share a shape — one wikitable whose first column is the linked
# place name — but not consistently enough to detect, so each state's deviations live in
# its `local_wiki` entry in config.py. In practice that is at most three integers.
#
# Unlike county pages there is no FIPS column to identify the right table by, which is
# why these coordinates are declared rather than discovered.
DEFAULTS = {
    "table_index": 0,
    "rows_to_skip": 1,
    "entry_column": 0,
}

# `parser` values a state may set in local_wiki
PARSERS = {
    "table": None,                                  # the default: read a wikitable
    "bullet_list": wikipedia_utils.bullet_list_refs,  # e.g. North Carolina
}


def default_title(state_name: str) -> str:
    return f"List_of_municipalities_in_{state_name.replace(' ', '_')}"


def scrape(
    census_data,
    state: str,
    state_name: str,
    wiki: Optional[Dict[str, Any]] = None,
    limit=None,
) -> Tuple[Dict[str, Any], List[str]]:
    """Attach Wikipedia data (url, wiki_url) to each municipality.

    `wiki` is the state's `local_wiki` config: any of the DEFAULTS keys, plus
      title   — override the page name. Needed where the conventional title is a
                disambiguation page (Georgia: the country vs the U.S. state).
      parser  — a key of PARSERS; defaults to reading a wikitable.
    """
    options = dict(wiki or {})
    title = options.pop("title", None) or default_title(state_name)
    parser = options.pop("parser", "table")

    if parser not in PARSERS:
        raise ValueError(
            f"{state}: unknown local_wiki parser {parser!r}; expected one of {sorted(PARSERS)}"
        )

    unknown = set(options) - set(DEFAULTS)
    if unknown:
        raise ValueError(f"{state}: unknown local_wiki keys {sorted(unknown)}")

    entries, table_names, warnings = wikipedia_utils.get_entries(
        title=title,
        state=state,
        limit=limit,
        extract_refs=PARSERS[parser],
        **{**DEFAULTS, **options},
    )

    census_data, match_warnings = wikipedia_utils.match_jurisdictions(
        census_data, entries, table_names
    )
    return census_data, warnings + match_warnings
