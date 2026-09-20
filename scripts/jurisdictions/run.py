"""
Full setup for a single state: jurisdiction data.

Prerequisites (done once manually before running this):
  1. Add state to scripts/jurisdictions/config.py
  2. Fit its `local_wiki` entry to the state's municipality list page
  3. Fetch Google Civic data for the state (see preflight output for details)

Usage:
  mise run setup-state -- --state va

Everything geo lives in civicpatch.org: boundary geometry, pmtiles and the containing-county
overlay that fills `meta_parent_ocdids`. After this finishes and syncs, trigger
`GenerateMapsWorkflow` for the state there.
"""
import sys

from scripts.jurisdictions.counties import pull_county_jurisdiction_data
from scripts.jurisdictions.local import (
    preflight_check,
    pull_jurisdiction_data,
    run_validation_transforms,
)
from scripts.jurisdictions.states import pull_state_jurisdiction_data
from scripts.jurisdictions.config import state_configs


def setup_state(state: str) -> None:
    if state not in state_configs:
        print(f"Unknown state '{state}'. Known states: {', '.join(state_configs)}")
        sys.exit(1)

    print(f"\n=== Setting up {state} ===\n")

    print("[1/3] State jurisdiction data...")
    pull_state_jurisdiction_data(state)

    print("[2/3] County jurisdiction data...")
    pull_county_jurisdiction_data(state)

    print("[3/3] Local jurisdiction data (Census + scraper + validation)...")
    preflight_check(state)
    pull_jurisdiction_data(state)
    run_validation_transforms(state)

    print(f"\n✓ {state} setup complete.")
    print("Next steps:")
    print("  • Push changes and trigger OD sync to land the new state in the DB")
    print("  • Trigger GenerateMapsWorkflow on civicpatch.org for boundaries and pmtiles")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Full setup for a single state")
    parser.add_argument("--state", required=True, help="State code (e.g. va)")
    args = parser.parse_args()
    setup_state(args.state)
