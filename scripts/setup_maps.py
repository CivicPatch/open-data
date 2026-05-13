"""
Generate map GeoJSONs from Census TIGER and upload to R2.

Run this when:
- Adding a new state
- Census TIGER updates (annually)
- Jurisdiction names change in jurisdictions.yml

After running this, run generate_pmtiles.py to build PMTiles from the uploaded GeoJSONs.
"""
import argparse
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3

from scripts.maps.county import build_county_map_for_state
from scripts.maps.local import build_maps_for_state
from scripts.maps.state import build_state_map_for_state
from scripts.state_configs import state_configs

PROJECT_ROOT = Path(__file__).parent.parent


def _upload_geojson(local_path: Path, s3_key: str) -> None:
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["STORAGE_ENDPOINT"],
        aws_access_key_id=os.environ["STORAGE_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["STORAGE_SECRET_ACCESS_KEY"],
    )
    s3.upload_file(
        str(local_path),
        "civicpatch",
        s3_key,
        ExtraArgs={"ContentType": "application/geo+json"},
    )


def setup_maps_for_state(state: str) -> None:
    config = state_configs[state]
    fips = config["fips"]
    maps_dir = PROJECT_ROOT / "data" / ".maps" / state

    print(f"[{state}] Generating state boundary...")
    build_state_map_for_state(state, fips)
    _upload_geojson(maps_dir / "states.geojson", f"maps/{state}/states.geojson")
    print(f"[{state}] states.geojson → R2")

    print(f"[{state}] Generating county boundaries...")
    build_county_map_for_state(state, fips)
    _upload_geojson(maps_dir / "counties.geojson", f"maps/{state}/counties.geojson")
    print(f"[{state}] counties.geojson → R2")

    print(f"[{state}] Generating local boundaries + parent_ocdids...")
    build_maps_for_state(state, fips, config["pull_from_census"])
    _upload_geojson(maps_dir / "local.geojson", f"maps/{state}/local.geojson")
    print(f"[{state}] local.geojson → R2")

    print(f"[{state}] Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate map GeoJSONs and upload to R2")
    parser.add_argument("--state", help="State code (e.g. co). Omit to run all active states.")
    args = parser.parse_args()

    states = [args.state] if args.state else list(state_configs.keys())

    if args.state and args.state not in state_configs:
        print(f"Unknown state '{args.state}'. Known: {', '.join(state_configs)}")
        raise SystemExit(1)

    workers = min(len(states), os.cpu_count() or 1)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(setup_maps_for_state, s): s for s in states}
        for future in as_completed(futures):
            future.result()
