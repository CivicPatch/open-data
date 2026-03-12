"""
validate_officials.py

Compares local YAML people files (data/tx/local/place_*) against
a processed JSON file (scripts/track_progress/google_data/tx_all_processed.json)

Usage:
    python validate_officials.py \
        --yaml-dir data/tx/local \
        --json-file scripts/track_progress/google_data/tx_all_processed.json \
        --out-dir validation_output

Outputs:
    validation_output/report.txt            — human-readable summary
    validation_output/per_field.csv         — per-field match rates across all matched people
    validation_output/per_jurisdiction.csv  — per-jurisdiction breakdown
    validation_output/mismatches.csv        — detail of every field mismatch
    validation_output/name_mismatches.csv   — detail of every person with no name match
"""

import argparse
import csv
import glob
import json
import os
import re
import sys
from collections import defaultdict

import yaml


# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------

STRIP_TOKENS = {
    # suffixes
    "jr", "sr", "ii", "iii", "iv", "v",
    # titles
    "dr", "mr", "mrs", "ms", "miss", "prof",
    "hon", "rev", "esq", "phd", "md", "dds",
}


def normalize_name(name: str) -> str:
    if not name:
        return ""
    name = name.strip().lower()
    # remove punctuation like periods and commas
    name = re.sub(r"[.,]", "", name)
    parts = [p for p in name.split() if p not in STRIP_TOKENS]
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Field normalization
# ---------------------------------------------------------------------------

def normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone) if phone else ""


def normalize_url(url: str) -> str:
    return url.strip().rstrip("/").lower() if url else ""


def normalize_email(email: str) -> str:
    return email.strip().lower() if email else ""


def normalize_scalar(val) -> str:
    return str(val).strip().lower() if val is not None else ""


def list_overlap(list_a, list_b, normalize_fn) -> bool:
    """True if any normalized element in list_a appears in list_b."""
    set_a = {normalize_fn(x) for x in (list_a or []) if x}
    set_b = {normalize_fn(x) for x in (list_b or []) if x}
    return bool(set_a & set_b)


def scalar_match(a, b) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return normalize_scalar(a) == normalize_scalar(b)


def office_name_match(a, b) -> bool:
    """
    True if either office name's words are a subset of the other's.
    e.g. "Mayor" vs "Mayor of Austin"  -> True
         "Council Member" vs "City Council Member" -> True
         "Mayor" vs "Council Member" -> False
    """
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    words_a = set(normalize_scalar(a).split())
    words_b = set(normalize_scalar(b).split())
    return words_a <= words_b or words_b <= words_a


# ---------------------------------------------------------------------------
# OCD-ID helpers
# ---------------------------------------------------------------------------

def is_place_ocdid(ocdid: str) -> bool:
    return bool(ocdid and re.search(r"/place:[^/]+$", ocdid))


def place_key_from_ocdid(ocdid: str) -> str:
    """Return the trailing place:xxx segment as a short key."""
    m = re.search(r"(place:[^/]+?)(?:/|$)", ocdid or "")
    return m.group(1) if m else (ocdid or "unknown")


def get_yaml_place_ocdid(person: dict) -> str | None:
    """
    Look for a place: ocdid in:
      - person['office']['division_ocdid']
      - person['jurisdiction_ocdid']
    Returns the first matching value, or None.
    """
    office = person.get("office") or {}
    for candidate in [office.get("division_ocdid"), person.get("jurisdiction_ocdid")]:
        if candidate and is_place_ocdid(candidate):
            return candidate
    # jurisdiction_ocdid may end in /government but still contain place:
    jid = person.get("jurisdiction_ocdid") or ""
    if "/place:" in jid:
        m = re.search(r"(ocd-[^/]+(?:/[^/]+)*?/place:[^/]+)", jid)
        if m:
            return m.group(1)
    return None


def get_json_place_ocdid(person: dict) -> str | None:
    div = person.get("office_divisionId") or ""
    if is_place_ocdid(div):
        return div
    if "/place:" in div:
        m = re.search(r"(ocd-[^/]+(?:/[^/]+)*?/place:[^/]+)", div)
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


def load_json_people(json_file: str) -> list[dict]:
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


# ---------------------------------------------------------------------------
# Field extraction
# ---------------------------------------------------------------------------

FIELD_ORDER = ["phones", "emails", "urls", "start_date", "end_date", "office_name", "division_ocdid"]
LIST_FIELDS  = {"phones", "emails", "urls"}
SCALAR_FIELDS = {"start_date", "end_date", "office_name", "division_ocdid"}


def yaml_fields(person: dict) -> dict:
    office = person.get("office") or {}
    return {
        "name":           person.get("name"),
        "phones":         person.get("phones") or [],
        "emails":         person.get("emails") or [],
        "urls":           person.get("urls") or [],
        "start_date":     person.get("start_date"),
        "end_date":       person.get("end_date"),
        "office_name":    office.get("name"),
        "division_ocdid": office.get("division_ocdid"),
    }


def json_fields(person: dict) -> dict:
    return {
        "name":           person.get("name"),
        "phones":         person.get("phones") or [],
        "emails":         person.get("emails") or [],
        "urls":           person.get("urls") or [],
        "start_date":     person.get("start_date"),
        "end_date":       person.get("end_date"),
        "office_name":    person.get("office_name"),
        "division_ocdid": person.get("office_divisionId"),
    }


# ---------------------------------------------------------------------------
# Field comparison
# ---------------------------------------------------------------------------

NORMALIZE_MAP = {
    "phones": normalize_phone,
    "emails": normalize_email,
    "urls":   normalize_url,
}


def compare_fields(yf: dict, jf: dict) -> dict:
    """
    Returns a dict keyed by field name, each value being:
      { present_a, present_b, both_present, match, val_a, val_b }
    """
    results = {}
    for field in FIELD_ORDER:
        a_val = yf.get(field)
        b_val = jf.get(field)

        if field in LIST_FIELDS:
            present_a   = bool(a_val)
            present_b   = bool(b_val)
            both        = present_a and present_b
            match       = list_overlap(a_val, b_val, NORMALIZE_MAP[field]) if both else False
        elif field == "office_name":
            present_a   = a_val is not None and str(a_val).strip() != ""
            present_b   = b_val is not None and str(b_val).strip() != ""
            both        = present_a and present_b
            match       = office_name_match(a_val, b_val) if both else False
        else:
            present_a   = a_val is not None and str(a_val).strip() != ""
            present_b   = b_val is not None and str(b_val).strip() != ""
            both        = present_a and present_b
            match       = scalar_match(a_val, b_val) if both else False

        results[field] = {
            "present_a":    present_a,
            "present_b":    present_b,
            "both_present": both,
            "match":        match,
            "val_a":        a_val,
            "val_b":        b_val,
        }
    return results


# ---------------------------------------------------------------------------
# Main validation
# ---------------------------------------------------------------------------

def run_validation(yaml_dir: str, json_file: str, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)

    print("Loading YAML people...")
    all_yaml = load_yaml_people(yaml_dir)
    print(f"  Loaded {len(all_yaml)} total YAML records")

    print("Loading JSON people...")
    all_json = load_json_people(json_file)
    print(f"  Loaded {len(all_json)} total JSON records")

    # Filter to place: jurisdictions only
    yaml_place = [p for p in all_yaml if get_yaml_place_ocdid(p)]
    json_place = [p for p in all_json if get_json_place_ocdid(p)]
    print(f"  After place: filter — YAML: {len(yaml_place)}, JSON: {len(json_place)}")

    # Group by jurisdiction key
    yaml_by_jur: dict[str, list[dict]] = defaultdict(list)
    for p in yaml_place:
        yaml_by_jur[place_key_from_ocdid(get_yaml_place_ocdid(p))].append(p)

    json_by_jur: dict[str, list[dict]] = defaultdict(list)
    for p in json_place:
        json_by_jur[place_key_from_ocdid(get_json_place_ocdid(p))].append(p)

    all_yaml_jurs = set(yaml_by_jur.keys())
    all_json_jurs = set(json_by_jur.keys())
    jurs_only_yaml = all_yaml_jurs - all_json_jurs
    jurs_only_json = all_json_jurs - all_yaml_jurs
    jurs_in_both   = all_yaml_jurs & all_json_jurs

    # Accumulators
    total_matched        = 0
    total_unmatched_yaml = 0
    total_unmatched_json = 0

    global_field_stats = {
        f: {"present_a": 0, "present_b": 0, "both_present": 0, "match": 0}
        for f in FIELD_ORDER
    }

    jur_rows      = []
    mismatch_rows = []

    for jur in sorted(jurs_in_both):
        y_people = yaml_by_jur[jur]
        j_people = json_by_jur[jur]

        # Build name lookup for JSON side
        j_by_name: dict[str, dict] = {}
        for jp in j_people:
            j_by_name[normalize_name(jp.get("name", ""))] = jp

        matched_pairs  = []
        unmatched_yaml = []
        unmatched_json = set(j_by_name.keys())

        for yp in y_people:
            key = normalize_name(yp.get("name", ""))
            if key in j_by_name:
                matched_pairs.append((yp, j_by_name[key]))
                unmatched_json.discard(key)
            else:
                unmatched_yaml.append(yp)

        total_matched        += len(matched_pairs)
        total_unmatched_yaml += len(unmatched_yaml)
        total_unmatched_json += len(unmatched_json)

        jur_field_stats = {
            f: {"present_a": 0, "present_b": 0, "both_present": 0, "match": 0}
            for f in FIELD_ORDER
        }

        for yp, jp in matched_pairs:
            field_results = compare_fields(yaml_fields(yp), json_fields(jp))
            for field, res in field_results.items():
                for stat in ("present_a", "present_b", "both_present", "match"):
                    jur_field_stats[field][stat]    += int(res[stat])
                    global_field_stats[field][stat] += int(res[stat])
                if res["both_present"] and not res["match"]:
                    mismatch_rows.append({
                        "jurisdiction": jur,
                        "name":         yp.get("name"),
                        "field":        field,
                        "value_yaml":   str(res["val_a"]),
                        "value_json":   str(res["val_b"]),
                    })

        row = {
            "jurisdiction":   jur,
            "yaml_count":     len(y_people),
            "json_count":     len(j_people),
            "matched_people": len(matched_pairs),
            "unmatched_yaml": len(unmatched_yaml),
            "unmatched_json": len(unmatched_json),
        }
        for field in FIELD_ORDER:
            s = jur_field_stats[field]
            row[f"{field}_match"] = s["match"]
            row[f"{field}_both"]  = s["both_present"]
            row[f"{field}_pct"]   = (
                f"{s['match']/s['both_present']*100:.1f}%"
                if s["both_present"] else "N/A"
            )
        jur_rows.append(row)

    # Add jurisdiction-only rows
    for jur in sorted(jurs_only_yaml):
        row = {
            "jurisdiction": jur, "yaml_count": len(yaml_by_jur[jur]),
            "json_count": 0, "matched_people": 0,
            "unmatched_yaml": len(yaml_by_jur[jur]), "unmatched_json": 0,
        }
        for f in FIELD_ORDER:
            row[f"{f}_match"] = 0; row[f"{f}_both"] = 0; row[f"{f}_pct"] = "N/A"
        jur_rows.append(row)

    for jur in sorted(jurs_only_json):
        row = {
            "jurisdiction": jur, "yaml_count": 0,
            "json_count": len(json_by_jur[jur]), "matched_people": 0,
            "unmatched_yaml": 0, "unmatched_json": len(json_by_jur[jur]),
        }
        for f in FIELD_ORDER:
            row[f"{f}_match"] = 0; row[f"{f}_both"] = 0; row[f"{f}_pct"] = "N/A"
        jur_rows.append(row)

    jur_rows.sort(key=lambda r: r["jurisdiction"])

    # -----------------------------------------------------------------------
    # Write CSVs
    # -----------------------------------------------------------------------

    jur_csv = os.path.join(out_dir, "per_jurisdiction.csv")
    jur_fieldnames = [
        "jurisdiction", "yaml_count", "json_count",
        "matched_people", "unmatched_yaml", "unmatched_json",
    ]
    for f in FIELD_ORDER:
        jur_fieldnames += [f"{f}_match", f"{f}_both", f"{f}_pct"]
    with open(jur_csv, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=jur_fieldnames)
        writer.writeheader()
        writer.writerows(jur_rows)

    field_csv = os.path.join(out_dir, "per_field.csv")
    with open(field_csv, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "field", "present_in_yaml", "present_in_json",
            "both_present", "matched", "match_pct"
        ])
        writer.writeheader()
        for field in FIELD_ORDER:
            s = global_field_stats[field]
            pct = f"{s['match']/s['both_present']*100:.1f}%" if s["both_present"] else "N/A"
            writer.writerow({
                "field":           field,
                "present_in_yaml": s["present_a"],
                "present_in_json": s["present_b"],
                "both_present":    s["both_present"],
                "matched":         s["match"],
                "match_pct":       pct,
            })

    mismatch_csv = os.path.join(out_dir, "mismatches.csv")
    with open(mismatch_csv, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "jurisdiction", "name", "field", "value_yaml", "value_json"
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

    w("=" * 70)
    w("DATA VALIDATION REPORT")
    w("Scope: place: jurisdictions only")
    w("=" * 70)
    w()
    w(f"Source A (YAML):  {len(yaml_place):>5} people across {len(all_yaml_jurs):>3} place: jurisdictions")
    w(f"Source B (JSON):  {len(json_place):>5} people across {len(all_json_jurs):>3} place: jurisdictions")
    w()
    w(f"Jurisdictions in both:       {len(jurs_in_both)}")
    w(f"Jurisdictions only in YAML:  {len(jurs_only_yaml)}")
    for j in sorted(jurs_only_yaml):
        w(f"    {j}  ({len(yaml_by_jur[j])} people)")
    w(f"Jurisdictions only in JSON:  {len(jurs_only_json)}")
    for j in sorted(jurs_only_json):
        w(f"    {j}  ({len(json_by_jur[j])} people)")
    w()
    w("-" * 70)
    w("NAME MATCHING  (within shared jurisdictions)")
    w("-" * 70)
    total_yaml_shared = sum(len(yaml_by_jur[j]) for j in jurs_in_both)
    total_json_shared = sum(len(json_by_jur[j]) for j in jurs_in_both)
    w(f"YAML people in shared jurisdictions:  {total_yaml_shared}")
    w(f"JSON people in shared jurisdictions:  {total_json_shared}")
    w(f"Matched pairs (name match):           {total_matched}")
    match_pct = total_matched / max(total_yaml_shared, 1) * 100
    w(f"Match rate (vs YAML):                 {match_pct:.1f}%")
    w(f"YAML people with no JSON match:       {total_unmatched_yaml}")
    w(f"JSON people with no YAML match:       {total_unmatched_json}")
    w()
    w("-" * 70)
    w("FIELD MATCH SUMMARY  (matched pairs only)")
    w("-" * 70)
    w(f"{'Field':<20} {'In YAML':>8} {'In JSON':>8} {'Both':>8} {'Match':>8} {'Match%':>8}")
    w("-" * 70)
    for field in FIELD_ORDER:
        s = global_field_stats[field]
        pct = f"{s['match']/s['both_present']*100:.1f}%" if s["both_present"] else "N/A"
        w(f"{field:<20} {s['present_a']:>8} {s['present_b']:>8} "
          f"{s['both_present']:>8} {s['match']:>8} {pct:>8}")
    w()
    w(f"Total field mismatches logged:  {len(mismatch_rows)}")
    w()
    w("-" * 70)
    w("PER-JURISDICTION SUMMARY")
    w("-" * 70)
    w(f"{'Jurisdiction':<35} {'YAML':>5} {'JSON':>5} {'Matched':>8} {'!YAML':>6} {'!JSON':>6}")
    w("-" * 70)
    for row in jur_rows:
        w(f"{row['jurisdiction']:<35} {row['yaml_count']:>5} {row['json_count']:>5} "
          f"{row['matched_people']:>8} {row['unmatched_yaml']:>6} {row['unmatched_json']:>6}")
    w()
    w("=" * 70)
    w("OUTPUT FILES")
    w("=" * 70)
    w(f"  {report_path}")
    w(f"  {field_csv}")
    w(f"  {jur_csv}")
    w(f"  {mismatch_csv}")

    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    return report_path, field_csv, jur_csv, mismatch_csv


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Validate YAML officials against Google civic JSON data"
    )
    parser.add_argument(
        "--yaml-dir", required=True,
        help="Directory containing place_* YAML files (e.g. data/tx/local)"
    )
    parser.add_argument(
        "--json-file", required=True,
        help="Path to tx_all_processed.json"
    )
    parser.add_argument(
        "--out-dir", default="validation_output",
        help="Directory to write output files (default: validation_output)"
    )
    args = parser.parse_args()

    if not os.path.isdir(args.yaml_dir):
        print(f"ERROR: --yaml-dir '{args.yaml_dir}' not found.", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(args.json_file):
        print(f"ERROR: --json-file '{args.json_file}' not found.", file=sys.stderr)
        sys.exit(1)

    run_validation(args.yaml_dir, args.json_file, args.out_dir)


if __name__ == "__main__":
    main()