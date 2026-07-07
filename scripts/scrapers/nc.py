from typing import Any, Dict, Tuple, List
import requests
from bs4 import BeautifulSoup
from scripts.scrapers import wikipedia_utils

TITLE = "List_of_municipalities_in_North_Carolina"


def _get_entries(state: str, limit=None) -> Tuple[Dict[str, Any], Dict[str, str], List[str]]:
    """North Carolina's list page has no full wikitable — municipalities are listed as
    per-letter bullet lists (`div.div-col > ul > li`) instead. The one wikitable on the
    page is just a "most populous" top-50 highlight, a subset of the A-Z list, so it's
    ignored here in favor of parsing the bullet lists directly."""
    cache = wikipedia_utils._load_cache(state)

    parse_url = wikipedia_utils.get_parse_url(TITLE)
    data = requests.get(parse_url, headers=wikipedia_utils.HEADERS)
    html = data.json()["parse"]["text"]["*"]
    soup = BeautifulSoup(html, "html.parser")

    entries_by_geoid = {}
    table_name_to_wiki_url: Dict[str, str] = {}
    warnings = []
    fetched = 0

    for div in soup.find_all("div", {"class": "div-col"}):
        for li in div.find_all("li"):
            link = li.find("a")
            if not link or not link.get("href"):
                warnings.append(f"No Wikipedia URL found for: {li.get_text(strip=True)}")
                continue

            entry_text = link.get_text(strip=True)
            wiki_url = link["href"]
            table_name_to_wiki_url[entry_text] = wikipedia_utils.get_wiki_url(wiki_url)

            if wiki_url in cache:
                entry = cache[wiki_url]
            else:
                if limit is not None and fetched >= limit:
                    continue
                entry, infobox_warnings = wikipedia_utils.get_entry_infobox(wiki_url)
                fetched += 1
                if infobox_warnings:
                    warnings.extend(infobox_warnings)
                if entry:
                    cache[wiki_url] = entry
                    wikipedia_utils._save_cache(state, cache)

            if entry:
                if entry["geoid"]:
                    entries_by_geoid[entry["geoid"]] = entry
                else:
                    warnings.append(f"No GEOID found in infobox for: {entry_text} ({entry.get('wiki_url', '?')})")
            else:
                warnings.append(f"Failed to retrieve entry for {wiki_url}")

    return entries_by_geoid, table_name_to_wiki_url, warnings


def scrape(census_data, limit=None) -> Tuple[Dict[str, Any], List[str]]:
    entries, table_names, warnings = _get_entries("nc", limit=limit)
    census_data, match_warnings = wikipedia_utils.match_jurisdictions(census_data, entries, table_names)
    return census_data, warnings + match_warnings
