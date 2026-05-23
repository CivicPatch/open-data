import argparse
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import tempfile
from pathlib import Path

import boto3
import requests
import yaml

from scripts.state_configs import state_configs

PROJECT_ROOT = Path(__file__).parent.parent


def _build_state_lookup(state: str) -> dict[str, str]:
    """geoid → ocd-jurisdiction ID from data_source/{state}/state/jurisdictions.yml"""
    yml_path = PROJECT_ROOT / "data_source" / state / "state" / "jurisdictions.yml"
    with open(yml_path) as f:
        data = yaml.safe_load(f)
    return {str(j["geoid"]): j["id"] for j in data.get("jurisdictions", []) if j.get("geoid")}


def _build_county_lookup(state: str) -> dict[str, str]:
    """geoid → ocd-jurisdiction ID from data_source/{state}/counties/jurisdictions.yml"""
    yml_path = PROJECT_ROOT / "data_source" / state / "counties" / "jurisdictions.yml"
    with open(yml_path) as f:
        data = yaml.safe_load(f)
    return {str(j["geoid"]): j["id"] for j in data.get("jurisdictions", []) if j.get("geoid")}


def _build_local_lookup(jurisdictions: list[dict]) -> dict[str, dict]:
    """geoid → {ocdid, name} from jurisdictions.yml entries"""
    lookup = {}
    for j in jurisdictions:
        geoid = j.get("geoid")
        if not geoid:
            continue
        lookup[str(geoid)] = {"ocdid": j["id"], "name": j["name"]}
    return lookup


def _enrich_state_feature(feature: dict, state_lookup: dict[str, str]) -> dict:
    props = feature["properties"]
    return {
        "type": "Feature",
        "geometry": feature["geometry"],
        "properties": {
            "jurisdiction_ocdid": state_lookup.get(str(props["GEOID"]), ""),
            "geoid": props["GEOID"],
            "name": props["NAME"],
            "code": props["STUSPS"].lower(),
        },
    }


def _enrich_county_feature(feature: dict, county_lookup: dict[str, str]) -> dict:
    props = feature["properties"]
    return {
        "type": "Feature",
        "geometry": feature["geometry"],
        "properties": {
            "jurisdiction_ocdid": county_lookup.get(str(props["GEOID"]), ""),
            "geoid": props["GEOID"],
            "name": props["NAMELSAD"],
        },
    }


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
            "county_ocdids": props.get("county_ocdids", []),
        },
    }


def _run_tippecanoe(layers: list[tuple[str, Path, int]], output_path: Path, label: str = "") -> None:
    """layers: list of (layer_name, geojson_path, min_zoom) tuples"""
    cmd = [
        "tippecanoe",
        "-o", str(output_path),
        "--maximum-zoom", "14",
        "--no-feature-limit",
        "--simplification", "10",
        "--force",
    ]
    for layer_name, geojson_path, min_zoom in layers:
        layer_spec = json.dumps({"file": str(geojson_path), "layer": layer_name, "minzoom": min_zoom})
        cmd.extend(["-L", layer_spec])
    prefix = f"[{label}] " if label else ""
    process = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True)
    for line in process.stderr:
        print(f"{prefix}{line}", end="", flush=True)
    process.wait()
    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, cmd)


def _purge_cloudflare_cache() -> None:
    """Purge all pmtiles cache variants. No-op if env vars not set (e.g. local dev)."""
    token = os.environ.get("CLOUDFLARE_PMTILES_BUST")
    zone_id = os.environ.get("CLOUDFLARE_ZONE_ID")
    if not token or not zone_id:
        print("Skipping CF cache purge (CLOUDFLARE_PMTILES_BUST / CLOUDFLARE_ZONE_ID not set)")
        return
    response = requests.post(
        f"https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"hosts": ["cdn.civicpatch.org"]},
        timeout=10,
    )
    response.raise_for_status()
    print(f"CF cache purged: {response.json().get('result', {}).get('id', '?')}")


def _upload_to_r2(local_path: Path, s3_key: str) -> str:
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["STORAGE_ENDPOINT"],
        aws_access_key_id=os.environ["STORAGE_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["STORAGE_SECRET_ACCESS_KEY"],
    )
    content_type = "application/geo+json" if s3_key.endswith(".geojson") else "application/octet-stream"
    s3.upload_file(
        str(local_path),
        "civicpatch",
        s3_key,
        ExtraArgs={"ContentType": content_type},
    )
    return f"{os.environ['FRIENDLY_STORAGE_HOST']}/{s3_key}"


def generate_national_states(all_state_features: list) -> str:
    print(f"Generating national states overview ({len(all_state_features)} features)...")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        states_path = tmp / "states.geojson"
        output_path = tmp / "states.pmtiles"
        states_path.write_text(json.dumps({"type": "FeatureCollection", "features": all_state_features}))
        print("  Running tippecanoe...")
        _run_tippecanoe([("states", states_path, 0)], output_path, label="national")
        print("  Uploading to R2...")
        url = _upload_to_r2(output_path, "maps/states.pmtiles")
    print(f"  Done: {url}")
    return url


def _download_geojson(s3, state: str, layer: str) -> dict:
    response = s3.get_object(Bucket="civicpatch", Key=f"maps/{state}/{layer}.geojson")
    return json.loads(response["Body"].read())


def generate_state_bundle(state: str) -> tuple[str, list]:
    print(f"[{state}] Downloading GeoJSONs from R2...")
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["STORAGE_ENDPOINT"],
        aws_access_key_id=os.environ["STORAGE_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["STORAGE_SECRET_ACCESS_KEY"],
    )

    state_lookup = _build_state_lookup(state)
    states_data = _download_geojson(s3, state, "states")
    states_features = [_enrich_state_feature(feat, state_lookup) for feat in states_data["features"]]
    print(f"[{state}] states: {len(states_features)} features")

    county_lookup = _build_county_lookup(state)
    counties_data = _download_geojson(s3, state, "counties")
    counties_features = [_enrich_county_feature(feat, county_lookup) for feat in counties_data["features"]]
    print(f"[{state}] counties: {len(counties_features)} features")

    yml_path = PROJECT_ROOT / "data_source" / state / "local" / "jurisdictions.yml"
    with open(yml_path) as f:
        local_lookup = _build_local_lookup(yaml.safe_load(f).get("jurisdictions", []))

    raw_local = _download_geojson(s3, state, "local")["features"]
    local_features = [e for feat in raw_local if (e := _enrich_local_feature(feat, local_lookup)) is not None]
    print(f"[{state}] local: {len(local_features)}/{len(raw_local)} features matched")

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
        ], output_path, label=state)
        print("  Uploading to R2...")
        url = _upload_to_r2(output_path, f"maps/{state}.pmtiles")

    print(f"  Done: {url}")
    return url, states_features


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and upload PMTiles to R2")
    parser.add_argument("--state", help="State code (e.g. co). Omit to run all active states.")
    args = parser.parse_args()

    states = [args.state] if args.state else list(state_configs.keys())

    all_state_features = []
    workers = min(len(states), os.cpu_count() or 1)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(generate_state_bundle, s): s for s in states}
        for future in as_completed(futures):
            _, state_feats = future.result()
            all_state_features.extend(state_feats)

    if not args.state:
        generate_national_states(all_state_features)

    _purge_cloudflare_cache()


if __name__ == "__main__":
    main()
