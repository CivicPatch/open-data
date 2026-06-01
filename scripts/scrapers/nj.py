from typing import Any, Dict, Tuple, List
from scripts.scrapers import wikipedia_utils


def scrape(census_data, limit=None) -> Tuple[Dict[str, Any], List[str]]:
    entries, table_names, warnings = wikipedia_utils.get_entries(
        title="List_of_municipalities_in_New_Jersey",
        table_index=0,
        rows_to_skip=2,
        entry_column=0,
        state="nj",
        limit=limit,
    )

    census_data, match_warnings = wikipedia_utils.match_jurisdictions(census_data, entries, table_names)
    return census_data, warnings + match_warnings
