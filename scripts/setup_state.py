import os
import csv
import io
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

import geopandas
import pandas
import requests
import yaml

from schemas import Jurisdiction
from scripts.scrapers import co as co_scraper
from scripts.scrapers import nj as nj_scraper
from scripts.scrapers import wa as wa_scraper

from scripts.github_actions.update_jurisdiction_metadata import create_update_progress_file

PROJECT_ROOT = Path(__file__).parent.parent

state_configs = {
    "co": {
        "fips": "08",
        "pull_from_census": ["places"],
        "scraper": co_scraper,
    },
    "nj": {"fips": "34", "pull_from_census": ["places", "county_subdivisions"], "scraper": nj_scraper},
    "wa": {"fips": "53", "pull_from_census": ["places"], "scraper": wa_scraper},
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

def pull_jurisdiction_data(state: str):
    # TODO: this will be replaced by jurisdictions repo work
    # Should do a daily (???) pull or when data updates
    census_data, census_geo_data, census_warnings = get_census_data_for_state(state)
    jurisdictions_with_supplemented_data, supplement_warnings = supplement_data(
        state, census_data
    )
    jurisdictions = jurisdictions_with_supplemented_data.values()
    jurisdictions_by_population = sorted(
        jurisdictions,
        key=lambda j: j.population if j.population is not None else 0,
        reverse=True,
    )
    data = {
        "jurisdictions": [
            jurisdiction.model_dump() for jurisdiction in jurisdictions_by_population
        ],
        "warnings": census_warnings + supplement_warnings,
    }

    # Find project root (where pyproject.toml is located)
    output_path = PROJECT_ROOT / "data_source" / state / "jurisdictions.yml"

    # Create directory if it doesn't exist
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        yaml.dump(
            data,
            f,
            sort_keys=False,
        )


# https://www.census.gov/library/reference/code-lists/class-codes.html
def get_census_data_for_state(state: str) -> Tuple[Dict[str, Jurisdiction], List[str]]:
    census_data = {}
    census_geo_data = {} # TODO
    warnings = []

    state_config = state_configs.get(state.lower())
    if not state_config:
        print(f"State '{state}' not found in state configs.")
        return census_data, warnings
    state_fips = state_config.get("fips") if state_config else None
    if not state_fips:
        print(f"State '{state}' not found in FIPS mapping.")
        return census_data, warnings

    pull_from_census = state_config.get("pull_from_census", [])
    geojson_data_local_file_path = str(PROJECT_ROOT / "data" / state / ".maps" / "local.geojson")
    geojson_data_source_dir = str(PROJECT_ROOT / "data_source" / state / ".maps")

    # Create directory if it doesn't exist
    os.makedirs(geojson_data_source_dir, exist_ok=True)
    os.makedirs(os.path.dirname(geojson_data_local_file_path), exist_ok=True)

    if "places" in pull_from_census:
        # Index by name
        # https://www.census.gov/data/developers/data-sets/popest-popproj/popest.html
        # Don't open the following link directly
        # https://api.census.gov/data/2023/acs/acs5/variables.json
        place_jurisdictions, p_warnings = pull_place_data(state, state_fips)
        warnings.extend(p_warnings)

        place_map_url = census_place_geozip(state)
        geojson_file_path = os.path.join(geojson_data_source_dir, "places.geojson")
        zip_to_geojson(place_map_url, geojson_file_path, geojson_data_source_dir)

        for jurisdiction_object in place_jurisdictions:
            jurisdiction_ocdid = jurisdiction_object.id
            if census_data.get(jurisdiction_ocdid):
                print(f"Duplicate jurisdiction found: {jurisdiction_ocdid}")
                existing_jurisdiction = census_data[jurisdiction_ocdid]
                existing_jurisdiction_name = existing_jurisdiction.name
                jurisdiction_object_name = jurisdiction_object.name
                warnings.append(
                    f"Duplicate jurisdiction found:"
                    f"{jurisdiction_ocdid} between {existing_jurisdiction_name} and {jurisdiction_object_name}"
                )
            else:
                census_data[jurisdiction_ocdid] = jurisdiction_object

    if "county_subdivisions" in pull_from_census:
        cousub_jurisdictions, c_warnings = pull_cousub_data(state, state_fips)
        warnings.extend(c_warnings)

        cousub_map_url = census_cousub_geozip(state)
        geojson_file_path = os.path.join(geojson_data_source_dir, "cousubs.geojson")
        zip_to_geojson(cousub_map_url, geojson_file_path, geojson_data_source_dir)

        for jurisdiction_object in cousub_jurisdictions:
            jurisdiction_ocdid = jurisdiction_object.id
            if census_data.get(jurisdiction_ocdid):
                print(f"Duplicate jurisdiction found: {jurisdiction_ocdid}")
                existing_jurisdiction = census_data[jurisdiction_ocdid]
                existing_jurisdiction_name = existing_jurisdiction.name
                jurisdiction_object_name = jurisdiction_object.name
                warnings.append(
                    f"Duplicate jurisdiction found: "
                    f"{jurisdiction_ocdid} between "
                    f"{existing_jurisdiction_name}"
                    f"and {jurisdiction_object_name}"
                )
            else:
                census_data[jurisdiction_ocdid] = jurisdiction_object

    print(f"Combining localities into final local.geojson file: {geojson_data_local_file_path}")
    combine_geojsons_with_type(geojson_data_source_dir, geojson_data_local_file_path)
    return census_data, census_geo_data, warnings


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


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python scripts/setup_state.py <state>")
        sys.exit(1)

    state_arg = sys.argv[1]
    pull_jurisdiction_data(state_arg)
