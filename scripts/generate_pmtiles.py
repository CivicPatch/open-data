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


def _run_tippecanoe(geojson_path: Path, output_path: Path, layer_name: str) -> None:
    subprocess.run(
        [
            "tippecanoe",
            "-o", str(output_path),
            "--layer", layer_name,
            "--maximum-zoom", "14",
            "--drop-densest-as-needed",
            "--force",
            str(geojson_path),
        ],
        check=True,
        capture_output=True,
    )


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


def generate_state_pmtiles() -> str:
    features = []
    for geojson_path in sorted((PROJECT_ROOT / "data").glob("*/.maps/states.geojson")):
        with open(geojson_path) as f:
            data = json.load(f)
        features.extend(_enrich_state_feature(feat) for feat in data["features"])

    enriched = {"type": "FeatureCollection", "features": features}

    with tempfile.TemporaryDirectory() as tmp:
        tmp_geojson = Path(tmp) / "us-states.geojson"
        tmp_pmtiles = Path(tmp) / "us-states.pmtiles"
        tmp_geojson.write_text(json.dumps(enriched))
        _run_tippecanoe(tmp_geojson, tmp_pmtiles, "states")
        url = _upload_to_r2(tmp_pmtiles, "maps/us-states.pmtiles")

    print(f"Uploaded: {url}")
    return url


def generate_county_pmtiles(state: str) -> str:
    fips_to_state = _FIPS_TO_STATE_CODE
    geojson_path = PROJECT_ROOT / "data" / state / ".maps" / "counties.geojson"

    with open(geojson_path) as f:
        data = json.load(f)

    features = [_enrich_county_feature(feat, fips_to_state) for feat in data["features"]]
    enriched = {"type": "FeatureCollection", "features": features}

    with tempfile.TemporaryDirectory() as tmp:
        tmp_geojson = Path(tmp) / f"{state}-counties.geojson"
        tmp_pmtiles = Path(tmp) / f"{state}-counties.pmtiles"
        tmp_geojson.write_text(json.dumps(enriched))
        _run_tippecanoe(tmp_geojson, tmp_pmtiles, "counties")
        url = _upload_to_r2(tmp_pmtiles, f"maps/{state}-counties.pmtiles")

    print(f"Uploaded: {url}")
    return url


def generate_local_pmtiles(state: str) -> str:
    yml_path = PROJECT_ROOT / "data_source" / state / "local" / "jurisdictions.yml"
    with open(yml_path) as f:
        yml_data = yaml.safe_load(f)
    lookup = _build_local_lookup(yml_data.get("jurisdictions", []))

    geojson_path = PROJECT_ROOT / "data" / state / ".maps" / "local.geojson"
    with open(geojson_path) as f:
        data = json.load(f)

    features = []
    for feat in data["features"]:
        enriched_feat = _enrich_local_feature(feat, lookup)
        if enriched_feat is not None:
            features.append(enriched_feat)

    enriched = {"type": "FeatureCollection", "features": features}

    with tempfile.TemporaryDirectory() as tmp:
        tmp_geojson = Path(tmp) / f"{state}.geojson"
        tmp_pmtiles = Path(tmp) / f"{state}.pmtiles"
        tmp_geojson.write_text(json.dumps(enriched))
        _run_tippecanoe(tmp_geojson, tmp_pmtiles, "jurisdictions")
        url = _upload_to_r2(tmp_pmtiles, f"maps/{state}.pmtiles")

    print(f"Uploaded: {url}")
    return url


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and upload PMTiles to R2")
    parser.add_argument("--state", help="State code (e.g. co). Omit to run all active states.")
    parser.add_argument(
        "--level",
        choices=["local", "county", "state", "all"],
        default="all",
    )
    args = parser.parse_args()

    states = [args.state] if args.state else list(state_configs.keys())

    if args.level in ("state", "all"):
        generate_state_pmtiles()

    if args.level in ("county", "all"):
        for s in states:
            generate_county_pmtiles(s)

    if args.level in ("local", "all"):
        for s in states:
            generate_local_pmtiles(s)


if __name__ == "__main__":
    main()
