import requests
from bs4 import BeautifulSoup
from typing import Any, Dict, Tuple, List
import time
from scripts.scrapers import wikipedia_utils

MUNICIPALITIES_URL = "https://en.wikipedia.org/w/api.php?action=parse&page=List_of_municipalities_in_Colorado&format=json"
CCDS_URL = "https://en.wikipedia.org/wiki/List_of_census-designated_places_in_Colorado"

def scrape(census_data) -> Tuple[Dict[str, Any], List[str]]:
    mun_entries, mun_warnings = wikipedia_utils.get_entries(
        title="List_of_municipalities_in_Washington",
        table_index=1,
        rows_to_skip=2,
        entry_column=0
    )

    warnings = mun_warnings 

    entries = {
        **mun_entries,
    }

    for jurisdiction_id, jurisdiction in census_data.items():
        geoid = jurisdiction.geoid
        if geoid in entries:
            municipality = entries[geoid]
            jurisdiction.url = municipality.get("url", None)
            census_data[jurisdiction_id] = jurisdiction
        else:
            warnings.append(f"No municipality data found for GEOID: {geoid}, ({jurisdiction.name})")
    return census_data, warnings
