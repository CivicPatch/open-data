"""
Full setup for a single state: jurisdiction data, maps, and PMTiles.

Prerequisites (done once manually before running this):
  1. Add state to scripts/state_configs.py
  2. Write scraper in scripts/scrapers/{state}.py
  3. Fetch Google Civic data for the state (see preflight output for details)

Usage:
  mise run setup-state --state va
"""
import sys

from scripts.generate_pmtiles import generate_state_bundle
from scripts.maps.county import build_county_map_for_state
from scripts.maps.state import build_state_map_for_state
from scripts.setup_counties import pull_county_jurisdiction_data
from scripts.setup_local import (
    create_or_update_jurisdiction_metadata,
    preflight_check,
    pull_jurisdiction_data,
    run_validation_transforms,
)
from scripts.setup_maps import setup_maps_for_state
from scripts.setup_states import pull_state_jurisdiction_data
from scripts.state_configs import state_configs


def setup_state(state: str) -> None:
    if state not in state_configs:
        print(f"Unknown state '{state}'. Known states: {', '.join(state_configs)}")
        sys.exit(1)

    print(f"\n=== Setting up {state} ===\n")
    fips = state_configs[state]["fips"]

    print("[1/5] State boundary + jurisdiction data...")
    pull_state_jurisdiction_data(state)
    build_state_map_for_state(state, fips)

    print("[2/5] County boundaries + jurisdiction data...")
    pull_county_jurisdiction_data(state)
    build_county_map_for_state(state, fips)

    print("[3/5] Local jurisdiction data (Census + scraper + validation)...")
    preflight_check(state)
    pull_jurisdiction_data(state)
    create_or_update_jurisdiction_metadata(state)
    run_validation_transforms(state)

    print("[4/5] Uploading GeoJSONs to R2...")
    setup_maps_for_state(state)

    print("[5/5] Generating PMTile...")
    generate_state_bundle(state)

    print(f"\n✓ {state} setup complete.")
    print("Next steps:")
    print("  • Run 'mise run generate-pmtiles' to rebuild the national states overview")
    print("  • Push changes and trigger OD sync to land the new state in the DB")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Full setup for a single state")
    parser.add_argument("--state", required=True, help="State code (e.g. va)")
    args = parser.parse_args()
    setup_state(args.state)
