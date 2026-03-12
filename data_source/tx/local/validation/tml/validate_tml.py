"""
validate_tml.py

Compares scraped TML data (tml_raw.json from scrape_tml_search.py) against
civicpatch YAML files (data/tx/local/place_*).

Matches people by name (case-insensitive, stripping titles/suffixes).
Only considers place: jurisdictions from the YAML side.
The only field TML provides for comparison is phone.

Usage:
    python validate_tml.py \\
        --tml-file tml_raw.json \\
        --yaml-dir data/tx/local \\
        --out-dir validation_output_tml

Outputs:
    {out_dir}/report.txt            — human-readable summary
    {out_dir}/per_field.csv         — global phone match rate
    {out_dir}/per_jurisdiction.csv  — per-jurisdiction breakdown
    {out_dir}/mismatches.csv        — one row per phone mismatch
"""

import argparse
import csv
import glob
import json
import os
import re
import sys
from collections import defaultdict
import unicodedata

import yaml


# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------

STRIP_TOKENS = {
    # suffixes
    "jr", "sr", "ii", "iii", "iv", "v",
    # titles
    "dr", "mr", "mrs", "ms", "miss", "prof",
    "hon", "rev", "esq", "phd", "md", "dds", "mpa", "cmo", "mstm", "med", "cpa", "(retired)", "pe"
}


def normalize_name(name: str) -> str:
    """
    Normalize name for matching by using only the last name.
    Removes diacritics and punctuation, lowercases, and strips whitespace.
    """
    if not name:
        return ""
    name = name.strip().lower()
    # Remove all punctuation except spaces and quotes
    name = re.sub(r"[^\w\s\"]", "", name)
    # Remove quoted nicknames
    name = re.sub(r'"\w+"', '', name)
    # Remove extra whitespace
    name = re.sub(r"\s+", " ", name)
    # Remove accents/diacritics
    name = unicodedata.normalize("NFKD", name)
    name = "".join([c for c in name if not unicodedata.combining(c)])
    # Remove titles/suffixes
    parts = [p for p in name.split() if p not in STRIP_TOKENS]
    # Use only the last token (last name) for matching
    if parts:
        return parts[-1]
    return ""


# ---------------------------------------------------------------------------
# Phone normalization
# ---------------------------------------------------------------------------

def normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone) if phone else ""


def phones_overlap(yaml_list: list, tml_list: list) -> bool:
    """True if any normalized phone in yaml_list matches any in tml_list."""
    a = {normalize_phone(p) for p in (yaml_list or []) if p}
    b = {normalize_phone(p) for p in (tml_list or []) if p}
    return bool(a & b)


# ---------------------------------------------------------------------------
# OCD-ID helpers
# ---------------------------------------------------------------------------

def is_place_ocdid(ocdid: str) -> bool:
    return bool(ocdid and re.search(r"/place:[^/]+", ocdid))


def place_key_from_ocdid(ocdid: str) -> str:
    m = re.search(r"(place:[^/]+?)(?:/|$)", ocdid or "")
    return m.group(1) if m else (ocdid or "unknown")


def get_yaml_place_ocdid(person: dict) -> str | None:
    office = person.get("office") or {}
    for candidate in [office.get("division_ocdid"), person.get("jurisdiction_ocdid")]:
        if candidate and is_place_ocdid(candidate):
            return candidate
    jid = person.get("jurisdiction_ocdid") or ""
    if "/place:" in jid:
        m = re.search(r"(ocd-[^/]+(?:/[^/]+)*?/place:[^/]+)", jid)
        if m:
            return m.group(1)
    return None


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

def load_yaml_people(yaml_dir: str) -> list[dict]:
    pattern = os.path.join(yaml_dir, "place_*")
    top_level = glob.glob(pattern)

    files = []
    for path in sorted(top_level):
        if os.path.isdir(path):
            files.extend(sorted(glob.glob(os.path.join(path, "*.yml"))))
            files.extend(sorted(glob.glob(os.path.join(path, "*.yaml"))))
        elif os.path.isfile(path) and path.endswith((".yml", ".yaml")):
            files.append(path)

    people = []
    for filepath in files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if isinstance(data, list):
                for p in data:
                    if isinstance(p, dict):
                        p["_source_file"] = filepath
                        people.append(p)
            elif isinstance(data, dict):
                data["_source_file"] = filepath
                people.append(data)
        except Exception as e:
            print(f"  [WARN] Could not parse {filepath}: {e}", file=sys.stderr)
    return people


def load_tml_records(tml_file: str) -> list[dict]:
    with open(tml_file, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def build_tml_name_index(tml_records: list[dict]) -> dict[str, list[dict]]:
    """Normalized name -> list of TML records (a name can appear in multiple cities)."""
    index: dict[str, list[dict]] = defaultdict(list)
    for r in tml_records:
        name = r.get("name", "")
        if name and name.lower() != "position vacant":
            index[normalize_name(name)].append(r)
    return index


def build_tml_name_index_by_jur(tml_records: list[dict]) -> dict[str, dict[str, list[dict]]]:
    """
    Build index: jurisdiction -> normalized name -> list of TML records.
    """
    index = defaultdict(lambda: defaultdict(list))
    for r in tml_records:
        name = r.get("name", "")
        jur = city_name_to_place_key(r.get("city_name", ""))
        if name and name.lower() != "position vacant" and jur:
            index[jur][normalize_name(name)].append(r)
    return index


def city_name_to_place_key(city_name: str) -> str:
    """
    Converts a city name like 'City of Austin' or 'Austin' to 'place:austin'.
    Removes 'City of' prefix, lowercases, replaces spaces with underscores.
    """
    if not city_name:
        return ""
    name = city_name.strip()
    # Remove 'City of' or similar prefixes
    name = re.sub(r"^(City|Town|Village|Municipality|Borough|County) of ", "", name, flags=re.IGNORECASE)
    name = name.lower().replace(" ", "_")
    return f"place:{name}"

def city_name_to_jurisdiction_ocdid(city_name: str) -> str:
    """
    Converts a city name to a jurisdiction OCD-ID if possible.
    This is a best-effort heuristic and may not be accurate for all cities.
    For example, 'City of Austin' would ideally map to 'ocd-division/country:us/state:tx/place:austin'.
    However, without state information, we can only return 'ocd-division/country:us/place:austin'.
    """
    place_key = city_name_to_place_key(city_name)
    if place_key:
        return f"ocd-jurisdiction/country:us/state:tx/{place_key}/government"
    return ""


def best_tml_match(yaml_person: dict, candidates: list[dict]) -> dict:
    """
    Given multiple TML records with the same name, prefer the one whose
    city name loosely matches the yaml person's jurisdiction.
    Falls back to the first candidate.
    """
    if len(candidates) == 1:
        return candidates[0]

    jur_ocdid = get_yaml_place_ocdid(yaml_person) or ""
    yaml_place_key = place_key_from_ocdid(jur_ocdid)
    for c in candidates:
        tml_place_key = city_name_to_place_key(c.get("city_name", ""))
        if tml_place_key == yaml_place_key:
            return c
    return candidates[0]


def tml_division_ocdid(tr: dict) -> str:
    """
    Attempt to extract a division_ocdid from TML office role.
    Ex: 
        Council Member District 2 -> ocd-division/country:us/state:tx/place:austin/council_district:2
    Handles numbers, letters, directionals, and abbreviations like 'dist.'.
    If roman numerals are present, they are converted to integers (e.g. Ward III -> ward:3).
    """
    ROMAN_NUMERAL_MAP = {
        "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10,
        "xi": 11, "xii": 12, "xiii": 13, "xiv": 14, "xv": 15, "xvi": 16, "xvii": 17, "xviii": 18, "xix": 19, "xx": 20
    }
    NUMBER_MAP = {
        "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
        "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
        "eleven": "11", "twelve": "12", "thirteen": "13", "fourteen": "14", "fifteen": "15",
        "sixteen": "16", "seventeen": "17", "eighteen": "18", "nineteen": "19", "twenty": "20"
    }
    city_key = city_name_to_place_key(tr.get("city_name", ""))
    office = tr.get("role", "") or tr.get("office", "") or ""
    # Try to find a ward or district/council district, including 'dist.' abbreviation
    m = re.search(r"\b(ward|district|dist\.?)\s*[-:]?\s*([A-Za-z0-9\-]+)\b", office, re.IGNORECASE)
    if m and city_key:
        kind = m.group(1).lower().replace('.', '')
        value = m.group(2).lower().replace(" ", "_")
        value = ROMAN_NUMERAL_MAP.get(value, value)  # Convert roman numeral to int if applicable
        value = NUMBER_MAP.get(value, value)  # Convert number word to digit if applicable

        if kind == "ward":
            divtype = "ward"
        else:
            divtype = "council_district"
        # Example: ocd-division/country:us/state:tx/place:austin/ward:1
        return f"ocd-division/country:us/state:tx/{city_key}/{divtype}:{value}"
    return f"ocd-division/country:us/state:tx/{city_key}" if city_key else ""


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def run_validation(yaml_dir: str, tml_file: str, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)

    print("Loading civicpatch YAML data...")
    all_yaml = load_yaml_people(yaml_dir)
    print(f"  Loaded {len(all_yaml)} total YAML records")

    print("Loading TML scraped data...")
    tml_records = load_tml_records(tml_file)
    print(f"  Loaded {len(tml_records)} TML records")

    # Filter YAML to place: jurisdictions only
    civicpatch_places = [p for p in all_yaml if get_yaml_place_ocdid(p)]
    print(f"  YAML after place: filter: {len(civicpatch_places)}")

    # Group YAML by jurisdiction for reporting
    yaml_by_jur: dict[str, list[dict]] = defaultdict(list)
    for p in civicpatch_places:
        yaml_by_jur[place_key_from_ocdid(get_yaml_place_ocdid(p))].append(p)

    # Build TML index by jurisdiction and name
    tml_index_by_jur = build_tml_name_index_by_jur(tml_records)

    # --- Match ---
    matched_pairs   = []   # (yaml_person, tml_record)
    unmatched_yaml  = []
    matched_tml_names_by_jur = defaultdict(set)

    for yp in civicpatch_places:
        jur_key = place_key_from_ocdid(get_yaml_place_ocdid(yp))
        key = normalize_name(yp.get("name", ""))
        candidates = tml_index_by_jur.get(jur_key, {}).get(key, [])
        if candidates:
            tr = best_tml_match(yp, candidates)
            matched_pairs.append((yp, tr))
            matched_tml_names_by_jur[jur_key].add(key)
        else:
            unmatched_yaml.append(yp)

    # Find unmatched TML names by jurisdiction
    unmatched_tml_names_by_jur = defaultdict(set)
    for jur_key, name_dict in tml_index_by_jur.items():
        for name in name_dict:
            if name not in matched_tml_names_by_jur[jur_key]:
                unmatched_tml_names_by_jur[jur_key].add(name)

    # --- Compare phones for each matched pair ---
    global_stats = {
        "present_yaml": 0,
        "present_tml":  0,
        "both":         0,
        "match":        0,
    }

    jur_stats: dict[str, dict] = defaultdict(lambda: {
        "yaml_count":   0,
        "tml_matched":  0,
        "present_yaml": 0,
        "present_tml":  0,
        "both":         0,
        "match":        0,
    })

    mismatch_rows = []

    for yp in civicpatch_places:
        jur_key = place_key_from_ocdid(get_yaml_place_ocdid(yp))
        jur_stats[jur_key]["yaml_count"] += 1

    for yp, tr in matched_pairs:
        jur_key = place_key_from_ocdid(get_yaml_place_ocdid(yp))
        jur_stats[jur_key]["tml_matched"] += 1

        y_phones = [p for p in (yp.get("phones") or []) if p]
        t_phone  = tr.get("phone")
        t_phones = [t_phone] if t_phone else []

        present_yaml = bool(y_phones)
        present_tml  = bool(t_phones)
        both         = present_yaml and present_tml
        match        = phones_overlap(y_phones, t_phones) if both else False

        for d in (global_stats, jur_stats[jur_key]):
            d["present_yaml"] += int(present_yaml)
            d["present_tml"]  += int(present_tml)
            d["both"]         += int(both)
            d["match"]        += int(match)

        if both and not match:
            mismatch_rows.append({
                "jurisdiction":    jur_key,
                "name":            yp.get("name"),
                "field":           "phones",
                "value_civicpatch": "; ".join(y_phones),
                "value_tml":       t_phone or "",
            })

        # --- Division mismatch check ---
        yaml_div = (yp.get("office") or {}).get("division_ocdid", "")
        tml_div = tml_division_ocdid(tr)
        if yaml_div and tml_div and yaml_div != tml_div:
            mismatch_rows.append({
                "jurisdiction":    jur_key,
                "name":            yp.get("name"),
                "field":           "division_ocdid",
                "value_civicpatch": yaml_div,
                "value_tml":       tml_div,
            })

    # Combine unmatched CivicPatch and TML people into one CSV
    combined_unmatched = []

    # Unmatched CivicPatch people
    for yp in unmatched_yaml:
        jur_key = place_key_from_ocdid(get_yaml_place_ocdid(yp))
        combined_unmatched.append({
            "jurisdiction": jur_key,
            "name": yp.get("name", ""),
            "office": (yp.get("office") or {}).get("title", ""),
            "city_name": "",
            "source_file": yp.get("_source_file", ""),
            "source": "civicpatch",
        })

    # Unmatched TML people
    for jur_key, name_set in unmatched_tml_names_by_jur.items():
        for name in name_set:
            for tr in tml_index_by_jur[jur_key][name]:
                combined_unmatched.append({
                    "jurisdiction": jur_key,
                    "name": tr.get("name", ""),
                    "office": tr.get("office", ""),
                    "city_name": tr.get("city_name", ""),
                    "source_file": "",
                    "tml_city_profile": tr.get("city_url", ""),
                    "division_ocdid": tml_division_ocdid(tr),
                    "source": "tml",
                })

    # Sort combined_unmatched by jurisdiction, then by name
    combined_unmatched.sort(key=lambda row: (row["jurisdiction"], row["name"]))

    unmatched_combined_csv = os.path.join(out_dir, "unmatched_people_by_jurisdiction.csv")
    with open(unmatched_combined_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "jurisdiction", "name", "office", "city_name", "source_file", "tml_city_profile", "division_ocdid", "source"
        ])
        writer.writeheader()
        for row in combined_unmatched:
            writer.writerow(row)

    # -----------------------------------------------------------------------
    # Write CSVs
    # -----------------------------------------------------------------------

    # per_jurisdiction.csv (now only name matching)
    all_jurs = sorted(yaml_by_jur.keys())
    jur_csv_rows = []
    for jur in all_jurs:
        s = jur_stats[jur]
        jur_csv_rows.append({
            "jurisdiction":   jur,
            "yaml_count":     s["yaml_count"],      # total civicpatch people in this jurisdiction
            "tml_matched":    s["tml_matched"],     # number of those with a name match in TML
            "unmatched_yaml": s["yaml_count"] - s["tml_matched"],
        })

    jur_csv = os.path.join(out_dir, "per_jurisdiction.csv")
    with open(jur_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["jurisdiction", "yaml_count", "tml_matched", "unmatched_yaml"])
        writer.writeheader()
        writer.writerows(jur_csv_rows)

    # per_field.csv
    s = global_stats
    pct = f"{s['match']/s['both']*100:.1f}%" if s["both"] else "N/A"
    field_csv = os.path.join(out_dir, "per_field.csv")
    with open(field_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "field", "present_in_yaml", "present_in_tml",
            "both_present", "matched", "match_pct"
        ])
        writer.writeheader()
        writer.writerow({
            "field":           "phones",
            "present_in_yaml": s["present_yaml"],
            "present_in_tml":  s["present_tml"],
            "both_present":    s["both"],
            "matched":         s["match"],
            "match_pct":       pct,
        })

    # mismatches.csv
    mismatch_csv = os.path.join(out_dir, "mismatches.csv")
    with open(mismatch_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "jurisdiction", "name", "field", "value_civicpatch", "value_tml"
        ])
        writer.writeheader()
        writer.writerows(mismatch_rows)

    # -----------------------------------------------------------------------
    # Write text report
    # -----------------------------------------------------------------------

    report_path = os.path.join(out_dir, "report.txt")
    lines = []

    def w(line=""):
        lines.append(line)
        print(line)

    total_matched     = len(matched_pairs)
    total_unmatched_y = len(unmatched_yaml)
    total_unmatched_t = len(unmatched_tml_names_by_jur)
    # Calculate TML-side match rate for people in shared jurisdictions
    matched_tml_count = 0
    total_tml_people_in_shared = 0
    # Build set of matched last names per jurisdiction from CivicPatch
    matched_names_by_jur = defaultdict(set)
    for yp, tr in matched_pairs:
        jur_key = place_key_from_ocdid(get_yaml_place_ocdid(yp))
        matched_names_by_jur[jur_key].add(normalize_name(yp.get("name", "")))

    shared_jurs = set(yaml_by_jur.keys()) & {city_name_to_place_key(tr.get("city_name", "")) for tr in tml_records}
    for jur in shared_jurs:
        # Get all TML people in this jurisdiction
        tml_people = [tr for tr in tml_records if city_name_to_place_key(tr.get("city_name", "")) == jur]
        total_tml_people_in_shared += len(tml_people)
        for tr in tml_people:
            if normalize_name(tr.get("name", "")) in matched_names_by_jur[jur]:
                matched_tml_count += 1

    match_rate_tml = (matched_tml_count / total_tml_people_in_shared * 100) if total_tml_people_in_shared else 0
    shared_match_rate = (total_matched / sum(jur_stats[jur]["yaml_count"] for jur in shared_jurs) * 100) if shared_jurs else 0

    # Calculate shared match rate (all people in shared jurisdictions)
    shared_civicpatch_count = sum(jur_stats[jur]["yaml_count"] for jur in shared_jurs)
    shared_tml_count = sum(len([tr for tr in tml_records if city_name_to_place_key(tr.get("city_name", "")) == jur]) for jur in shared_jurs)
    shared_total_people = shared_civicpatch_count + shared_tml_count - total_matched  # subtract matched pairs (counted in both)
    shared_match_rate_overall = (total_matched / shared_total_people * 100) if shared_total_people else 0

    # 1. CivicPatch match rate (all jurisdictions)
    total_civicpatch_people = len(civicpatch_places)
    civicpatch_side_match_rate = (len(matched_pairs) / total_civicpatch_people * 100) if total_civicpatch_people else 0

    # 2. TML match rate (all jurisdictions)
    total_tml_people = len(tml_records)
    matched_tml_people = 0
    for jur_key, name_dict in tml_index_by_jur.items():
        for name in name_dict:
            if name in matched_tml_names_by_jur[jur_key]:
                matched_tml_people += len(name_dict[name])
    tml_side_match_rate = (matched_tml_people / total_tml_people * 100) if total_tml_people else 0

    # 3. CivicPatch match rate (shared jurisdictions)
    shared_jurs = set(yaml_by_jur.keys()) & {city_name_to_place_key(tr.get("city_name", "")) for tr in tml_records}
    shared_civicpatch_count = sum(jur_stats[jur]["yaml_count"] for jur in shared_jurs)
    shared_match_rate_civicpatch = (total_matched / shared_civicpatch_count * 100) if shared_civicpatch_count else 0

    # 4. TML match rate (shared jurisdictions)
    matched_tml_count = 0
    total_tml_people_in_shared = 0
    matched_names_by_jur = defaultdict(set)
    for yp, tr in matched_pairs:
        jur_key = place_key_from_ocdid(get_yaml_place_ocdid(yp))
        matched_names_by_jur[jur_key].add(normalize_name(yp.get("name", "")))
    for jur in shared_jurs:
        tml_people = [tr for tr in tml_records if city_name_to_place_key(tr.get("city_name", "")) == jur]
        total_tml_people_in_shared += len(tml_people)
        for tr in tml_people:
            if normalize_name(tr.get("name", "")) in matched_names_by_jur[jur]:
                matched_tml_count += 1
    shared_match_rate_tml = (matched_tml_count / total_tml_people_in_shared * 100) if total_tml_people_in_shared else 0

    # 5. Overall shared match rate (all people in shared jurisdictions)
    shared_tml_count = sum(len([tr for tr in tml_records if city_name_to_place_key(tr.get("city_name", "")) == jur]) for jur in shared_jurs)
    shared_total_people = shared_civicpatch_count + shared_tml_count - total_matched  # subtract matched pairs (counted in both)
    shared_match_rate_overall = (total_matched / shared_total_people * 100) if shared_total_people else 0

    # Write summary section with clear labels and explanation
    w("=" * 70)
    w("MATCH RATES SUMMARY")
    w("=" * 70)
    w()
    w(f"CivicPatch match rate (all jurisdictions):         {civicpatch_side_match_rate:.1f}%")
    w(f"TML match rate (all jurisdictions):                {tml_side_match_rate:.1f}%")
    w(f"CivicPatch match rate (shared jurisdictions):      {shared_match_rate_civicpatch:.1f}%")
    w(f"TML match rate (shared jurisdictions):             {shared_match_rate_tml:.1f}%")
    w(f"Overall match rate (shared jurisdictions):         {shared_match_rate_overall:.1f}%")
    w()
    w("Explanation:")
    w('- "CivicPatch match rate" is the percent of CivicPatch people matched to TML.')
    w('- "TML match rate" is the percent of TML people matched to CivicPatch.')
    w('- "Shared jurisdictions" means cities/towns present in both datasets.')
    w('- "Overall match rate (shared jurisdictions)" is the percent of all people in shared jurisdictions who are matched (matched pairs divided by total unique people in those jurisdictions).')

    w("=" * 70)
    w("DATA VALIDATION REPORT  (civicpatch vs TML)")
    w("Scope: place: jurisdictions only | Field compared: phone")
    w("=" * 70)
    w()
    w(f"Source A (civicpatch YAML):  {len(civicpatch_places):>5} people")
    w(f"Source B (TML scraped):      {len(tml_records):>5} people")
    w()
    w("-" * 70)
    w("NAME MATCHING")
    w("-" * 70)
    w(f"Matched pairs:                        {total_matched:>5}")
    w(f"civicpatch people with no TML match:  {total_unmatched_y:>5}")
    w(f"TML people with no civicpatch match:  {total_unmatched_t:>5}")
    w()
    w("-" * 70)
    w("PHONE MATCH SUMMARY  (matched pairs only)")
    w("-" * 70)
    w(f"{'Field':<20} {'In YAML':>8} {'In TML':>8} {'Both':>8} {'Match':>8} {'Match%':>8}")
    w("-" * 70)
    w(f"{'phones':<20} {s['present_yaml']:>8} {s['present_tml']:>8} "
      f"{s['both']:>8} {s['match']:>8} {pct:>8}")
    w()
    w(f"Total phone mismatches: {len(mismatch_rows)}")
    w()
    w("-" * 70)
    w("PER-JURISDICTION SUMMARY (name matching only)")
    w("-" * 70)
    w(f"{'Jurisdiction':<35} {'YAML':>5} {'TML':>5} {'!Match':>7} {'Diff':>5}")
    w("-" * 70)
    for row in jur_csv_rows:
        diff_mark = "*" if row['yaml_count'] != row['tml_matched'] else ""
        w(f"{row['jurisdiction']:<35} {row['yaml_count']:>5} {row['tml_matched']:>5} {row['unmatched_yaml']:>7} {diff_mark:>5}")
    w()
    w("-" * 70)
    w("JURISDICTION COMPARISON")
    w("-" * 70)
    civicpatch_jurs = set(yaml_by_jur.keys())
    tml_jurs = set()
    for tr in tml_records:
        jur_key = city_name_to_place_key(tr.get("city_name", ""))
        if jur_key:
            tml_jurs.add(jur_key)

    only_civicpatch = sorted(civicpatch_jurs - tml_jurs)
    only_tml = sorted(tml_jurs - civicpatch_jurs)

    w(f"Jurisdictions data present in CivicPatch but not TML (count: {len(only_civicpatch)}); civicpatch total count: {len(civicpatch_jurs)}:")
    for jur in only_civicpatch:
        w(f"  {jur}")
    w()
    w(f"Jurisdictions data present in TML but not CivicPatch (count: {len(only_tml)}); tml total count: {len(tml_jurs)}:")
    for jur in only_tml:
        w(f"  {jur}")
    w()
    w("=" * 70)
    w("OUTPUT FILES")
    w("=" * 70)
    w(f"  {report_path}")
    w(f"  {field_csv}")
    w(f"  {jur_csv}")
    w(f"  {mismatch_csv}")
    w(f"  {unmatched_combined_csv}")

    jurisdictions_file = os.path.join("data_source", "tx", "jurisdictions.yml")
    with open(jurisdictions_file, "r", encoding="utf-8") as f:
        jurisdictions_data = yaml.safe_load(f)
    jurisdiction_data = jurisdictions_data.get("jurisdictions", [])
    civicpatch_jurisdiction_ocdids = [j.get("id") for j in jurisdiction_data]
    tml_jurisdiction_ocdids = set()
    for tr in tml_records:
        jur_key = city_name_to_jurisdiction_ocdid(tr.get("city_name", ""))
        if jur_key:
            tml_jurisdiction_ocdids.add(jur_key)
    civicpatch_diff = set(civicpatch_jurisdiction_ocdids) - tml_jurisdiction_ocdids
    tml_diff = tml_jurisdiction_ocdids - set(civicpatch_jurisdiction_ocdids)
    w(f"\nJurisdiction OCD-IDs present in CivicPatch index but not TML index (count: {len(civicpatch_diff)}):")
    w(f"  " + "\n  ".join(sorted(civicpatch_diff)))
    w(f"\nJurisdiction OCD-IDs present in TML index but not CivicPatch index (count: {len(tml_diff)}):")
    w(f"  " + "\n  ".join(sorted(tml_diff)))

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Validate TML scraped data against civicpatch YAML files"
    )
    parser.add_argument(
        "--tml-file", required=True,
        help="Path to tml_raw.json produced by scrape_tml_search.py"
    )
    parser.add_argument(
        "--yaml-dir", required=True,
        help="Directory containing place_* YAML files (e.g. data/tx/local)"
    )
    parser.add_argument(
        "--out-dir", default="validation_output_tml",
        help="Directory to write output files (default: validation_output_tml)"
    )
    args = parser.parse_args()

    if not os.path.isfile(args.tml_file):
        print(f"ERROR: --tml-file '{args.tml_file}' not found.", file=sys.stderr)
        sys.exit(1)
    if not os.path.isdir(args.yaml_dir):
        print(f"ERROR: --yaml-dir '{args.yaml_dir}' not found.", file=sys.stderr)
        sys.exit(1)

    run_validation(args.yaml_dir, args.tml_file, args.out_dir)


if __name__ == "__main__":
    main()
