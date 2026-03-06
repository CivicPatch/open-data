"""
transform_civic.py  —  Transform Google Civic API data into CP YAML format

Usage:
    python transform_civic.py <state>
    python transform_civic.py <state> <raw_json> <processed_json> <output_yaml>

Example:
    python transform_civic.py tx
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_local(division_id: str) -> bool:
    """True if the divisionId contains /place: (includes council districts, wards, etc.)"""
    return "/place:" in (division_id or "")


def division_to_jurisdiction(division_id: str) -> str:
    """
    ocd-division/country:us/state:tx/place:austin
    -> ocd-jurisdiction/country:us/state:tx/place:austin/government
    """
    return division_id.replace("ocd-division/", "ocd-jurisdiction/", 1) + "/government"


# ── Transform ─────────────────────────────────────────────────────────────────

def transform_record(record: dict) -> dict:
    division_id = record.get("office_divisionId", "")
    return {
        "name":        record.get("name"),
        "other_names": [],
        "phones":      record.get("phones") or [],
        "emails":      [],
        "urls":        record.get("urls") or [],
        "start_date":  None,
        "end_date":    None,
        "office": {
            "name":           record.get("office_name"),
            "division_ocdid": division_id,
        },
        "image":              record.get("photoUrl") or None,
        "jurisdiction_ocdid": division_to_jurisdiction(division_id),
        "cdn_image":          None,
        "source_urls":        [],
        "updated_at":         datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "id":                 None,
    }


def load_meta_from_raw(raw_path: str, state: str) -> dict:
    """Extract local divisions and jurisdictions from raw Google Civic JSON."""
    with open(raw_path) as f:
        raw = json.load(f)

    all_divisions = raw.get("divisions", {}) if isinstance(raw, dict) else {}
    state_prefix  = f"ocd-division/country:us/state:{state.lower()}/"

    divisions     = []
    jurisdictions = []
    for division_id in sorted(all_divisions):
        if division_id.startswith(state_prefix) and is_local(division_id):
            divisions.append(division_id)
            jurisdictions.append(division_to_jurisdiction(division_id))

    return {"divisions": divisions, "jurisdictions": jurisdictions}


def transform_file(raw_path: str, processed_path: str, output_path: str, state: str):
    # ── Meta from raw ─────────────────────────────────────────────────────────
    meta = load_meta_from_raw(raw_path, state)

    # ── Records from processed ────────────────────────────────────────────────
    with open(processed_path) as f:
        records = json.load(f)
    if not isinstance(records, list):
        records = [records]

    local_records = [r for r in records if is_local(r.get("office_divisionId", ""))]
    skipped       = len(records) - len(local_records)
    transformed   = [transform_record(r) for r in local_records]

    # ── Write output ──────────────────────────────────────────────────────────
    def none_representer(dumper, _):
        return dumper.represent_scalar("tag:yaml.org,2002:null", "null")
    yaml.add_representer(type(None), none_representer)

    output = {"meta": meta, "records": transformed}

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        yaml.dump(output, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    print(f"✓ {len(transformed)} local records written to {output_path}")
    print(f"  {skipped} non-local records skipped (country/state level)")
    print(f"  {len(meta['divisions'])} local divisions in meta")


# ── Entry point ───────────────────────────────────────────────────────────────

def paths_for_state(state: str):
    s = state.lower()
    return (
        f"scripts/track_progress/google_data/{s}_all_raw.json",
        f"scripts/track_progress/google_data/{s}_all_processed.json",
        f"data_source/{s}/local/validation/google/output.yml",
    )


def main():
    if len(sys.argv) == 2:
        state = sys.argv[1]
        raw_path, processed_path, output_path = paths_for_state(state)
    elif len(sys.argv) == 5:
        _, state, raw_path, processed_path, output_path = sys.argv
    else:
        print("Usage:")
        print("  python transform_civic.py <state>")
        print("  python transform_civic.py <state> <raw_json> <processed_json> <output_yaml>")
        sys.exit(1)

    transform_file(raw_path, processed_path, output_path, state)


if __name__ == "__main__":
    main()