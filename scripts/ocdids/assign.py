"""Choose each jurisdiction's OCD-ID: the registry's where it has one, minted otherwise."""

from collections import Counter
from typing import Dict, Mapping, Sequence, Set

from scripts.ocdids.mint import mint, mint_disambiguated
from scripts.ocdids.models import Assignment, CensusRow, Source


def assign(rows: Sequence[CensusRow], registry_by_geoid: Mapping[str, str]) -> Dict[str, Assignment]:
    """GEOID → Assignment for one state's rows. IDs that still collide are flagged, never merged."""
    minted = mint_all(rows)
    chosen = choose_ids(rows, minted, registry_by_geoid)
    colliding = colliding_geoids(chosen)

    assignments = {}
    for row in rows:
        in_registry = row.geoid in registry_by_geoid
        assignments[row.geoid] = Assignment(
            geoid=row.geoid,
            division_ocdid=chosen[row.geoid],
            minted_ocdid=minted[row.geoid] if in_registry else chosen[row.geoid],
            source=Source.REGISTRY if in_registry else Source.MINTED,
            collision=row.geoid in colliding,
        )
    return assignments


def mint_all(rows: Sequence[CensusRow]) -> Dict[str, str]:
    """What our rules alone produce, including the registry's collision fallback."""
    minted = {row.geoid: mint(row) for row in rows}
    colliding = colliding_geoids(minted)

    result = {}
    for row in rows:
        if row.geoid in colliding:
            result[row.geoid] = mint_disambiguated(row)
        else:
            result[row.geoid] = minted[row.geoid]
    return result


def choose_ids(rows: Sequence[CensusRow], minted: Mapping[str, str], registry_by_geoid: Mapping[str, str]) -> Dict[str, str]:
    """Registry ID where known, else minted. A minted ID that collides with a registry ID
    takes the collision fallback; registry IDs are never changed."""
    preferred = {row.geoid: registry_by_geoid.get(row.geoid, minted[row.geoid]) for row in rows}
    colliding = colliding_geoids(preferred)

    result = {}
    for row in rows:
        is_minted = row.geoid not in registry_by_geoid
        if row.geoid in colliding and is_minted:
            result[row.geoid] = mint_disambiguated(row)
        else:
            result[row.geoid] = preferred[row.geoid]
    return result


def colliding_geoids(ocdid_by_geoid: Mapping[str, str]) -> Set[str]:
    counts = Counter(ocdid_by_geoid.values())
    return {geoid for geoid, ocdid in ocdid_by_geoid.items() if counts[ocdid] > 1}
