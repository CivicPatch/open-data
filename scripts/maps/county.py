"""Download Census TIGER county boundaries and write per-state counties.geojson."""
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import geopandas
import requests

PROJECT_ROOT = Path(__file__).parent.parent.parent

# National county file — one download, filtered per state by STATEFP column.
_TIGER_URL = "https://www2.census.gov/geo/tiger/TIGER2025/COUNTY/tl_2025_us_county.zip"
_CACHE_DIR = PROJECT_ROOT / "data_source" / ".maps_cache"
_CACHE_ZIP = _CACHE_DIR / "tl_2025_us_county.zip"
_CACHE_SHP_DIR = _CACHE_DIR / "county_shp"


def _ensure_shapefile() -> Path:
    """Download and extract the national county shapefile if not already cached."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if not _CACHE_ZIP.exists():
        print("Downloading national county shapefile (cached after first run)...")
        response = requests.get(_TIGER_URL)
        _CACHE_ZIP.write_bytes(response.content)

    if not _CACHE_SHP_DIR.exists():
        _CACHE_SHP_DIR.mkdir()
        with zipfile.ZipFile(_CACHE_ZIP) as zf:
            zf.extractall(_CACHE_SHP_DIR)

    shp_files = list(_CACHE_SHP_DIR.glob("*.shp"))
    if not shp_files:
        raise ValueError(f"No shapefile found after extracting {_CACHE_ZIP}")
    return shp_files[0]


def build_county_map_for_state(state: str, fips: str) -> str:
    """Filter the national county shapefile to this state and write counties.geojson."""
    output_path = PROJECT_ROOT / "data" / ".maps" / state / "counties.geojson"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    shp_path = _ensure_shapefile()
    gdf = geopandas.read_file(shp_path)
    state_gdf = gdf[gdf["STATEFP"] == fips].copy()
    state_gdf.to_file(str(output_path), driver="GeoJSON")

    with open(output_path) as f:
        geojson = json.load(f)
    geojson["updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(output_path, "w") as f:
        json.dump(geojson, f, indent=2)

    print(f"Written {len(state_gdf)} counties to {output_path}")
    return str(output_path)
