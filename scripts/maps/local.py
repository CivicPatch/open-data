import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import geopandas
import pandas
import requests

PROJECT_ROOT = Path(__file__).parent.parent.parent

def census_place_geozip(fips: str) -> str:
    return f"https://www2.census.gov/geo/tiger/TIGER2025/PLACE/tl_2025_{fips}_place.zip"


def census_cousub_geozip(fips: str) -> str:
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

def build_maps_for_state(state: str, fips: str, pull_from_census: list[str]):
    """Download census geo data, convert to GeoJSON, and combine into local.geojson."""
    geojson_data_local_file_path = str(
        PROJECT_ROOT / "data" / ".maps" / state / "local.geojson"
    )
    geojson_data_source_dir = str(PROJECT_ROOT / "data_source" / state / ".maps")

    os.makedirs(geojson_data_source_dir, exist_ok=True)
    os.makedirs(os.path.dirname(geojson_data_local_file_path), exist_ok=True)

    if "places" in pull_from_census:
        geojson_file_path = os.path.join(geojson_data_source_dir, "places.geojson")
        census_place_geozip_url = census_place_geozip(fips)
        zip_to_geojson(census_place_geozip_url, geojson_file_path, geojson_data_source_dir)

    if "county_subdivisions" in pull_from_census:
        geojson_file_path = os.path.join(geojson_data_source_dir, "cousubs.geojson")
        cousub_map_url = census_cousub_geozip(fips)
        zip_to_geojson(cousub_map_url, geojson_file_path, geojson_data_source_dir)

    print(f"Combining localities into final local.geojson: {geojson_data_local_file_path}")
    combine_geojsons_with_type(geojson_data_source_dir, geojson_data_local_file_path)

    counties_path = str(PROJECT_ROOT / "data" / ".maps" / state / "counties.geojson")
    _add_parent_ocdids(geojson_data_local_file_path, counties_path, state)

    return geojson_data_local_file_path


def _add_parent_ocdids(local_path: str, counties_path: str, state: str) -> None:
    """Spatial join each local feature's centroid to its county, then write
    parent_ocdids = [county_ocdid, state_ocdid] into every feature's properties.
    OCD IDs come from canonical YAML files, not constructed by code."""
    if not Path(counties_path).exists():
        raise FileNotFoundError(
            f"counties.geojson not found for {state}: {counties_path}\n"
            f"Run 'mise run setup-state -- --state {state}' to generate county boundaries first."
        )
    counties_yml = PROJECT_ROOT / "data_source" / state / "counties" / "jurisdictions.yml"
    state_yml = PROJECT_ROOT / "data_source" / state / "state" / "jurisdictions.yml"

    with open(counties_yml) as f:
        county_lookup = {
            str(j["geoid"]): j["id"]
            for j in ryaml.load(f).get("jurisdictions", [])
            if j.get("geoid")
        }
    with open(state_yml) as f:
        state_juds = ryaml.load(f).get("jurisdictions", [])
    state_ocdid = state_juds[0]["id"] if state_juds else ""

    local_gdf = geopandas.read_file(local_path).reset_index(drop=True)
    counties_gdf = geopandas.read_file(counties_path)

    # Project to planar CRS for accurate centroids, then reproject counties to match
    local_projected = local_gdf.to_crs("EPSG:5070")
    counties_projected = counties_gdf.to_crs("EPSG:5070")
    centroids = local_projected.copy()
    centroids["geometry"] = local_projected.geometry.centroid

    joined = centroids.sjoin(
        counties_projected[["GEOID", "geometry"]],
        how="left",
        predicate="within",
    )
    county_geoid_map = joined["GEOID_right"].to_dict()

    with open(local_path) as f:
        geojson = json.load(f)

    for i, feature in enumerate(geojson["features"]):
        county_geoid = county_geoid_map.get(i)
        parents = []
        if county_geoid and not pandas.isna(county_geoid):
            county_ocdid = county_lookup.get(str(county_geoid))
            if county_ocdid:
                parents.append(county_ocdid)
        if state_ocdid:
            parents.append(state_ocdid)
        feature["properties"]["parent_ocdids"] = parents

    with open(local_path, "w") as f:
        json.dump(geojson, f, indent=2)

    matched = sum(1 for i in range(len(geojson["features"])) if county_geoid_map.get(i) and not pandas.isna(county_geoid_map.get(i)))
    print(f"  parent_ocdids: {matched}/{len(geojson['features'])} features matched to a county")

if __name__ == "__main__":
    state = "tx"
    pull_from_census = ["places"]

    build_maps_for_state(state, pull_from_census)