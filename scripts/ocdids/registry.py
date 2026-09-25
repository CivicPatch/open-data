"""The OCD division registry (opencivicdata/ocd-division-ids), indexed by Census GEOID.

REGISTRY_PATH is a pinned copy of the registry's identifiers/country-us.csv, currently at
upstream commit 1ec1eda (2026-09-15). To update it, download the latest file over it,
then regenerate the mismatch report and review both diffs:

    curl -sSfL https://raw.githubusercontent.com/opencivicdata/ocd-division-ids/master/identifiers/country-us.csv \\
        -o data_source/ocd_division_ids/country-us.csv
    uv run python -m scripts.ocdids.registry_report
"""

import csv
from functools import lru_cache
from typing import Mapping

from scripts.ocdids.models import Registry
from scripts.paths import PROJECT_ROOT

REGISTRY_PATH = PROJECT_ROOT / "data_source" / "ocd_division_ids" / "country-us.csv"
_GEOID_PREFIX = "place-"

# GEOID → registry ID for jurisdictions the registry has under an older Census GEOID
# (renamed or re-coded since its 2014 snapshot), which a GEOID lookup would miss.
GEOID_ALIASES: Mapping[str, str] = {
    # MA "Town city"s: registry keyed them by their county-subdivision GEOID
    "2501370": "ocd-division/country:us/state:ma/place:amherst",
    "2556000": "ocd-division/country:us/state:ma/place:randolph",
    "2546598": "ocd-division/country:us/state:ma/place:north_attleborough",
    "2508130": "ocd-division/country:us/state:ma/place:bridgewater",
    "0812900": "ocd-division/country:us/state:co/place:central_city",
    "3727324": "ocd-division/country:us/state:nc/place:grandfather",
    # Schrunk-Steiber township: registry predates the merger, has Schrunk (3801571220)
    "3801571223": "ocd-division/country:us/state:nd/county:burleigh/place:schrunk",
    # Rocky Top city: renamed from Lake City in 2014; registry keeps the old name
    "4764668": "ocd-division/country:us/state:tn/place:lake_city",
    "4834018": "ocd-division/country:us/state:tx/place:hillcrest",
    "4859065": "ocd-division/country:us/state:tx/place:post_oak_bend_city",
    # Town of Pecos City: registry has it as Pecos city (4856516)
    "4873493": "ocd-division/country:us/state:tx/place:pecos",
}


def parse_registry(csv_text: str, aliases: Mapping[str, str] = GEOID_ALIASES) -> Registry:
    rows = list(csv.DictReader(csv_text.splitlines()))
    division_ocdids = frozenset(row["id"] for row in rows)
    unknown_aliases = {geoid: ocdid for geoid, ocdid in aliases.items() if ocdid not in division_ocdids}
    if unknown_aliases:
        raise ValueError(f"GEOID aliases point outside the registry: {unknown_aliases}")
    by_geoid = {
        row["census_geoid"].removeprefix(_GEOID_PREFIX): row["id"]
        for row in rows
        if row["census_geoid"].startswith(_GEOID_PREFIX)
    }
    return Registry(division_ocdids=division_ocdids, division_ocdid_by_geoid={**by_geoid, **aliases})


@lru_cache(maxsize=1)
def load_registry() -> Registry:
    return parse_registry(REGISTRY_PATH.read_text())
