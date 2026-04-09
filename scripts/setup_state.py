import importlib.util
import os
import csv
import io
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

import geopandas
import pandas
import requests
from ruamel.yaml import YAML

ryaml = YAML()
ryaml.preserve_quotes = True
ryaml.default_flow_style = False
ryaml.width = 4096

def _represent_none(representer, _):
    return representer.represent_scalar("tag:yaml.org,2002:null", "null")

ryaml.representer.add_representer(type(None), _represent_none)

from schemas import Jurisdiction
from scripts.scrapers import co as co_scraper
from scripts.scrapers import nj as nj_scraper
from scripts.scrapers import wa as wa_scraper
from scripts.scrapers import tx as tx_scraper
import scripts.track_progress.generate_progress as generate_progress
import scripts.track_progress.generate_google_data as generate_google_data
from scripts.maps.local import build_maps_for_state


PROJECT_ROOT = Path(__file__).parent.parent

state_configs = {
    "co": {
        "fips": "08",
        "pull_from_census": ["places"],
        "scraper": co_scraper,
        "validation_sources": ["google"],
    },
    "nj": {
        "fips": "34",
        "pull_from_census": ["places", "county_subdivisions"],
        "scraper": nj_scraper,
        "validation_sources": ["google"],
    },
    "tx": {
        "fips": "48",
        "pull_from_census": ["places"],
        "scraper": tx_scraper,
        "validation_sources": ["google", "tml"],
    },
    "wa": {
        "fips": "53",
        "pull_from_census": ["places"],
        "scraper": wa_scraper,
        "validation_sources": ["google"],
    },
}


def census_place_geozip(state: str):
    state_fips = state_configs[state]["fips"]
    return f"https://www2.census.gov/geo/tiger/TIGER2025/PLACE/tl_2025_{state_fips}_place.zip"


def census_cousub_geozip(state: str):
    state_fips = state_configs[state]["fips"]
    return f"https://www2.census.gov/geo/tiger/TIGER2025/COUSUB/tl_2025_{state_fips}_cousub.zip"

def zip_to_geojson(url: str, output_geojson: str, data_source_map_dir: str):
    zip_path = os.path.join(data_source_map_dir, "data.zip")
    # Download the ZIP file
    response = requests.get(url)
    with open(zip_path, "wb") as f:
        f.write(response.content)
    # Extract the ZIP file
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(data_source_map_dir)
    # Find the .shp file
    shp_files = [f for f in os.listdir(data_source_map_dir) if f.endswith(".shp")]
    if not shp_files:
        raise ValueError("No shapefile found in ZIP")
    shp_path = os.path.join(data_source_map_dir, shp_files[0])
    # Read and convert to GeoJSON
    gdf = geopandas.read_file(shp_path)
    gdf.to_file(output_geojson, driver="GeoJSON")

def combine_geojsons_with_type(folder_path: str, output_path: str):
    geojson_files = [f for f in os.listdir(folder_path) if f.endswith('.geojson')]
    gdfs = []
    for file in geojson_files:
        file_path = os.path.join(folder_path, file)
        gdf = geopandas.read_file(file_path)
        # Add 'type' column with file name (without extension)
        file_type = os.path.splitext(file)[0]
        gdf['type'] = file_type
        gdfs.append(gdf)
    if not gdfs:
        raise ValueError("No .geojson files found in the folder.")
    combined_gdf = geopandas.GeoDataFrame(pandas.concat(gdfs, ignore_index=True), crs=gdfs[0].crs)
    combined_gdf.to_file(output_path, driver="GeoJSON")

def _load_existing_jurisdictions(path: Path):
    """Load existing jurisdictions.yml with ruamel.yaml (preserving comments).

    Returns (doc, existing_by_id) where:
      - doc is the full CommentedMap (top-level document), or {} if file absent
      - existing_by_id is a dict keyed by jurisdiction id pointing to CommentedMap entries
    """
    if not path.exists():
        return {}, {}
    with open(path) as f:
        doc = ryaml.load(f)
    if not doc or "jurisdictions" not in doc:
        return doc or {}, {}
    return doc, {j["id"]: j for j in doc["jurisdictions"]}


def pull_jurisdiction_data(state: str):
    # TODO: this will be replaced by jurisdictions repo work
    # Should do a daily (???) pull or when data updates

    output_path = PROJECT_ROOT / "data_source" / state / "jurisdictions.yml"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Single load — preserves comments in CommentedMap objects
    doc, existing_by_id = _load_existing_jurisdictions(output_path)

    census_data, census_geo_data, census_warnings = get_census_data_for_state(state)

    # Partition into new vs. existing vs. inactive
    census_ids = set(census_data.keys())
    existing_ids = set(existing_by_id.keys())

    new_ids = census_ids - existing_ids
    present_ids = census_ids & existing_ids
    inactive_ids = existing_ids - census_ids

    # Only fetch Wikipedia data for genuinely new jurisdictions
    new_census_subset = {id_: census_data[id_] for id_ in new_ids}
    if new_census_subset:
        new_supplemented, supplement_warnings = supplement_data(state, new_census_subset)
    else:
        new_supplemented, supplement_warnings = {}, []

    # Update existing entries in-place (population/name from census; clear inactive status)
    for ocdid in present_ids:
        census_j = census_data[ocdid]
        existing_entry = existing_by_id[ocdid]
        existing_entry["population"] = census_j.population
        existing_entry["name"] = census_j.name
        if "status" in existing_entry:
            del existing_entry["status"]

    # Mark entries absent from census as inactive
    for ocdid in inactive_ids:
        existing_by_id[ocdid]["status"] = "inactive"

    # Convert new supplemented Jurisdiction objects to plain dicts and add to map
    for ocdid, jurisdiction in new_supplemented.items():
        existing_by_id[ocdid] = jurisdiction.model_dump(exclude_none=True)

    # Sort all entries by population descending
    all_jurisdictions = sorted(
        existing_by_id.values(),
        key=lambda j: j.get("population") if j.get("population") is not None else 0,
        reverse=True,
    )

    doc["jurisdictions"] = all_jurisdictions
    doc["warnings"] = census_warnings + supplement_warnings

    with open(output_path, "w") as f:
        ryaml.dump(doc, f)


# https://www.census.gov/library/reference/code-lists/class-codes.html
def get_census_data_for_state(state: str):
    census_data = {}
    warnings = []

    state_config = state_configs.get(state.lower())
    if not state_config:
        print(f"State '{state}' not found in state configs.")
        return census_data, {}, warnings

    state_fips = state_config.get("fips")
    if not state_fips:
        print(f"State '{state}' not found in FIPS mapping.")
        return census_data, {}, warnings

    pull_from_census = state_config.get("pull_from_census", [])

    if "places" in pull_from_census:
        place_jurisdictions, p_warnings = pull_place_data(state, state_fips)
        warnings.extend(p_warnings)
        for jurisdiction_object in place_jurisdictions:
            jurisdiction_ocdid = jurisdiction_object.id
            if census_data.get(jurisdiction_ocdid):
                existing = census_data[jurisdiction_ocdid]
                warnings.append(
                    f"Duplicate jurisdiction found: {jurisdiction_ocdid} between "
                    f"{existing.name} and {jurisdiction_object.name}"
                )
            else:
                census_data[jurisdiction_ocdid] = jurisdiction_object

    if "county_subdivisions" in pull_from_census:
        cousub_jurisdictions, c_warnings = pull_cousub_data(state, state_fips)
        warnings.extend(c_warnings)
        for jurisdiction_object in cousub_jurisdictions:
            jurisdiction_ocdid = jurisdiction_object.id
            if census_data.get(jurisdiction_ocdid):
                existing = census_data[jurisdiction_ocdid]
                warnings.append(
                    f"Duplicate jurisdiction found: {jurisdiction_ocdid} between "
                    f"{existing.name} and {jurisdiction_object.name}"
                )
            else:
                census_data[jurisdiction_ocdid] = jurisdiction_object

    # Build maps separately — stamps updated_at into local.geojson
    build_maps_for_state(state, pull_from_census)

    return census_data, {}, warnings

def pull_place_data(
    state: str, state_fips: str
) -> Tuple[List[Jurisdiction], List[str]]:
    warnings = []
    state_config = state_configs.get(state.lower())
    if state_config is None:
        print(f"No configuration found for state: {state}")
        return [], warnings

    api_url = f"https://api.census.gov/data/2023/acs/acs5?get=NAME,B01003_001E&for=place:*&in=state:{state_fips}"
    # Ex: https://api.census.gov/data/2023/acs/acs5?get=NAME,B01003_001E&for=place:*&in=state:08
    codes_url = f"https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_gaz_place_{state_fips}.txt"
    # Ex: https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_gaz_place_08.txt
    api_response = requests.get(api_url)
    codes_response = requests.get(codes_url)

    jurisdictions = []
    if api_response.status_code == 200 and codes_response.status_code == 200:
        codes_data = codes_response.text  # Skip header
        codes_reader = csv.reader(io.StringIO(codes_data), delimiter="|")

        # Skip header row
        _header = next(codes_reader)
        codes_data = list(codes_reader)

        api_data_json = api_response.json()
        api_data_by_geoid = get_api_data_by_geoid(
            state, state_fips, api_data_json[1:], 1, "place"
        )
        for item in codes_data:
            name = item[4]
            funcstat = item[6]
            if funcstat not in ["A", "B", "C", "G"]:
                warnings.append(
                    f"Place: Skipping place with unsupported functional status ({funcstat}): {name})"
                )
                continue
            geoid = item[1]
            api_data = api_data_by_geoid.get(geoid, None)
            if api_data is None:
                warnings.append(f"Missing population for place: ({geoid})")
                continue
            population = int(api_data["population"])
            if population == 0:
                continue
            jurisdiction_object = Jurisdiction(
                id=api_data["jurisdiction_ocdid"],
                name=api_data["friendly_name"],
                url=None,
                population=population,
                geoid=geoid,
            )
            jurisdictions.append(jurisdiction_object)
    return jurisdictions, warnings


def pull_cousub_data(
    state: str, state_fips: str
) -> Tuple[List[Jurisdiction], List[str]]:
    warnings = []
    state_config = state_configs.get(state.lower())
    if state_config is None:
        print(f"No configuration found for state: {state}")
        return [], warnings

    api_url = f"https://api.census.gov/data/2023/acs/acs5?get=NAME,B01003_001E&for=county%20subdivision:*&in=state:{state_fips}"
    # Ex: https://api.census.gov/data/2023/acs/acs5?get=NAME,B01003_001E&for=county%20subdivision:*&in=state:08
    codes_url = f"https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_gaz_cousubs_{state_fips}.txt"
    # Ex: https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_gaz_cousubs_08.txt
    api_response = requests.get(api_url)
    codes_response = requests.get(codes_url)

    jurisdictions = []
    if codes_response.status_code == 200 and api_response.status_code == 200:
        codes_data = codes_response.text  # Skip header
        codes_reader = csv.reader(io.StringIO(codes_data), delimiter="|")

        # Skip header row
        _header = next(codes_reader)
        codes_data = list(codes_reader)

        api_data_json = api_response.json()
        api_data_by_geoid = get_api_data_by_geoid(
            state, state_fips, api_data_json[1:], 1, "county_subdivision"
        )
        for item in codes_data:
            name = item[4]
            funcstat = item[5]
            if funcstat not in ["A", "B", "C", "G"]:
                warnings.append(
                    f"Cousub: Skipping cousub with unsupported functional status ({funcstat}): {name})"
                )
                continue
            geoid = item[1]
            api_data = api_data_by_geoid.get(geoid, None)
            if api_data is None:
                warnings.append(f"Missing population for county subdivision: ({geoid})")
                continue
            population = int(api_data["population"])
            if population == 0:
                continue

            jurisdiction_object = Jurisdiction(
                id=api_data["jurisdiction_ocdid"],
                name=api_data["friendly_name"],
                url=None,
                population=population,
                geoid=geoid,
            )
            jurisdictions.append(jurisdiction_object)
    return jurisdictions, warnings


def create_jurisdiction_ocdid(state, api_name, type):
    if type == "county_subdivision":
        jurisdiction_name, _friendly_name = get_names(api_name)
        county_name = get_county_name(api_name)
        return f"ocd-jurisdiction/country:us/state:{state}/county:{county_name}/place:{jurisdiction_name}/government"
    else:  # place
        jurisdiction_name, _friendly_name = get_names(api_name)
        return f"ocd-jurisdiction/country:us/state:{state}/place:{jurisdiction_name}/government"


def create_geoid(state_fips: str, type: str, row: List[str]) -> str:
    if type == "county_subdivision":
        return f"{state_fips}{row[3]}{row[4]}"
    else:  # place
        return f"{state_fips}{row[3]}"


def get_api_data_by_geoid(
    state: str,
    state_fips: str,
    population_data: List[Any],
    population_index: int,
    type: str,
) -> Dict[str, Dict[str, Any]]:
    data = {}
    for item in population_data:
        name = item[0]
        geoid = create_geoid(state_fips, type, item)
        population = int(item[population_index])
        jurisdiction_name, friendly_name = get_names(name)
        # county_name = get_county_name(name)
        jurisdiction_ocdid = create_jurisdiction_ocdid(state, name, type)
        # jurisdiction_ocdid = f"ocd-jurisdiction/country:us/state:{state}/county:{county_name}/place:{jurisdiction_name}/government"
        data[geoid] = {
            "jurisdiction_ocdid": jurisdiction_ocdid,
            "jurisdiction_name": jurisdiction_name,
            "friendly_name": friendly_name,
            # "county_name": county_name,
            "population": population,
        }
    return data


def get_names(name: str) -> Tuple[str, str]:
    """Extract place name and jurisdiction name from full name."""
    # Example: "Gervais city, Oregon" -> ("gervais", "Gervais city")
    # jurisdiction_name, friendly_name
    parts = name.split(",")
    friendly_name = parts[0].strip()
    # Extract place name (without type)
    place_name_parts = friendly_name.split(" ")
    place_name = " ".join(place_name_parts[:-1]).lower()  # Remove last
    # Replace spaces with underscores
    jurisdiction_name = place_name.replace(" ", "_")
    return jurisdiction_name, friendly_name


def get_county_name(name: str) -> str:
    # "Buena Vista CCD, Orange County, Oregon" -> "orange"
    # "Redwood city, Red Wood County, Oregon" -> "red_wood"
    parts = name.split(",")
    county_part = parts[1].strip()  # e.g., "Orange County"
    county_name = county_part.replace(" County", "")
    county_name = county_name.replace(" ", "_").lower()
    return county_name


def supplement_data(
    state: str, census_data
) -> Tuple[Dict[str, Jurisdiction], List[str]]:
    state_config = state_configs.get(state.lower())
    scraper = state_config.get("scraper") if state_config else None
    if not scraper:
        print(f"No scraper found for state: {state}")
        exit(1)

    census_data, scrape_warnings = scraper.scrape(census_data)

    return census_data, scrape_warnings


def _run_google_transform(state: str):
    raw_rel, output_rel = generate_google_data.paths_for_state(state)
    raw_path = PROJECT_ROOT / raw_rel
    output_path = PROJECT_ROOT / output_rel

    if not raw_path.exists():
        if output_path.exists():
            print(f"[google] Raw data not found for '{state}', skipping (existing output preserved).")
            return
        print(f"[google] Missing required raw data for new state '{state}': {raw_path}")
        print("  Fetch Google Civic API data for this state before running setup.")
        sys.exit(1)

    generate_google_data.transform_file(str(raw_path), str(output_path), state)


def _run_tml_transform(state: str):
    tml_dir = PROJECT_ROOT / "data_source" / state / "local" / "validation" / "tml"
    raw_path = tml_dir / "tml_raw.json"
    output_path = tml_dir / "output.yml"
    transform_path = tml_dir / "transform_tml_raw.py"

    if not raw_path.exists():
        if output_path.exists():
            print(f"[tml] Raw data not found for '{state}', skipping (existing output preserved).")
            return
        print(f"[tml] Missing TML raw data for '{state}': {raw_path}")
        print("  Run scrape_tml_search.py to fetch TML data first.")
        sys.exit(1)

    if not transform_path.exists():
        print(f"[tml] Missing transform script: {transform_path}")
        sys.exit(1)

    spec = importlib.util.spec_from_file_location("transform_tml_raw", transform_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.transform_file(str(raw_path), str(output_path), state)


def run_validation_transforms(state: str):
    sources = state_configs[state].get("validation_sources", ["google"])
    for source in sources:
        if source == "google":
            _run_google_transform(state)
        elif source == "tml":
            _run_tml_transform(state)
        else:
            print(f"Unknown validation source '{source}' configured for state '{state}'.")
            sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/setup_state.py <state>")
        sys.exit(1)

    state_arg = sys.argv[1]
    pull_jurisdiction_data(state_arg)
    run_validation_transforms(state_arg)
    generate_progress.generate_readme()

