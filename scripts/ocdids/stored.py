"""Jurisdictions as stored in data_source/<state>/<level>/jurisdictions.yml."""

from enum import Enum
from pathlib import Path
from typing import List, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict

from scripts.jurisdictions.yaml_io import ryaml
from scripts.ocdids.models import CensusRow, CensusType
from scripts.paths import PROJECT_ROOT


class Level(str, Enum):
    STATE = "state"
    COUNTIES = "counties"
    LOCAL = "local"


class StoredJurisdiction(BaseModel):
    model_config = ConfigDict(frozen=True)

    level: Level
    id: str
    name: str
    geoid: Optional[str] = None


_CENSUS_TYPE_BY_GEOID_LENGTH = {
    5: CensusType.COUNTY,
    7: CensusType.PLACE,
    10: CensusType.COUNTY_SUBDIVISION,
}
_COUNTY_GEOID_LENGTH = 5


def jurisdictions_path(state: str, level: Level) -> Path:
    return PROJECT_ROOT / "data_source" / state / level.value / "jurisdictions.yml"


def stored_states() -> List[str]:
    return sorted(path.parent.parent.name for path in PROJECT_ROOT.glob("data_source/*/local/jurisdictions.yml"))


def read_stored(state: str) -> List[StoredJurisdiction]:
    return [entry for level in Level for entry in _read_level(state, level)]


def _read_level(state: str, level: Level) -> List[StoredJurisdiction]:
    path = jurisdictions_path(state, level)
    if not path.exists():
        return []
    entries = ryaml.load(path.read_text()).get("jurisdictions") or []
    return [
        StoredJurisdiction(level=level, id=e["id"], name=e["name"], geoid=e.get("geoid"))
        for e in entries
    ]


def census_rows(state: str, stored: Sequence[StoredJurisdiction]) -> List[CensusRow]:
    """Rebuild Census rows from stored entries: the GEOID's length gives the type, and a
    county subdivision's first five GEOID digits give its county."""
    county_names = {j.geoid: j.name for j in stored if j.level == Level.COUNTIES and j.geoid}

    rows = []
    for jurisdiction in stored:
        row = _census_row(state, jurisdiction, county_names)
        if row is not None:
            rows.append(row)
    return rows


def _census_row(state: str, stored: StoredJurisdiction, county_names: Mapping[str, str]) -> Optional[CensusRow]:
    if not stored.geoid:
        return None
    census_type = _CENSUS_TYPE_BY_GEOID_LENGTH.get(len(stored.geoid))
    if census_type is None:
        return None

    county_name = None
    if census_type == CensusType.COUNTY_SUBDIVISION:
        county_name = county_names.get(stored.geoid[:_COUNTY_GEOID_LENGTH])
    return CensusRow(state=state, geoid=stored.geoid, census_type=census_type, name=stored.name, county_name=county_name)


def stored_by_geoid(stored: Sequence[StoredJurisdiction]) -> Mapping[str, StoredJurisdiction]:
    return {j.geoid: j for j in stored if j.geoid}


def read_state(state: str) -> Tuple[List[StoredJurisdiction], List[CensusRow]]:
    stored = read_stored(state)
    return stored, census_rows(state, stored)
