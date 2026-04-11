import requests
from typing import Any, Dict, Tuple, List
from bs4 import BeautifulSoup
from scripts.scrapers import wikipedia_utils

# MUNICIPALITIES_URL = "https://www.nj.gov/nj/gov/county/localgov.shtml"

def scrape(census_data, limit=None) -> Tuple[Dict[str, Any], List[str]]:
    root_warnings = []
    mun_entries, table_names, mun_warnings = wikipedia_utils.get_entries(
        title="List_of_municipalities_in_New_Jersey",
        table_index=0,
        rows_to_skip=2,
        entry_column=0,
        state="nj",
        limit=limit,
    )

    root_warnings = mun_warnings

    entries = {**mun_entries}
    matched_geoids = set()

    for jurisdiction_ocdid, jurisdiction in census_data.items():
        geoid = jurisdiction.geoid
        existing_issues = list(jurisdiction.issues or [])

        if geoid not in entries:
            state_prefix = geoid[:2]
            place_suffix = geoid[-5:]
            potential_entry_keys = [k for k in entries.keys() if k.startswith(state_prefix) and k.endswith(place_suffix)]

            if potential_entry_keys:
                municipality = entries[potential_entry_keys[0]]
                matched_geoids.add(potential_entry_keys[0])
                if "geoid_mismatch" not in existing_issues:
                    existing_issues.append("geoid_mismatch")
                jurisdiction.generated_comments = (
                    f"Matched via GEOID suffix fallback: census GEOID {geoid} → "
                    f"wiki GEOID {potential_entry_keys[0]} ({municipality.get('wiki_url', '?')})"
                )
            else:
                candidates = wikipedia_utils.find_candidates(jurisdiction.name, table_names)
                if candidates:
                    jurisdiction.generated_comments = "Wiki URL candidates: " + ", ".join(candidates)
                if "no_wiki_match" not in existing_issues:
                    existing_issues.append("no_wiki_match")
                jurisdiction.issues = existing_issues or None
                census_data[jurisdiction_ocdid] = jurisdiction
                continue
        else:
            municipality = entries[geoid]
            matched_geoids.add(geoid)
            existing_issues = [i for i in existing_issues if i != "no_wiki_match"]

        jurisdiction.url = municipality.get("url", None)
        jurisdiction.wiki_url = municipality.get("wiki_url", None)
        jurisdiction.issues = existing_issues or None
        census_data[jurisdiction_ocdid] = jurisdiction

    root_warnings += wikipedia_utils.warn_unmatched_wiki_entries(entries, matched_geoids)
    return census_data, root_warnings
