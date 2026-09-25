from enum import Enum
from typing import FrozenSet, Mapping, Optional

from pydantic import BaseModel, ConfigDict


class CensusType(str, Enum):
    PLACE = "place"
    COUNTY_SUBDIVISION = "county_subdivision"
    COUNTY = "county"


class CensusRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    state: str
    geoid: str
    census_type: CensusType
    name: str  # Census name without state or county: "Concord town"
    county_name: Optional[str] = None  # county subdivisions only: "Middlesex County"


class Source(str, Enum):
    REGISTRY = "registry"
    MINTED = "minted"


class Assignment(BaseModel):
    model_config = ConfigDict(frozen=True)

    geoid: str
    division_ocdid: str
    minted_ocdid: str
    source: Source
    collision: bool = False


class Registry(BaseModel):
    model_config = ConfigDict(frozen=True)

    division_ocdids: FrozenSet[str]
    division_ocdid_by_geoid: Mapping[str, str]
