import pytest

from scripts.ocdids.registry import parse_registry

CSV = """id,name,census_geoid
ocd-division/country:us/state:ma/place:concord,Concord town,place-2501715060
ocd-division/country:us/state:ma/place:concord/precinct:1,Concord MA - Precinct 1,
ocd-division/country:us/state:ma/place:amherst,Amherst town,place-2501501325
"""


def test_indexes_by_geoid():
    registry = parse_registry(CSV, aliases={})
    assert registry.division_ocdid_by_geoid["2501715060"] == "ocd-division/country:us/state:ma/place:concord"


def test_rows_without_geoid_are_known_ids_but_not_indexed():
    registry = parse_registry(CSV, aliases={})
    assert "ocd-division/country:us/state:ma/place:concord/precinct:1" in registry.division_ocdids
    assert len(registry.division_ocdid_by_geoid) == 2


def test_alias_adds_geoid():
    registry = parse_registry(CSV, aliases={"2501370": "ocd-division/country:us/state:ma/place:amherst"})
    assert registry.division_ocdid_by_geoid["2501370"] == "ocd-division/country:us/state:ma/place:amherst"


def test_alias_outside_registry_raises():
    with pytest.raises(ValueError, match="outside the registry"):
        parse_registry(CSV, aliases={"1": "ocd-division/country:us/state:ma/place:nowhere"})
