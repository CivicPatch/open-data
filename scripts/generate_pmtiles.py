import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import boto3
import yaml

from scripts.state_configs import state_configs

_COUNTY_SUFFIXES = (
    " and borough",
    " census area",
    " municipality",
    " borough",
    " parish",
    " county",
)


def _normalize_county_name(name: str) -> str:
    lower = name.lower()
    for suffix in _COUNTY_SUFFIXES:
        if lower.endswith(suffix):
            lower = lower[: -len(suffix)]
            break
    return re.sub(r"[^a-z0-9_]", "", lower.replace(" ", "_").replace("-", "_"))


_FIPS_TO_STATE_CODE: dict[str, str] = {v["fips"]: k for k, v in state_configs.items()}


def _enrich_state_feature(feature: dict) -> dict:
    props = feature["properties"]
    code = props["STUSPS"].lower()
    return {
        "type": "Feature",
        "geometry": feature["geometry"],
        "properties": {
            "jurisdiction_ocdid": f"ocd-division/country:us/state:{code}",
            "geoid": props["GEOID"],
            "name": props["NAME"],
            "code": code,
        },
    }


def _enrich_county_feature(feature: dict, fips_to_state: dict[str, str]) -> dict:
    props = feature["properties"]
    # caller must ensure STATEFP is in fips_to_state (i.e. state is in state_configs)
    state_code = fips_to_state[props["STATEFP"]]
    normalized = _normalize_county_name(props["NAME"])
    return {
        "type": "Feature",
        "geometry": feature["geometry"],
        "properties": {
            "jurisdiction_ocdid": f"ocd-division/country:us/state:{state_code}/county:{normalized}",
            "geoid": props["GEOID"],
            "name": props["NAMELSAD"],
        },
    }


def _build_local_lookup(jurisdictions: list[dict]) -> dict[str, dict]:
    lookup = {}
    for j in jurisdictions:
        geoid = j.get("geoid")
        if not geoid:
            continue
        ocdid = (
            j["id"]
            .replace("ocd-jurisdiction/", "ocd-division/")
            .replace("/government", "")
        )
        lookup[str(geoid)] = {"ocdid": ocdid, "name": j["name"]}
    return lookup


def _enrich_local_feature(feature: dict, lookup: dict[str, dict]) -> dict | None:
    props = feature.get("properties", {})
    geoid = str(props.get("GEOID") or props.get("geoid") or "")
    match = lookup.get(geoid)
    if not match:
        return None
    return {
        "type": "Feature",
        "geometry": feature["geometry"],
        "properties": {
            "jurisdiction_ocdid": match["ocdid"],
            "geoid": geoid,
            "name": match["name"],
        },
    }


def _run_tippecanoe(layers: list[tuple[str, Path, int]], output_path: Path) -> None:
    """layers: list of (layer_name, geojson_path, min_zoom) tuples"""
    cmd = [
        "tippecanoe",
        "-o", str(output_path),
        "--maximum-zoom", "14",
        "--no-feature-limit",
        "--force",
    ]
    for layer_name, geojson_path, min_zoom in layers:
        layer_spec = json.dumps({"file": str(geojson_path), "layer": layer_name, "minzoom": min_zoom})
        cmd.extend(["-L", layer_spec])
    subprocess.run(cmd, check=True, capture_output=True)


def _upload_to_r2(local_path: Path, s3_key: str) -> str:
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
        ExtraArgs={"ContentType": "application/octet-stream"},
    )
    return f"{os.environ['FRIENDLY_STORAGE_HOST']}/{s3_key}"


PROJECT_ROOT = Path(__file__).parent.parent


def generate_national_states() -> str:
    print("Generating national states overview...")
    features = []
    for geojson_path in sorted((PROJECT_ROOT / "data" / ".maps").glob("*/states.geojson")):
        with open(geojson_path) as f:
            data = json.load(f)
        features.extend(_enrich_state_feature(feat) for feat in data["features"])

    print(f"  {len(features)} state features enriched")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        states_path = tmp / "states.geojson"
        output_path = tmp / "states.pmtiles"
        states_path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
        print("  Running tippecanoe...")
        _run_tippecanoe([("states", states_path, 0)], output_path)
        print("  Uploading to R2...")
        url = _upload_to_r2(output_path, "maps/states.pmtiles")

    print(f"  Done: {url}")
    return url


def generate_state_bundle(state: str) -> str:
    print(f"Generating {state} bundle (states + counties + local)...")
    maps_dir = PROJECT_ROOT / "data" / ".maps" / state

    with open(maps_dir / "states.geojson") as f:
        states_features = [_enrich_state_feature(feat) for feat in json.load(f)["features"]]
    print(f"  states: {len(states_features)} features")

    with open(maps_dir / "counties.geojson") as f:
        counties_features = [_enrich_county_feature(feat, _FIPS_TO_STATE_CODE) for feat in json.load(f)["features"]]
    print(f"  counties: {len(counties_features)} features")

    yml_path = PROJECT_ROOT / "data_source" / state / "local" / "jurisdictions.yml"
    with open(yml_path) as f:
        lookup = _build_local_lookup(yaml.safe_load(f).get("jurisdictions", []))

    with open(maps_dir / "local.geojson") as f:
        raw_local = json.load(f)["features"]
    local_features = [e for feat in raw_local if (e := _enrich_local_feature(feat, lookup)) is not None]
    print(f"  local: {len(local_features)}/{len(raw_local)} features matched")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        states_path = tmp / "states.geojson"
        counties_path = tmp / "counties.geojson"
        local_path = tmp / "local.geojson"
        output_path = tmp / f"{state}.pmtiles"

        states_path.write_text(json.dumps({"type": "FeatureCollection", "features": states_features}))
        counties_path.write_text(json.dumps({"type": "FeatureCollection", "features": counties_features}))
        local_path.write_text(json.dumps({"type": "FeatureCollection", "features": local_features}))

        print("  Running tippecanoe...")
        _run_tippecanoe([
            ("states", states_path, 0),
            ("counties", counties_path, 5),
            ("local", local_path, 8),
        ], output_path)
        print("  Uploading to R2...")
        url = _upload_to_r2(output_path, f"maps/{state}.pmtiles")

    print(f"  Done: {url}")
    return url


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and upload PMTiles to R2")
    parser.add_argument("--state", help="State code (e.g. co). Omit to run all active states.")
    parser.add_argument(
        "--level",
        choices=["bundle", "national", "all"],
        default="all",
        help="bundle: per-state multi-layer PMTile; national: states overview; all: both",
    )
    args = parser.parse_args()

    states = [args.state] if args.state else list(state_configs.keys())

    if args.level in ("national", "all"):
        generate_national_states()

    if args.level in ("bundle", "all"):
        for s in states:
            generate_state_bundle(s)


if __name__ == "__main__":
    main()
