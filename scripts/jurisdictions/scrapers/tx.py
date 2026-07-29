import json
from typing import Any, Dict, Tuple, List
from pathlib import Path
from scripts.jurisdictions.scrapers import wikipedia_utils

# https://www.tml.org/

SCRAPER_PATH = Path(__file__).parent


def scrape(census_data, limit=None) -> Tuple[Dict[str, Any], List[str]]:
    entries, table_names, warnings = wikipedia_utils.get_entries(
        title="List_of_municipalities_in_Texas",
        table_index=0,
        rows_to_skip=2,
        entry_column=1,
        state="tx",
        limit=limit,
    )

    with open(SCRAPER_PATH / "tx_entries.json", "w") as f:
        json.dump(entries, f, indent=4)

    census_data, match_warnings = wikipedia_utils.match_jurisdictions(census_data, entries, table_names)
    return census_data, warnings + match_warnings
