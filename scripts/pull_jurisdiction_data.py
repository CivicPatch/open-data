import requests
from typing import Dict, Any, List, Tuple
from schemas import Jurisdiction
import csv
import yaml
import io
from pathlib import Path
from scripts.scrapers import (
    co as co_scraper
)

PROJECT_ROOT = Path(__file__).parent.parent

state_configs = {
    "co": {
        "fips": "08",
        "pull_from_census": ["places"],
        "scraper": co_scraper,
    },
    "wa": {
        "fips": "53",
        "pull_from_census": ["places"],
        "scraper": None,  # Placeholder for WA scraper
    }
}

def pull_jurisdiction_data(state: str):
    # TODO: this will be replaced by jurisdictions repo work
    # Should do a daily (???) pull or when data updates
    census_data, census_warnings = get_census_data_for_state(state)
    jurisdictions_with_supplemented_data, supplement_warnings = supplement_data(state, census_data)
    jurisdictions = jurisdictions_with_supplemented_data.values()
    jurisdictions_by_population = sorted(jurisdictions, key=lambda j: j.population if j.population is not None else 0, reverse=True)
    data = {
        "jurisdictions": [jurisdiction.model_dump() for jurisdiction in jurisdictions_by_population],
        "warnings": census_warnings + supplement_warnings
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

    if "places" in pull_from_census:
        # Index by name
        # https://www.census.gov/data/developers/data-sets/popest-popproj/popest.html
        # Don't open the following link directly
        # https://api.census.gov/data/2023/acs/acs5/variables.json
        place_jurisdictions, p_warnings = pull_place_data(state, state_fips)
        warnings.extend(p_warnings)
        for jurisdiction_object in place_jurisdictions:
            jurisdiction_id = jurisdiction_object.id
            if census_data.get(jurisdiction_id):
                print(f"Warning: Duplicate jurisdiction found: {jurisdiction_id}")
                existing_jurisdiction = census_data[jurisdiction_id]
                existing_jurisdiction_name = existing_jurisdiction.name
                jurisdiction_object_name = jurisdiction_object.name
                warnings.append(f"Duplicate jurisdiction found: {jurisdiction_id} between {existing_jurisdiction_name} and {jurisdiction_object_name}")
            else:
                census_data[jurisdiction_id] = jurisdiction_object

    if "county_subdivisions" in pull_from_census:
        cousub_jurisdictions, c_warnings = pull_cousub_data(state, state_fips)
        warnings.extend(c_warnings)
        for jurisdiction_object in cousub_jurisdictions:
            jurisdiction_id = jurisdiction_object.id
            if census_data.get(jurisdiction_id):
                print(f"Warning: Duplicate jurisdiction found: {jurisdiction_id}")
                existing_jurisdiction = census_data[jurisdiction_id]
                existing_jurisdiction_name = existing_jurisdiction.name
                jurisdiction_object_name = jurisdiction_object.name
                warnings.append(f"Duplicate jurisdiction found: {jurisdiction_id} between {existing_jurisdiction_name} and {jurisdiction_object_name}")
            else:
                census_data[jurisdiction_id] = jurisdiction_object

    return census_data, warnings

def pull_place_data(state: str, state_fips: str) -> Tuple[List[Jurisdiction], List[str]]:
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
        codes_reader = csv.reader(io.StringIO(codes_data), delimiter='|')

        # Skip header row
        _header = next(codes_reader)
        codes_data = list(codes_reader)
    
        api_data_json = api_response.json()
        api_data_by_geoid = get_api_data_by_geoid(
            state,
            state_fips,
            api_data_json[1:], 
            1,
            "place"
        )
        for item in codes_data:
            name = item[4]
            funcstat = item[6]
            if funcstat not in ["A", "B", "C", "G"]:
                warnings.append(f"Skipping place with unsupported functional status ({funcstat}): {name})")
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
                id=api_data["jurisdiction_id"],
                name=api_data["friendly_name"],
                url=None,
                population=population,
                geoid=geoid,
            )
            jurisdictions.append(jurisdiction_object)
    return jurisdictions, warnings

def pull_cousub_data(state: str, state_fips: str) -> Tuple[List[Jurisdiction], List[str]]:
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
        codes_reader = csv.reader(io.StringIO(codes_data), delimiter='|')

        # Skip header row
        _header = next(codes_reader)
        codes_data = list(codes_reader)

        api_data_json = api_response.json()
        api_data_by_geoid = get_api_data_by_geoid(
            state,
            state_fips,
            api_data_json[1:], 
            1,
            "county_subdivision"
        )
        for item in codes_data:
            name = item[4]
            funcstat = item[5]
            if funcstat not in ["A", "B", "C", "G"]:
                warnings.append(f"Skipping place with unsupported functional status ({funcstat}): {name})")
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
                id=api_data["jurisdiction_id"],
                name=api_data["friendly_name"],
                url=None,
                population=population,
                geoid=geoid
            )
            jurisdictions.append(jurisdiction_object)
    return jurisdictions, warnings

def create_jurisdiction_id(state, api_name, type):
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

def get_api_data_by_geoid(state: str, state_fips: str, population_data: List[Any], population_index: int, type: str) -> Dict[str, Dict[str, Any]]:
    data = {}
    for item in population_data:
        name = item[0]
        geoid = create_geoid(state_fips, type, item)
        population = int(item[population_index])
        jurisdiction_name, friendly_name = get_names(name)
        # county_name = get_county_name(name)
        jurisdiction_id = create_jurisdiction_id(state, name, type)
        # jurisdiction_id = f"ocd-jurisdiction/country:us/state:{state}/county:{county_name}/place:{jurisdiction_name}/government"
        data[geoid] = {
            "jurisdiction_id": jurisdiction_id,
            "jurisdiction_name": jurisdiction_name,
            "friendly_name": friendly_name,
            # "county_name": county_name,
            "population": population
        }
    return data 

def get_names(name: str) -> Tuple[str,str]:
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

def supplement_data(state: str, census_data) -> Tuple[Dict[str, Jurisdiction], List[str]]:
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
        print("Usage: python scripts/pull_jurisdiction_data.py <state>")
        sys.exit(1)
    
    state_arg = sys.argv[1]
    pull_jurisdiction_data(state_arg)