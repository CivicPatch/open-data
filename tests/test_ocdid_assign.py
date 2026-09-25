from scripts.ocdids.assign import assign
from scripts.ocdids.models import CensusRow, CensusType, Source

MA = "ocd-division/country:us/state:ma"
ME = "ocd-division/country:us/state:me"


def place(geoid, name, state="ma"):
    return CensusRow(state=state, geoid=geoid, census_type=CensusType.PLACE, name=name)


def town(geoid, name, county_name):
    return CensusRow(state="me", geoid=geoid, census_type=CensusType.COUNTY_SUBDIVISION, name=name, county_name=county_name)


class TestAssign:
    def test_registry_wins(self):
        result = assign([place("2501370", "Amherst Town city")], {"2501370": f"{MA}/place:amherst"})
        assert result["2501370"].division_ocdid == f"{MA}/place:amherst"
        assert result["2501370"].minted_ocdid == f"{MA}/place:amherst_town"
        assert result["2501370"].source == Source.REGISTRY

    def test_minted_when_not_in_registry(self):
        result = assign([place("2599999", "Newtown city")], {})
        assert result["2599999"].division_ocdid == f"{MA}/place:newtown"
        assert result["2599999"].source == Source.MINTED

    def test_collision_falls_back_to_full_name(self):
        rows = [town("1", "Lincoln town", "Penobscot County"), town("2", "Lincoln plantation", "Oxford County")]
        result = assign(rows, {})
        assert result["1"].division_ocdid == f"{ME}/place:lincoln_town"
        assert result["2"].division_ocdid == f"{ME}/place:lincoln_plantation"
        assert not result["1"].collision

    def test_minted_colliding_with_registry_id_takes_fallback(self):
        rows = [place("1", "Amherst city"), place("2", "Amherst village")]
        result = assign(rows, {"1": f"{MA}/place:amherst"})
        assert result["1"].division_ocdid == f"{MA}/place:amherst"
        assert result["2"].division_ocdid == f"{MA}/place:amherst_village"

    def test_unresolvable_collision_flagged(self):
        rows = [place("1", "Springfield city"), place("2", "Springfield city")]
        result = assign(rows, {})
        assert result["1"].collision and result["2"].collision
