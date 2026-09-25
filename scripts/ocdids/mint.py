"""Mint OCD-IDs with the registry's own rules (see mint_rules)."""

import re
from typing import Iterable, Tuple

from scripts.ocdids.ids import state_division
from scripts.ocdids.mint_rules import (
    COUNTY_ENDINGS,
    COUNTY_NAME_OVERRIDES,
    PLACE_ENDINGS,
    PLACE_GEOID_OVERRIDES,
    PLACE_NAME_OVERRIDES,
    SUBDIV_RULES,
    SUBDIVISION_ENDINGS,
)
from scripts.ocdids.models import CensusRow, CensusType


def slug(name: str) -> str:
    """`. ` and ` ` → `_`, any other punctuation → `~` (the registry's make_id)."""
    underscored = re.sub(r"\.? ", "_", name.lower())
    return re.sub(r"[^\w~_.-]", "~", underscored)


def strip_ending(name: str, endings: Iterable[str]) -> str:
    for ending in endings:
        if name.endswith(ending):
            # str.replace rather than removesuffix: reproduces the registry exactly
            return name.replace(ending, "")
    return name


def county_segment(county_name: str) -> Tuple[str, str]:
    """("St. Clair County") → ("county", "st_clair")."""
    if county_name in COUNTY_NAME_OVERRIDES:
        name, county_type = COUNTY_NAME_OVERRIDES[county_name]
        return county_type, slug(name)
    for ending, county_type in COUNTY_ENDINGS.items():
        if county_name.endswith(ending):
            return county_type, slug(county_name.replace(ending, ""))
    return "county", slug(county_name)


def mint_county(state: str, county_name: str) -> str:
    county_type, value = county_segment(county_name)
    return f"{state_division(state)}/{county_type}:{value}"


def mint_place(row: CensusRow) -> str:
    if row.name in PLACE_NAME_OVERRIDES:
        name = PLACE_NAME_OVERRIDES[row.name]
    elif row.geoid in PLACE_GEOID_OVERRIDES:
        name = PLACE_GEOID_OVERRIDES[row.geoid]
    else:
        name = strip_ending(row.name, PLACE_ENDINGS)
    return f"{state_division(row.state)}/place:{slug(name)}"


def mint_county_subdivision(row: CensusRow) -> str:
    rule = SUBDIV_RULES.get(row.state)
    if rule is None:
        raise ValueError(
            f"{row.state}: no SUBDIV_RULES entry — decide whether its county subdivisions "
            f"are 'prefix' or 'town' (see census_places.py in ocd-division-ids)"
        )
    place = f"place:{slug(strip_ending(row.name, SUBDIVISION_ENDINGS))}"
    if rule == "town":
        return f"{state_division(row.state)}/{place}"
    if not row.county_name:
        raise ValueError(f"{row.state}: county subdivision {row.name!r} needs its county")
    return f"{mint_county(row.state, row.county_name)}/{place}"


def mint(row: CensusRow) -> str:
    if row.census_type == CensusType.PLACE:
        return mint_place(row)
    if row.census_type == CensusType.COUNTY_SUBDIVISION:
        return mint_county_subdivision(row)
    return mint_county(row.state, row.name)


def segment_type(row: CensusRow) -> str:
    if row.census_type == CensusType.COUNTY:
        county_type, _value = county_segment(row.name)
        return county_type
    # The registry maps every place and county-subdivision type word (city, town, township, ...) to "place"
    return "place"


def mint_disambiguated(row: CensusRow) -> str:
    """The registry's fallback when two rows mint the same ID: the full Census name, type word
    included ("Lincoln town" → lincoln_town). It always goes directly under the state, even for
    a county subdivision that would otherwise sit under its county."""
    return f"{state_division(row.state)}/{segment_type(row)}:{slug(row.name)}"
