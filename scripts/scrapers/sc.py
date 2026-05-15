from typing import Any, Dict, Tuple, List
from scripts.scrapers import wikipedia_utils


def scrape(census_data, limit=None) -> Tuple[Dict[str, Any], List[str]]:
    mun_entries, table_names, mun_warnings = wikipedia_utils.get_entries(
        title="List_of_municipalities_in_South_Carolina",
        table_index=0,
        rows_to_skip=2,
        entry_column=0,
        state="sc",
        limit=limit,
    )

    root_warnings = mun_warnings
    matched_geoids = set()

    for jurisdiction_ocdid, jurisdiction in census_data.items():
        geoid = jurisdiction.geoid
        existing_issues = list(jurisdiction.issues or [])

        if geoid in mun_entries:
            municipality = mun_entries[geoid]
            matched_geoids.add(geoid)
            existing_issues = [i for i in existing_issues if i != "no_wiki_match"]
            jurisdiction.url = municipality.get("url", None)
            jurisdiction.wiki_url = municipality.get("wiki_url", None)
        else:
            candidates = wikipedia_utils.find_candidates(jurisdiction.name, table_names)
            if candidates:
                jurisdiction.generated_comments = "Wiki URL candidates: " + ", ".join(candidates)
            if "no_wiki_match" not in existing_issues:
                existing_issues.append("no_wiki_match")

        jurisdiction.issues = existing_issues or None
        census_data[jurisdiction_ocdid] = jurisdiction

    root_warnings += wikipedia_utils.warn_unmatched_wiki_entries(mun_entries, matched_geoids)
    return census_data, root_warnings
