import json
import yaml
import uuid
import re
from datetime import datetime
from pathlib import Path

def city_name_to_place_slug(city_name: str) -> str:
    """'City of Rangerville' -> 'rangerville'"""
    # Strip prefixes like "City of", "Town of", "Village of"
    name = re.sub(r"^(city|town|village)\s+of\s+", "", city_name, flags=re.IGNORECASE)
    # Lowercase, replace spaces/special chars with underscores
    name = name.lower().strip()
    name = re.sub(r"['\.]", "", name)       # remove apostrophes, periods
    name = re.sub(r"[\s\-]+", "_", name)    # spaces/hyphens -> underscore
    return name

def make_jurisdiction_ocdid(place_slug: str, state: str = "tx") -> str:
    return f"ocd-jurisdiction/country:us/state:{state}/place:{place_slug}/government"

def make_division_ocdid(place_slug: str, state: str = "tx") -> str:
    return f"ocd-division/country:us/state:{state}/place:{place_slug}"

def transform_individual(record: dict, state: str = "tx") -> dict:
    place_slug = city_name_to_place_slug(record.get("city_name", ""))
    
    return {
        "name": record.get("name"),
        "other_names": [],
        "phones": [record["phone"]] if record.get("phone") else [],
        "emails": [],
        "urls": [record["individual_url"]] if record.get("individual_url") else [],
        "start_date": None,
        "end_date": None,
        "office": {
            "name": record.get("role"),
            "division_ocdid": make_division_ocdid(place_slug, state),
        },
        "image": None,
        "jurisdiction_ocdid": make_jurisdiction_ocdid(place_slug, state),
        "cdn_image": None,
        "source_urls": [record["city_url"]] if record.get("city_url") else [],
        "updated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "id": str(uuid.uuid4()),
    }

def transform_file(input_path: str, output_path: str, state: str = "tx"):
    with open(input_path) as f:
        # Handle both a bare array and a wrapped object
        raw = f.read().strip()
        # If it's not wrapped in [], wrap it so partial files also parse
        if not raw.startswith("["):
            raw = "[" + raw.rstrip(",") + "]"
        records = json.loads(raw)

    transformed = [transform_individual(r, state) for r in records]

    # Custom representer so null stays null (not 'null' string) and
    # empty lists stay []
    def none_representer(dumper, _):
        return dumper.represent_scalar("tag:yaml.org,2002:null", "null")

    yaml.add_representer(type(None), none_representer)

    with open(output_path, "w") as f:
        yaml.dump(transformed, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    print(f"✓ Wrote {len(transformed)} records to {output_path}")

if __name__ == "__main__":
    import sys
    input_file  = sys.argv[1] if len(sys.argv) > 1 else "data_source/tx/local/validation/tml/tml_raw.json"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "data_source/tx/local/validation/tml/output.yml"
    state_code  = sys.argv[3] if len(sys.argv) > 3 else "tx"
    transform_file(input_file, output_file, state_code)