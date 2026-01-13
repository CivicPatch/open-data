import requests
from typing import Any, Dict, Tuple, List
from bs4 import BeautifulSoup
from scripts.scrapers import wikipedia_utils

# MUNICIPALITIES_URL = "https://www.nj.gov/nj/gov/county/localgov.shtml"

def scrape(census_data) -> Tuple[Dict[str, Any], List[str]]:
    warnings = []
    mun_entries, mun_warnings = wikipedia_utils.get_entries(
        title="List_of_municipalities_in_New_Jersey",
        table_index=0,
        rows_to_skip=2,
        entry_column=0
    )

    warnings = mun_warnings

    entries = {
        **mun_entries,
    }

    for jurisdiction_ocdid, jurisdiction in census_data.items():
        geoid = jurisdiction.geoid
        if geoid not in entries:
            state_prefix = geoid[:2]
            place_suffix = geoid[5:]
            potential_entry_keys = [k for k in entries.keys() if k.startswith(state_prefix) and k.endswith(place_suffix)]

            if potential_entry_keys:
                # If we found potential entries, use the first one
                municipality = entries[potential_entry_keys[0]]
                warnings.append(f"Resolved GEOID mismatch for {jurisdiction.name}: using GEOID {municipality['geoid']} instead of {geoid}")
            else:
                warnings.append(f"No matching municipality found for GEOID: {geoid}, ({jurisdiction.name})")
                continue
        else:
            municipality = entries[geoid]

        jurisdiction.url = municipality.get("url", None)
        census_data[jurisdiction_ocdid] = jurisdiction

    return census_data, warnings

