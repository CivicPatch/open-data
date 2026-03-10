import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import geopandas
import pandas
import requests

PROJECT_ROOT = Path(__file__).parent.parent.parent

STATE_FIPS = {
    "co": "08",
    "nj": "34",
    "tx": "48",
    "wa": "53",
}

def census_place_geozip(state: str) -> str:
    fips = STATE_FIPS[state]
    return f"https://www2.census.gov/geo/tiger/TIGER2025/PLACE/tl_2025_{fips}_place.zip"


def census_cousub_geozip(state: str) -> str:
    fips = STATE_FIPS[state]
    return f"https://www2.census.gov/geo/tiger/TIGER2025/COUSUB/tl_2025_{fips}_cousub.zip"


def zip_to_geojson(url: str, output_geojson: str, data_source_map_dir: str):
    zip_path = os.path.join(data_source_map_dir, "data.zip")
    response = requests.get(url)
    with open(zip_path, "wb") as f:
        f.write(response.content)
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(data_source_map_dir)
    shp_files = [f for f in os.listdir(data_source_map_dir) if f.endswith(".shp")]
    if not shp_files:
        raise ValueError("No shapefile found in ZIP")
    shp_path = os.path.join(data_source_map_dir, shp_files[0])
    gdf = geopandas.read_file(shp_path)
    gdf.to_file(output_geojson, driver="GeoJSON")


def combine_geojsons_with_type(folder_path: str, output_path: str):
    geojson_files = [f for f in os.listdir(folder_path) if f.endswith(".geojson")]
    gdfs = []
    for file in geojson_files:
        file_path = os.path.join(folder_path, file)
        gdf = geopandas.read_file(file_path)
        gdf["type"] = os.path.splitext(file)[0]
        gdfs.append(gdf)
    if not gdfs:
        raise ValueError("No .geojson files found in the folder.")
    combined_gdf = geopandas.GeoDataFrame(
        pandas.concat(gdfs, ignore_index=True), crs=gdfs[0].crs
    )
    combined_gdf.to_file(output_path, driver="GeoJSON")

    # Stamp updated_at into the FeatureCollection
    with open(output_path, "r") as f:
        geojson = json.load(f)
    geojson["updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(output_path, "w") as f:
        json.dump(geojson, f, indent=2)

    features_found = geojson.get("features", [])
    print(f"Found {len(features_found)} features. Updated {output_path} with updated_at timestamp.")

def build_maps_for_state(state: str, pull_from_census: list[str]):
    """Download census geo data, convert to GeoJSON, and combine into local.geojson."""
    geojson_data_local_file_path = str(
        PROJECT_ROOT / "data" / state / ".maps" / "local.geojson"
    )
    geojson_data_source_dir = str(PROJECT_ROOT / "data_source" / state / ".maps")

    os.makedirs(geojson_data_source_dir, exist_ok=True)
    os.makedirs(os.path.dirname(geojson_data_local_file_path), exist_ok=True)

    if "places" in pull_from_census:
        geojson_file_path = os.path.join(geojson_data_source_dir, "places.geojson")
        census_place_geozip_url = census_place_geozip(state)
        zip_to_geojson(census_place_geozip_url, geojson_file_path, geojson_data_source_dir)

    if "county_subdivisions" in pull_from_census:
        geojson_file_path = os.path.join(geojson_data_source_dir, "cousubs.geojson")
        cousub_map_url = census_cousub_geozip(state)
        zip_to_geojson(cousub_map_url, geojson_file_path, geojson_data_source_dir)

    print(f"Combining localities into final local.geojson: {geojson_data_local_file_path}")
    combine_geojsons_with_type(geojson_data_source_dir, geojson_data_local_file_path)

    return geojson_data_local_file_path

if __name__ == "__main__":
    state = "tx"
    pull_from_census = ["places"]

    build_maps_for_state(state, pull_from_census)