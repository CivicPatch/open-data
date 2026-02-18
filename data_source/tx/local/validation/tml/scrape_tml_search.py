"""
scrape_tml_search.py

Scrapes a TML directory search-results page (and all pagination), then follows
each individual's /profile/individual/{id} link to collect their phone number.
Saves raw results to a JSON file.

Usage:
    python scrape_tml_search.py \\
        --search-url "https://directory.tml.org/results?search%5Btitle%5D%5B%5D=ABAC&search%5Btitle%5D%5B%5D=ABAD&search%5Btitle%5D%5B%5D=AB02&search%5Btitle%5D%5B%5D=AAAA&search%5Btitle%5D%5B%5D=AB01&search%5Bsubmit%5D=&search%5Btype%5D=title" \\
        --out tml_raw.json

    # Resume a partial run
    python scrape_tml_search.py --search-url "..." --out tml_raw.json --resume

Options:
    --out PATH              Output JSON file (default: tml_raw.json)
    --delay FLOAT           Seconds between search-page requests (default: 1.0)
    --individual-delay FLT  Seconds between individual profile fetches (default: 0.5)
    --resume                Skip individuals whose phone is already populated in --out

Output JSON schema (one object per person):
    [
      {
        "individual_id":  5351,
        "individual_url": "https://directory.tml.org/profile/individual/5351",
        "name":           "Kirk Watson",
        "role":           "Mayor",
        "city_name":      "City of Austin",
        "city_id":        1301,
        "city_url":       "https://directory.tml.org/profile/city/1301",
        "phone":          "(512) 974-2000"   // null if not listed
      },
      ...
    ]
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://directory.tml.org"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; civic-data-scraper/1.0)",
    "Accept": "text/html,application/xhtml+xml",
}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_search_results_page(html: str) -> list[dict]:
    """
    Parse one page of TML search results.

    Each result is a triplet:
      <element> role text </element>
      <element> <a href="/profile/individual/ID">Name</a> </element>
      <element> <a href="/profile/city/ID">City Name</a> </element>

    Returns a list of partial person dicts (no phone yet).
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    ind_links = soup.find_all("a", href=re.compile(r"^/profile/individual/\d+$"))

    for a_ind in ind_links:
        name    = a_ind.get_text(strip=True)
        ind_href = a_ind["href"]
        ind_id  = int(re.search(r"/profile/individual/(\d+)", ind_href).group(1))
        parent  = a_ind.parent

        # Role: preceding sibling with no <a> tag inside
        role = None
        prev = parent.find_previous_sibling()
        if prev and not prev.find("a"):
            role = prev.get_text(strip=True)

        # City: following sibling containing a /profile/city/ link
        city_name = None
        city_id   = None
        city_url  = None
        nxt = parent.find_next_sibling()
        if nxt:
            city_link = nxt.find("a", href=re.compile(r"/profile/city/"))
            if city_link:
                city_name = city_link.get_text(strip=True)
                city_href = city_link["href"]
                m = re.search(r"/profile/city/(\d+)", city_href)
                if m:
                    city_id  = int(m.group(1))
                    city_url = BASE_URL + city_href

        results.append({
            "individual_id":  ind_id,
            "individual_url": BASE_URL + ind_href,
            "name":           name,
            "role":           role or "",
            "city_name":      city_name or "",
            "city_id":        city_id,
            "city_url":       city_url,
            "phone":          None,
        })

    return results


def find_next_page_url(html: str, current_url: str) -> str | None:
    """Return the URL of the next results page, or None if on the last page."""
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a"):
        if a.get_text(strip=True) in ("Next", "Next »", ">", "»", "next"):
            href = a.get("href", "")
            if href:
                return urljoin(current_url, href)
    return None


def parse_individual_page(html: str) -> dict:
    """
    Extract available fields from an individual profile page.
    The page is a <dl> with <dt> labels and <dd> values.
    Currently extracts: phone
    """
    soup = BeautifulSoup(html, "html.parser")
    result = {}
    for dt in soup.find_all("dt"):
        label = dt.get_text(strip=True).lower().rstrip(":")
        dd = dt.find_next_sibling("dd")
        if not dd:
            continue
        value = dd.get_text(strip=True)
        if label == "phone" and value:
            result["phone"] = value
    return result


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def fetch_page(session: requests.Session, url: str) -> str | None:
    try:
        resp = session.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        print(f"  [ERROR] {url}: {e}", file=sys.stderr)
        return None


def scrape(session: requests.Session, search_url: str,
           delay: float, individual_delay: float,
           resume: bool, out_path: str) -> list[dict]:

    # Load existing records if resuming
    all_records: dict[int, dict] = {}
    if Path(out_path).exists():
        try:
            with open(out_path) as f:
                for r in json.load(f):
                    all_records[r["individual_id"]] = r
            print(f"  Loaded {len(all_records)} existing records from {out_path}")
        except Exception as e:
            print(f"  [WARN] Could not load {out_path}: {e}", file=sys.stderr)

    def save():
        with open(out_path, "w") as f:
            json.dump(
                [all_records[k] for k in sorted(all_records)],
                f, indent=2, ensure_ascii=False
            )

    # --- Step 1: Collect all search result pages ---
    print(f"\n[STEP 1] Fetching search results pages...")
    url = search_url
    page_num = 0

    while url:
        page_num += 1
        print(f"  Page {page_num}: {url}")
        html = fetch_page(session, url)
        if not html:
            break

        records = parse_search_results_page(html)
        print(f"    Found {len(records)} individuals")

        for r in records:
            iid = r["individual_id"]
            if iid not in all_records:
                all_records[iid] = r
            else:
                # Refresh search-page fields (role/city) but preserve phone if already fetched
                for k in ("role", "city_name", "city_id", "city_url"):
                    if r[k]:
                        all_records[iid][k] = r[k]

        next_url = find_next_page_url(html, url)
        url = next_url if next_url and next_url != url else None
        if url:
            time.sleep(delay)

    print(f"  Total unique individuals: {len(all_records)}")
    save()

    # --- Step 2: Fetch individual profiles for phone ---
    if resume:
        need_phone = [iid for iid, r in all_records.items() if r.get("phone") is None]
    else:
        need_phone = list(all_records.keys())

    print(f"\n[STEP 2] Fetching {len(need_phone)} individual profiles for phone numbers...")

    for i, iid in enumerate(need_phone, 1):
        rec = all_records[iid]
        print(f"  [{i}/{len(need_phone)}] {rec['name']} ({rec['individual_url']})...", end=" ", flush=True)
        time.sleep(individual_delay)
        html = fetch_page(session, rec["individual_url"])
        if html:
            extra = parse_individual_page(html)
            rec.update(extra)
            print(f"phone={rec.get('phone', 'n/a')}")
        else:
            print("failed")
        save()

    print(f"\n[DONE] {len(all_records)} records written to {out_path}")
    return list(all_records.values())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Scrape TML directory search results and individual profiles"
    )
    parser.add_argument(
        "--search-url", required=True,
        help="Full TML search results URL"
    )
    parser.add_argument(
        "--out", default="tml_raw.json",
        help="Output JSON file (default: tml_raw.json)"
    )
    parser.add_argument(
        "--delay", type=float, default=1.0,
        help="Seconds between search-page requests (default: 1.0)"
    )
    parser.add_argument(
        "--individual-delay", type=float, default=0.5,
        help="Seconds between individual profile fetches (default: 0.5)"
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Skip individuals whose phone is already populated in the output file"
    )
    args = parser.parse_args()

    session = requests.Session()
    scrape(
        session,
        args.search_url,
        args.delay,
        args.individual_delay,
        args.resume,
        args.out,
    )


if __name__ == "__main__":
    main()
