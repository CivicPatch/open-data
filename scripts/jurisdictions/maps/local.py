import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import yaml
import geopandas
import pandas
import requests

from scripts.paths import PROJECT_ROOT
from scripts.jurisdictions.yaml_io import load_existing_jurisdictions, ryaml
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
        # Take the .shp named in *this* zip. Listing the directory instead would pick up
        # shapefiles left behind by an earlier layer (places/cousubs share this dir), and
        # os.listdir order is arbitrary — that is how a state could end up with both
        # places.geojson and cousubs.geojson built from the same shapefile.
        shp_files = [n for n in zip_ref.namelist() if n.endswith(".shp")]
    if not shp_files:
        raise ValueError(f"No shapefile found in ZIP: {url}")
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
    _add_county_ocdids(geojson_data_local_file_path, counties_path, state)

    return geojson_data_local_file_path


# Floating-point guard only, NOT a policy cutoff. TIGER's place and county layers are
# topologically integrated, so an overlap is either a real shared area or exact zero —
# there are no digitisation slivers to filter out. Every county a place genuinely reaches
# is recorded, however small (Enumclaw WA pokes ~5 hectares into Pierce, 0.4% of its
# area); ordering by descending share is what identifies the primary county.
_MIN_COUNTY_AREA_SHARE = 1e-9


def _add_county_ocdids(local_path: str, counties_path: str, state: str) -> None:
    """Spatial join each local feature to every county it materially overlaps, write
    county_ocdids into the feature's properties, and mirror
    parent_ocdids = [*county_ocdids, state_ocdid] back into jurisdictions.yml.
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
            for j in yaml.safe_load(f).get("jurisdictions", [])
            if j.get("geoid")
        }
    with open(state_yml) as f:
        state_ocdid = yaml.safe_load(f)["jurisdictions"][0]["id"]

    local_gdf = geopandas.read_file(local_path).reset_index(drop=True)
    counties_gdf = geopandas.read_file(counties_path)

    local_projected = local_gdf.to_crs("EPSG:5070")
    counties_projected = counties_gdf.to_crs("EPSG:5070")

    # Overlay the full polygons rather than joining centroids: a centroid lies in exactly
    # one county by construction, so centroid joins can never see a place that straddles a
    # county line (Bothell WA spans King and Snohomish).
    pieces = local_projected[["geometry"]].reset_index(names="local_index").overlay(
        counties_projected[["GEOID", "geometry"]],
        how="intersection",
        keep_geom_type=True,
    )
    pieces["share"] = (
        pieces.geometry.area
        / local_projected.geometry.area.reindex(pieces["local_index"]).to_numpy()
    )
    pieces = pieces[pieces["share"] >= _MIN_COUNTY_AREA_SHARE]

    # Largest overlap first, so the county a place mostly sits in leads the list.
    pieces = pieces.sort_values(["local_index", "share"], ascending=[True, False])
    county_geoid_map: dict[int, list[str]] = (
        pieces.groupby("local_index")["GEOID"].apply(list).to_dict()
    )

    with open(local_path) as f:
        geojson = json.load(f)

    geoid_to_parents: dict[str, list[str]] = {}
    for i, feature in enumerate(geojson["features"]):
        county_ocdids = [
            ocdid
            for geoid in county_geoid_map.get(i, [])
            if (ocdid := county_lookup.get(str(geoid)))
        ]
        feature["properties"]["county_ocdids"] = county_ocdids
        if county_ocdids:
            geoid = str(
                feature["properties"].get("GEOID")
                or feature["properties"].get("geoid")
                or ""
            )
            if geoid:
                geoid_to_parents[geoid] = [*county_ocdids, state_ocdid]

    with open(local_path, "w") as f:
        json.dump(geojson, f, indent=2)

    matched = sum(1 for f in geojson["features"] if f["properties"]["county_ocdids"])
    straddling = sum(
        1 for f in geojson["features"] if len(f["properties"]["county_ocdids"]) > 1
    )
    print(
        f"  county_ocdids: {matched}/{len(geojson['features'])} features matched to a "
        f"county ({straddling} spanning more than one)"
    )

    _write_parent_ocdids(state, geoid_to_parents)


def _write_parent_ocdids(state: str, geoid_to_parents: dict[str, list[str]]) -> None:
    """Mirror the spatial-join result into jurisdictions.yml so it reaches the DB.

    The geojson alone is not enough: open-data syncs from the YAML. This write-back was
    dropped when the pipeline was split into packages, which is why states onboarded
    after that point carry no parent_ocdids at all."""
    local_yml = PROJECT_ROOT / "data_source" / state / "local" / "jurisdictions.yml"
    doc, _ = load_existing_jurisdictions(local_yml)
    if not doc.get("jurisdictions"):
        print(f"  parent_ocdids: {local_yml} has no jurisdictions; skipping write-back")
        return

    written = 0
    for j in doc["jurisdictions"]:
        parents = geoid_to_parents.get(str(j.get("geoid", "")))
        if parents:
            j["parent_ocdids"] = parents
            written += 1

    with open(local_yml, "w") as f:
        ryaml.dump(doc, f)
    print(f"  parent_ocdids: written to {written} jurisdictions in {local_yml.name}")

if __name__ == "__main__":
    import argparse

    from scripts.jurisdictions.config import state_configs

    parser = argparse.ArgumentParser(description=build_maps_for_state.__doc__)
    parser.add_argument("state", help=f"State code, one of: {', '.join(state_configs)}")
    args = parser.parse_args()

    config = state_configs[args.state]
    build_maps_for_state(args.state, config["fips"], config["pull_from_census"])