import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import requests

from schemas import Jurisdiction
from scripts.jurisdictions import headers
from scripts.jurisdictions.scrapers import counties as counties_scraper
from scripts.jurisdictions.config import state_configs
from scripts.jurisdictions.maps.county import build_county_map_for_state
from scripts.jurisdictions.yaml_io import get_names, load_existing_jurisdictions, ryaml

from scripts.paths import PROJECT_ROOT
_ACS_URL = "https://api.census.gov/data/2024/acs/acs5"


def _acs_url(query: str) -> str:
    key = os.environ.get("CENSUS_API_KEY")
    if not key:
        sys.exit(
            "CENSUS_API_KEY env var is required. "
            "Sign up: https://api.census.gov/data/key_signup.html — add to .env"
        )
    return f"{_ACS_URL}?{query}&key={key}"


def get_county_census_data(state: str, fips: str) -> Dict[str, Jurisdiction]:
    """Fetch county jurisdictions for a state from the Census ACS, keyed by OCD-ID."""
    census_data: Dict[str, Jurisdiction] = {}

    api_url = _acs_url(f"get=NAME,B01003_001E&for=county:*&in=state:{fips}")
    response = requests.get(api_url)
    if response.status_code != 200:
        print(f"Census county API request failed for {state}: {response.status_code}")
        return census_data

    for row in response.json()[1:]:
        name = row[0]           # e.g. "King County, Washington"
        population = int(row[1])
        county_code = row[3]    # 3-digit county FIPS
        geoid = f"{fips}{county_code}"

        if population == 0:
            continue

        county_name, friendly_name = get_names(name)
        ocdid = f"ocd-jurisdiction/country:us/state:{state}/county:{county_name}/government"
        census_data[ocdid] = Jurisdiction(
            id=ocdid, name=friendly_name, population=population, geoid=geoid
        )

    return census_data


def supplement_county_data(
    state: str, census_data: Dict[str, Jurisdiction], limit=None
) -> Tuple[Dict[str, Jurisdiction], List[str]]:
    """Attach Wikipedia data (url, wiki_url) to each county."""
    state_config = state_configs[state.lower()]
    return counties_scraper.scrape(
        census_data,
        state,
        state_config["name"],
        state_config["fips"],
        limit=limit,
    )


def pull_county_jurisdiction_data(state: str, limit=None, skip_wiki: bool = False):
    """Fetch county jurisdictions from Census ACS and write to data_source/{state}/counties/jurisdictions.yml."""
    state_config = state_configs.get(state.lower())
    fips = state_config["fips"]

    output_path = PROJECT_ROOT / "data_source" / state / "counties" / "jurisdictions.yml"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc, existing_by_id = load_existing_jurisdictions(output_path)

    census_data = get_county_census_data(state, fips)
    if not census_data:
        return

    # Detect renames: same GEOID but different OCD-ID (name changed in Census).
    # Preserve the original OCD-ID — GEOID is the stable identifier.
    existing_by_geoid = {
        j["geoid"]: ocdid
        for ocdid, j in existing_by_id.items()
        if j.get("geoid")
    }
    for census_ocdid in list(census_data.keys()):
        if census_ocdid in existing_by_id:
            continue
        old_ocdid = existing_by_geoid.get(census_data[census_ocdid].geoid)
        if old_ocdid:
            print(f"  ↔  GEOID {census_data[census_ocdid].geoid}: preserving OCD-ID {old_ocdid!r} (was {census_ocdid!r})")
            census_data[old_ocdid] = census_data[census_ocdid].model_copy(update={"id": old_ocdid})
            del census_data[census_ocdid]

    supplement_warnings: List[str] = []
    if not skip_wiki:
        census_data, supplement_warnings = supplement_county_data(state, census_data, limit=limit)

    # Merge into existing entries, preserving human edits (see field semantics below)
    for ocdid, supplemented_j in census_data.items():
        existing_entry = existing_by_id.get(ocdid)
        if existing_entry is None:
            existing_by_id[ocdid] = supplemented_j.model_dump(exclude_none=True)
            continue

        existing_entry["population"] = supplemented_j.population
        existing_entry["name"] = supplemented_j.name
        if supplemented_j.url and not existing_entry.get("url"):
            existing_entry["url"] = supplemented_j.url
        if supplemented_j.wiki_url:
            existing_entry["wiki_url"] = supplemented_j.wiki_url
        # issues and generated_comments replaced each run
        if supplemented_j.issues:
            existing_entry["issues"] = supplemented_j.issues
        elif "issues" in existing_entry:
            del existing_entry["issues"]
        if supplemented_j.generated_comments:
            existing_entry["generated_comments"] = supplemented_j.generated_comments
        elif "generated_comments" in existing_entry:
            del existing_entry["generated_comments"]
        # comments: never overwritten by scripts

    sorted_jurisdictions = sorted(
        existing_by_id.values(),
        key=lambda j: j.get("population") or 0,
        reverse=True,
    )
    doc["jurisdictions"] = sorted_jurisdictions
    doc["warnings"] = supplement_warnings

    doc.yaml_set_start_comment(
        headers.county_header(state, fips, state_config["name"])
    )

    with open(output_path, "w") as f:
        ryaml.dump(doc, f)
    print(f"Written {len(sorted_jurisdictions)} counties to {output_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("state", nargs="?", help="State code (omit to run all states with counties enabled)")
    parser.add_argument("--limit", type=int, default=None, help="Max Wikipedia pages to fetch (smoke-testing)")
    parser.add_argument("--skip-wiki", action="store_true", help="Skip Wikipedia enrichment; census data only")
    args = parser.parse_args()

    if args.state:
        if args.state not in state_configs:
            print(f"Unknown state '{args.state}'. Known states: {', '.join(state_configs)}")
            sys.exit(1)
        states = [args.state]
    else:
        states = list(state_configs.keys())
        print(f"Running for all states: {', '.join(states)}")

    for state in states:
        pull_county_jurisdiction_data(state, limit=args.limit, skip_wiki=args.skip_wiki)
        build_county_map_for_state(state, state_configs[state]["fips"])
