import re

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
