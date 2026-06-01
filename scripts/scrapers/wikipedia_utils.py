import json
from bs4 import BeautifulSoup
from pathlib import Path
import time
import requests
from typing import Any, Dict, Optional, Tuple, List

HEADERS = {'User-Agent': 'CivicPatch/0.0 (https://civicpatch.org/; wiki@civicpatch.org)'}

CACHE_DIR = Path(__file__).parent / "cache"


def _cache_path(state: str) -> Path:
    return CACHE_DIR / f"{state}_wikipedia.json"


def _load_cache(state: str) -> Dict[str, Any]:
    path = _cache_path(state)
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def _save_cache(state: str, cache: Dict[str, Any]):
    CACHE_DIR.mkdir(exist_ok=True)
    with open(_cache_path(state), "w") as f:
        json.dump(cache, f, indent=2)


def get_entries(
    title: str,
    table_index: int,
    rows_to_skip: int,
    entry_column: int,
    state: Optional[str] = None,
    limit: Optional[int] = None,
) -> Tuple[Dict[str, Any], Dict[str, str], List[str]]:
    cache = _load_cache(state) if state else {}

    parse_url = get_parse_url(title)
    data = requests.get(parse_url, headers=HEADERS)
    html = data.json()["parse"]["text"]["*"]
    soup = BeautifulSoup(html, "html.parser")
    entries_by_geoid = {}
    # Built from table HTML alone — no infobox fetch needed, available for all rows
    table_name_to_wiki_url: Dict[str, str] = {}
    warnings = []

    table = soup.find_all("table", {"class": "wikitable"})[table_index]
    rows = table.find_all("tr")[rows_to_skip:]
    fetched = 0
    for row in rows:
        cols = row.find_all(["td", "th"])

        normalized_td = normalize_td(cols[entry_column])
        entry_text = normalized_td["text"]
        wiki_url = normalized_td["url"]

        if not wiki_url:
            warnings.append(f"No Wikipedia URL found for: {entry_text}")
            continue

        # Always record table name → wiki_url regardless of limit or cache
        table_name_to_wiki_url[entry_text] = get_wiki_url(wiki_url)

        if wiki_url in cache:
            entry = cache[wiki_url]
        else:
            if limit is not None and fetched >= limit:
                continue
            entry, infobox_warnings = get_entry_infobox(wiki_url)
            fetched += 1
            if infobox_warnings:
                warnings.extend(infobox_warnings)
            if entry and state:
                cache[wiki_url] = entry
                _save_cache(state, cache)  # write after each fetch so crashes don't lose progress

        if entry:
            if entry["geoid"]:
                entries_by_geoid[entry["geoid"]] = entry
            else:
                warnings.append(f"No GEOID found in infobox for: {entry_text} ({entry.get('wiki_url', '?')})")
        else:
            warnings.append(f"Failed to retrieve entry for {wiki_url}")

    return entries_by_geoid, table_name_to_wiki_url, warnings


def get_entry_infobox(wiki_url) -> Tuple[Dict[str, Any], List[str]]:
    print("Scraping: ", wiki_url)
    time.sleep(0.05) # Wikipedia rate limit - 200 req/sec
    try:
        parse_url = get_parse_url(wiki_url)
        data = requests.get(parse_url, headers=HEADERS)
        html = data.json()["parse"]["text"]["*"]
        soup = BeautifulSoup(html, "html.parser")

        # Follow redirects (Wikipedia API returns redirect HTML rather than the target page)
        redirect = soup.find("div", {"class": "redirectMsg"})
        if redirect:
            redirect_link = redirect.find("a")
            if redirect_link and redirect_link.get("href"):
                redirect_url = redirect_link["href"]
                print("Following redirect: ", redirect_url)
                time.sleep(0.05)
                parse_url = get_parse_url(redirect_url)
                data = requests.get(parse_url, headers=HEADERS)
                html = data.json()["parse"]["text"]["*"]
                soup = BeautifulSoup(html, "html.parser")

        infobox = soup.find("table", {"class": "infobox"})
        if infobox:
            geoid = ""
            official_website = ""
            for row in infobox.find_all("tr"):
                header = row.find("th")
                if header:
                    # Remove superscripts for cleaner matching
                    for sup in header.find_all('sup'):
                        sup.extract()
                    header_text = header.get_text(strip=True).lower()
                    link = header.find("a")
                    link_text = link.get_text(strip=True).lower() if link else ""
                    # Match "FIPS code" or "FIPS" + "code" (with possible superscripts)
                    if (
                        "fips code" in header_text
                        or ("fips" in link_text and "code" in header_text)
                        or "geoid" in header_text
                    ):
                        data_td = row.find("td")
                        if data_td:
                            # Remove superscripts from td
                            for element in data_td.find_all('sup'):
                                element.extract()
                            # If td contains a link, get its text
                            td_link = data_td.find("a")
                            if td_link:
                                geoid = td_link.get_text(strip=True)
                            else:
                                geoid = data_td.get_text(strip=True)
                    elif "website" in header_text:
                        data_td = row.find("td")
                        if data_td:
                            link = data_td.find("a")
                            if link and link.has_attr("href"):
                                official_website = link["href"]
            return {
                "wiki_url": get_wiki_url(wiki_url),
                "geoid": normalize_geoid(geoid),
                "url": official_website
            }, []
    except Exception as e:
        return {}, [f"Error fetching/parsing {wiki_url}: {e}"]
    return {}, []


def get_parse_url(wiki_url: str):
    title = wiki_url.rstrip("/").split("/")[-1]
    return f"https://en.wikipedia.org/w/api.php?action=parse&page={title}&format=json"


def get_wiki_url(wiki_url: str):
    title = wiki_url.rstrip("/").split("/")[-1]
    return f"https://en.wikipedia.org/wiki/{title}"


def normalize_td(td_element):
    """Extract clean text and URL from a table cell, removing superscripts and extra symbols"""
    if not td_element:
        return {"text": "", "url": ""}

    # Find the main link (first <a> tag that's not inside a <sup>)
    entry_link = td_element.find("a")

    if entry_link:
        # Get clean text and URL from the main link
        text = entry_link.get_text(strip=True)
        url = entry_link.get("href", "")
    else:
        # No link found, just get the text content
        text = td_element.get_text(strip=True)
        url = ""

    return {
        "text": text,
        "url": url
    }


def normalize_geoid(geoid_str: str):
    return geoid_str.replace("-", "")


def find_candidates(name: str, table_name_to_wiki_url: Dict[str, str]) -> List[str]:
    """Match census jurisdiction name (LSAD stripped) against Wikipedia table names."""
    parts = name.split()
    base_name = " ".join(parts[:-1]).lower() if len(parts) > 1 else name.lower()
    return [
        wiki_url for table_name, wiki_url in table_name_to_wiki_url.items()
        if base_name in table_name.lower()
    ]


def match_jurisdictions(
    census_data, entries: Dict[str, Any], table_names: Dict[str, str]
) -> Tuple[Dict[str, Any], List[str]]:
    """Attach Wikipedia data (url, wiki_url) to each census jurisdiction by GEOID.

    Matching is tried in two steps:
      1. Direct GEOID match against the wiki entries.
      2. Fallback: same state prefix (first 2 digits) and same place suffix (last 5
         digits). This bridges GEOID representation mismatches — e.g. a place GEOID
         vs. a county-subdivision GEOID for the same municipality in MCD/town states.
         For places-only states the fallback reduces to an exact match, so it is a
         safe no-op there.

    Unmatched jurisdictions get a `no_wiki_match` issue (plus any name-based wiki URL
    candidates); suffix-fallback matches get a `geoid_mismatch` issue. Mutates and
    returns `census_data` along with root-level warnings.
    """
    root_warnings: List[str] = []
    matched_geoids = set()

    for jurisdiction_ocdid, jurisdiction in census_data.items():
        geoid = jurisdiction.geoid
        existing_issues = list(jurisdiction.issues or [])

        if geoid in entries:
            match_key = geoid
        else:
            state_prefix = geoid[:2]
            place_suffix = geoid[-5:]
            match_key = next(
                (
                    k for k in entries
                    # Full GEOID with state prefix (place or county-subdivision form).
                    if (k.startswith(state_prefix) and k.endswith(place_suffix))
                    # …or a bare 5-digit place FIPS written without the state prefix
                    # (some infoboxes do this, e.g. Keene NH lists "39300" for 3339300).
                    # Restricted to a 7-digit census *place* geoid (2 state + 5 place) so a
                    # county-subdivision's last-5 can't grab an unrelated bare place code.
                    or (len(geoid) == 7 and k == place_suffix)
                ),
                None,
            )

        if match_key is None:
            candidates = find_candidates(jurisdiction.name, table_names)
            if candidates:
                jurisdiction.generated_comments = "Wiki URL candidates: " + ", ".join(candidates)
            if "no_wiki_match" not in existing_issues:
                existing_issues.append("no_wiki_match")
            jurisdiction.issues = existing_issues or None
            census_data[jurisdiction_ocdid] = jurisdiction
            continue

        municipality = entries[match_key]
        matched_geoids.add(match_key)
        existing_issues = [i for i in existing_issues if i != "no_wiki_match"]
        if match_key != geoid:
            if "geoid_mismatch" not in existing_issues:
                existing_issues.append("geoid_mismatch")
            jurisdiction.generated_comments = (
                f"Matched via GEOID suffix fallback: census GEOID {geoid} → "
                f"wiki GEOID {match_key} ({municipality.get('wiki_url', '?')})"
            )

        jurisdiction.url = municipality.get("url", None)
        jurisdiction.wiki_url = municipality.get("wiki_url", None)
        jurisdiction.issues = existing_issues or None
        census_data[jurisdiction_ocdid] = jurisdiction

    root_warnings += warn_unmatched_wiki_entries(entries, matched_geoids)
    return census_data, root_warnings


def warn_unmatched_wiki_entries(entries: Dict[str, Any], matched_geoids: set) -> List[str]:
    """Return warnings for wiki entries that had a GEOID but were never matched to a census jurisdiction."""
    warnings = []
    for geoid, entry in entries.items():
        if geoid and geoid not in matched_geoids:
            warnings.append(
                f"Wiki entry with GEOID {geoid} ({entry.get('wiki_url', '?')}) not matched to any census jurisdiction"
            )
    return warnings
