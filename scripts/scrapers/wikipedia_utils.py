from bs4 import BeautifulSoup
import time
import requests
from typing import Any, Dict, Tuple, List

HEADERS = {'User-Agent': 'CivicPatch/0.0 (https://civicpatch.org/; wiki@civicpatch.org)'}

def get_entries(title, table_index: int, rows_to_skip: int, entry_column: int) -> Tuple[Dict[str, Any], List[str]]:
    parse_url = get_parse_url(title)
    data = requests.get(parse_url, headers=HEADERS)
    html = data.json()["parse"]["text"]["*"]
    soup = BeautifulSoup(html, "html.parser")
    entries_by_geoid = {}
    warnings = []

    table = soup.find_all("table", {"class": "wikitable"})[table_index]
    rows = table.find_all("tr")[rows_to_skip:]
    for row in rows:
        cols = row.find_all(["td", "th"])

        normalized_td = normalize_td(cols[entry_column])
        entry_text = normalized_td["text"]
        wiki_url = normalized_td["url"]
        entry, infobox_warnings = get_entry_infobox(wiki_url)
        if len(infobox_warnings) > 0:
            warnings.extend(infobox_warnings) 
        print("Infobox: ", entry)

        if not wiki_url:
            warnings.append(f"No Wikipedia URL found for: {entry_text}")
            continue

        if entry:
            if entry["geoid"]:
                entries_by_geoid[entry["geoid"]] = entry
            else:
                warnings.append(f"No GEOID found in infobox for {entry}")
        else:
            warnings.append(f"Failed to retrieve entry for {wiki_url}")

    print("Warnings found: ", warnings)
    return entries_by_geoid, warnings

def get_entry_infobox(wiki_url) -> Tuple[Dict[str, Any], List[str]]:
    print("Scraping: ", wiki_url)
    time.sleep(0.05) # Wikipedia rate limit - 200 req/sec
    try:
        parse_url = get_parse_url(wiki_url)
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
    title = wiki_url.split("/")[-1]
    if title.endswith("/"):
        title = title[:-1]
    parse_url = f"https://en.wikipedia.org/w/api.php?action=parse&page={title}&format=json"
    return parse_url

def get_wiki_url(wiki_url: str):
    title = wiki_url.split("/")[-1]
    if title.endswith("/"):
        title = title[:-1]
    full_url = f"https://en.wikipedia.org/wiki/{title}"
    return full_url


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
