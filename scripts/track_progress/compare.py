"""
compare.py  —  compare CP local YMLs against Google external source

Usage:
    python compare.py <state>
    python compare.py <local_dir> <jurisdictions.yml> <external.yaml> <google_raw.json> <output.json> <state>

Example:
    python compare.py tx
"""

import json
import sys
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

from shared.utils.name_utils import normalize_name
from shared.utils.phone_utils import normalize_phone_number
from shared.utils.email_utils import normalize_email


VACANCY_NAMES = {"position vacant", "vacant", "vacancy"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_vacant(name: str) -> bool:
    return normalize_name(name) in VACANCY_NAMES


def record_summary(r):
    if r is None:
        return None
    return {
        "role":     (r.get("office") or {}).get("name"),
        "division": (r.get("office") or {}).get("division_ocdid"),
        "phones":   r.get("phones") or [],
        "emails":   r.get("emails") or [],
        "urls":     r.get("urls") or [],
    }


# ── Field comparison ──────────────────────────────────────────────────────────

def compare_fields(cp: dict, ext: dict) -> dict:
    """
    Compare fields only when both sides have a value.
    Returns dict of field -> (cp_value, ext_value) for fields that differ.
    """
    diffs = {}

    cp_role  = (cp.get("office") or {}).get("name")
    ext_role = (ext.get("office") or {}).get("name")
    if cp_role and ext_role and cp_role != ext_role:
        diffs["role"] = (cp_role, ext_role)

    cp_div  = (cp.get("office") or {}).get("division_ocdid")
    ext_div = (ext.get("office") or {}).get("division_ocdid")
    if cp_div and ext_div and cp_div != ext_div:
        diffs["division"] = (cp_div, ext_div)

    cp_phone  = normalize_phone_number((cp.get("phones") or [None])[0])
    ext_phone = normalize_phone_number((ext.get("phones") or [None])[0])
    if cp_phone and ext_phone and cp_phone != ext_phone:
        diffs["phone"] = (cp_phone, ext_phone)

    cp_email  = normalize_email((cp.get("emails") or [None])[0])
    ext_email = normalize_email((ext.get("emails") or [None])[0])
    if cp_email and ext_email and cp_email != ext_email:
        diffs["email"] = (cp_email, ext_email)

    return diffs


# ── I/O ───────────────────────────────────────────────────────────────────────

def load_yaml(path):
    with open(path) as f:
        data = yaml.safe_load(f)
    if isinstance(data, dict) and "records" in data:
        return data["records"]
    return data if isinstance(data, list) else [data]


def to_place_jurisdiction(jid: str) -> str | None:
    """
    Normalize a jurisdiction ocdid to the /place: level.
    ocd-jurisdiction/country:us/state:tx/place:austin/council_district:5/government
    -> ocd-jurisdiction/country:us/state:tx/place:austin/government
    ocd-jurisdiction/country:us/state:tx/place:austin/government (already at place level)
    -> ocd-jurisdiction/country:us/state:tx/place:austin/government
    Returns None if no /place: segment found.
    """
    m = re.search(r"(ocd-jurisdiction/[^/]+/[^/]+/place:[^/]+)", jid)
    return m.group(1) + "/government" if m else None


def load_ext(path: str) -> tuple[list, set]:
    """
    Load external output.yml.
    Returns (records, ext_jurisdiction_ids) where ext_jurisdiction_ids
    comes from meta.jurisdictions if present, else derived from records.
    All jurisdiction IDs are normalized to the /place: level.
    """
    with open(path) as f:
        data = yaml.safe_load(f)

    if isinstance(data, dict) and "records" in data:
        records = data["records"]
        meta_jurisdictions = data.get("meta", {}).get("jurisdictions")
        raw_ids = set(meta_jurisdictions) if meta_jurisdictions else None
    else:
        records = data if isinstance(data, list) else [data]
        raw_ids = None

    if raw_ids is None:
        raw_ids = set(
            r["jurisdiction_ocdid"]
            for r in records
            if r.get("jurisdiction_ocdid")
        )

    # Normalize to place level, dropping hyper-local subdivisions
    ext_jurisdiction_ids = set(filter(None, (to_place_jurisdiction(j) for j in raw_ids)))

    return records, ext_jurisdiction_ids


def load_jurisdictions(path: str) -> dict:
    """
    Returns:
        { jurisdiction_ocdid: { "url": str | None, "scrapeable": bool } }
    """
    with open(path) as f:
        data = yaml.safe_load(f)

    items = data.get("jurisdictions", data) if isinstance(data, dict) else data

    result = {}
    for item in (items if isinstance(items, list) else [items]):
        jid = item.get("jurisdiction_ocdid") or item.get("id")
        if jid:
            urls = item.get("urls") or []
            url  = urls[0] if urls else item.get("url")
            result[jid] = {
                "url":        url,
                "scrapeable": bool(url),
            }
    return result


# ── Core ──────────────────────────────────────────────────────────────────────

def build_locality_entry(cp_records: list, ext_records: list, jurisdiction: str) -> dict:
    ext_by_name = {
        normalize_name(r["name"]): r
        for r in ext_records
        if not is_vacant(r.get("name", ""))
    }
    cp_by_name = {
        normalize_name(r["name"]): r
        for r in cp_records
        if not is_vacant(r.get("name", ""))
    }

    records = []
    for norm_name in sorted(set(cp_by_name) | set(ext_by_name)):
        cp  = cp_by_name.get(norm_name)
        ext = ext_by_name.get(norm_name)

        if cp and ext:
            field_diffs = compare_fields(cp, ext)
            match = "matched"
        elif cp:
            field_diffs = {}
            match = "only_civicpatch"
        else:
            field_diffs = {}
            match = "only_external"

        records.append({
            "name":            (cp or ext)["name"],
            "match":           match,
            "field_diffs":     field_diffs,
            "civicpatch_data": record_summary(cp),
            "ext_data":        record_summary(ext),
        })

    total_cp         = len(cp_by_name)
    total_ext        = len(ext_by_name)
    name_matched     = sum(1 for r in records if r["match"] == "matched")
    only_civicpatch  = sum(1 for r in records if r["match"] == "only_civicpatch")
    only_external    = sum(1 for r in records if r["match"] == "only_external")

    name_match_pct = round(name_matched / total_ext, 2) if total_ext else 0.0

    status = (
        "good"    if name_match_pct >= 0.8 else
        "partial" if name_match_pct >= 0.4 else
        "poor"    if total_cp > 0           else
        "missing"
    )

    place = re.search(r"/place:([^/]+)", jurisdiction)
    place = place.group(1) if place else jurisdiction

    return {
        "jurisdiction":     jurisdiction,
        "place":            place,
        "civicpatch_count": total_cp,
        "ext_count":        total_ext,
        "name_matched":     name_matched,
        "only_civicpatch":  only_civicpatch,
        "only_external":    only_external,
        "name_match_pct":   name_match_pct,
        "field_diffs": {
            "role":     sum(1 for r in records if "role"     in r["field_diffs"]),
            "division": sum(1 for r in records if "division" in r["field_diffs"]),
            "phone":    sum(1 for r in records if "phone"    in r["field_diffs"]),
            "email":    sum(1 for r in records if "email"    in r["field_diffs"]),
        },
        "status":     status,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "records":    records,
    }


# ── Run ───────────────────────────────────────────────────────────────────────

def load_coverage_since_reference(state: str) -> int:
    meta_path = f"data_source/{state}/jurisdictions_metadata.yml"
    try:
        with open(meta_path) as f:
            meta = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"WARNING: {meta_path} not found, skipping coverage_since_coverage_reference_date")
        return 0

    config = meta.get("config", {})
    ref_date_str = config.get("coverage_reference_date")
    if not ref_date_str:
        print(f"WARNING: coverage_reference_date not found in {meta_path}")
        return 0

    ref_date = datetime.fromisoformat(ref_date_str)
    jurisdictions = meta.get("jurisdictions_by_id", {})
    count = 0
    for j in jurisdictions.values():
        updated_at = j.get("updated_at")
        if updated_at and datetime.fromisoformat(updated_at) > ref_date:
            count += 1
    return count

def run(
    local_dir:          str,
    jurisdictions_path: str,
    ext_path:           str,
    out_path:           str,
    state:              str,
):
    # ── Load + validate jurisdictions ─────────────────────────────────────────
    jurisdictions          = load_jurisdictions(jurisdictions_path)
    known_count            = len(jurisdictions)
    scrapeable_count       = sum(1 for j in jurisdictions.values() if j["scrapeable"])
    known_jurisdiction_ids = set(jurisdictions.keys())

    # ── Load + validate CP YMLs ───────────────────────────────────────────────
    local_files = sorted(Path(local_dir).glob("*.yml")) + sorted(Path(local_dir).glob("*.yaml"))
    if not local_files:
        print(f"ERROR: no .yml files found in {local_dir}")
        sys.exit(1)

    cp_by_jurisdiction = {}
    for path in local_files:
        records      = load_yaml(path)
        jurisdiction = records[0].get("jurisdiction_ocdid") if records else None
        if not jurisdiction:
            print(f"ERROR: {path.name} has no jurisdiction_ocdid")
            sys.exit(1)
        if jurisdiction not in jurisdictions:
            print(f"ERROR: {path.name} jurisdiction not in jurisdictions.yml:")
            print(f"  {jurisdiction}")
            sys.exit(1)
        cp_by_jurisdiction[jurisdiction] = records

    # ── Load external YAML (records + known locality list from meta) ──────────
    ext_all, ext_known_jurisdiction_ids = load_ext(ext_path)
    state_prefix        = f"ocd-jurisdiction/country:us/state:{state.lower()}/"
    ext_by_jurisdiction = {}
    for r in ext_all:
        j = r.get("jurisdiction_ocdid", "")
        if j.startswith(state_prefix):
            ext_by_jurisdiction.setdefault(j, []).append(r)

    ext_count    = len(ext_known_jurisdiction_ids)
    ext_coverage = len(ext_by_jurisdiction)

    # ── Locality diffs ────────────────────────────────────────────────────────
    cp_jurisdiction_ids        = set(cp_by_jurisdiction.keys())
    not_yet_scraped            = sorted(
        j for j in known_jurisdiction_ids - cp_jurisdiction_ids
        if jurisdictions[j]["scrapeable"]
    )
    in_external_not_known      = sorted(ext_known_jurisdiction_ids - known_jurisdiction_ids)
    in_civicpatch_not_external = sorted(cp_jurisdiction_ids - ext_known_jurisdiction_ids)

    # ── Build per-locality entries ────────────────────────────────────────────
    all_jurisdictions = cp_jurisdiction_ids | set(ext_by_jurisdiction.keys())
    localities = []
    for jurisdiction in sorted(all_jurisdictions):
        cp_records        = cp_by_jurisdiction.get(jurisdiction, [])
        ext_records_local = ext_by_jurisdiction.get(jurisdiction, [])
        entry             = build_locality_entry(cp_records, ext_records_local, jurisdiction)
        localities.append(entry)
        print(f"  {entry['place']:<30} {entry['status']:<10} names={entry['name_match_pct']:.0%}")

    # ── Summary ───────────────────────────────────────────────────────────────
    localities_with_both   = [l for l in localities if l["civicpatch_count"] > 0 and l["ext_count"] > 0]
    total_name_matched     = sum(l["name_matched"] for l in localities_with_both)
    total_ext_in_both      = sum(l["ext_count"]    for l in localities_with_both)
    overall_name_match_pct = round(total_name_matched / total_ext_in_both, 2) if total_ext_in_both else None

    # ── Add coverage_since_coverage_reference_date ─────────────────────────────
    coverage_since_ref = load_coverage_since_reference(state.lower())

    summary = {
        "state":        state.lower(),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),

        "civicpatch": {
            "officials":  sum(l["civicpatch_count"] for l in localities),
            "localities": {
                "coverage":   len(cp_jurisdiction_ids),
                "coverage_since_coverage_reference_date": coverage_since_ref,
                "scrapeable": scrapeable_count,
                "known":      known_count,
            },
        },

        "external": {
            "officials":  sum(l["ext_count"] for l in localities),
            "localities": ext_count,
            "coverage":   ext_coverage,
        },

        "match_quality": {
            "localities_compared": len(localities_with_both),
            "name_match_pct":      overall_name_match_pct,
            "field_diffs": {
                "role":     sum(l["field_diffs"]["role"]     for l in localities),
                "division": sum(l["field_diffs"]["division"] for l in localities),
                "phone":    sum(l["field_diffs"]["phone"]    for l in localities),
                "email":    sum(l["field_diffs"]["email"]    for l in localities),
            },
        },

        "locality_gaps": {
            "not_yet_scraped":            not_yet_scraped,
            "in_external_not_known":      in_external_not_known,
            "in_civicpatch_not_external": in_civicpatch_not_external,
        },
    }

    with open(out_path, "w") as f:
        json.dump({"summary": summary, "localities": localities}, f, indent=2)

    coverage  = summary["civicpatch"]["localities"]["coverage"]
    known     = summary["civicpatch"]["localities"]["known"]
    match_pct = summary["match_quality"]["name_match_pct"]
    match_str = f"{match_pct:.0%}" if match_pct is not None else "n/a"

    print(f"\n✓ [{state.upper()}] {len(localities)} localities written to {out_path}")
    print(f"  localities: {coverage} coverage / {known} known / {ext_count} in external")
    print(f"  name match: {match_str}")


# ── Paths + entry points ──────────────────────────────────────────────────────

def paths_for_state(state: str):
    s = state.lower()
    return (
        f"data/{s}/local",
        f"data_source/{s}/jurisdictions.yml",
        f"data_source/{s}/local/validation/google/output.yml",
        f"scripts/track_progress/data/{s}_output.json",
    )


def main():
    if len(sys.argv) == 2:
        state = sys.argv[1]
        local_dir, jurisdictions_path, ext_path, out_path = paths_for_state(state)
    elif len(sys.argv) == 6:
        _, local_dir, jurisdictions_path, ext_path, out_path, state = sys.argv
    else:
        print("Usage:")
        print("  python compare.py <state>")
        print("  python compare.py <local_dir> <jurisdictions.yml> <external.yaml> <output.json> <state>")
        sys.exit(1)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    run(
        local_dir          = local_dir,
        jurisdictions_path = jurisdictions_path,
        ext_path           = ext_path,
        out_path           = out_path,
        state              = state,
    )


if __name__ == "__main__":
    main()