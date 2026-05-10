import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import boto3
import yaml

from scripts.state_configs import state_configs

PROJECT_ROOT = Path(__file__).parent.parent

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


def _fips_to_state_code() -> dict[str, str]:
    return {v["fips"]: k for k, v in state_configs.items()}


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
