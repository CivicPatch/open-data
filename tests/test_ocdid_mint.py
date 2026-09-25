import pytest

from scripts.ocdids.mint import mint, mint_county, mint_disambiguated, slug
from scripts.ocdids.models import CensusRow, CensusType

MA = "ocd-division/country:us/state:ma"
MI = "ocd-division/country:us/state:mi"
NJ = "ocd-division/country:us/state:nj"


def place(state, name, geoid="0"):
    return CensusRow(state=state, geoid=geoid, census_type=CensusType.PLACE, name=name)


def subdivision(state, name, county_name):
    return CensusRow(state=state, geoid="0", census_type=CensusType.COUNTY_SUBDIVISION, name=name, county_name=county_name)


class TestSlug:
    def test_spaces_become_underscores(self):
        assert slug("Mount Pleasant") == "mount_pleasant"

    def test_period_space_becomes_underscore(self):
        assert slug("St. Clair") == "st_clair"

    def test_apostrophe_becomes_tilde(self):
        assert slug("Coeur d'Alene") == "coeur_d~alene"

    def test_parens_become_tilde(self):
        assert slug("El Paso de Robles (Paso Robles)") == "el_paso_de_robles_~paso_robles~"

    def test_slash_becomes_tilde(self):
        assert slug("New Germantown/Schiller") == "new_germantown~schiller"

    def test_non_ascii_kept(self):
        assert slug("Cañon City") == "cañon_city"


class TestMintPlace:
    def test_strips_type_word(self):
        assert mint(place("ma", "Boston city")) == f"{MA}/place:boston"

    def test_keeps_city_that_is_part_of_the_name(self):
        assert mint(place("co", "Central City city")) == "ocd-division/country:us/state:co/place:central_city"

    def test_strips_cdp(self):
        assert mint(place("ca", "Mountain House CDP")) == "ocd-division/country:us/state:ca/place:mountain_house"

    def test_name_override(self):
        assert mint(place("tn", "Hartsville/Trousdale County")) == "ocd-division/country:us/state:tn/place:hartsville"

    def test_geoid_override(self):
        assert mint(place("tx", "Reno city (Lamar County)", geoid="4861592")) == (
            "ocd-division/country:us/state:tx/place:reno_~lamar_county~"
        )


class TestMintCountySubdivision:
    def test_town_state_has_no_county(self):
        assert mint(subdivision("ma", "Concord town", "Middlesex County")) == f"{MA}/place:concord"

    def test_prefix_state_has_county(self):
        assert mint(subdivision("nj", "Springfield township", "Morris County")) == f"{NJ}/county:morris/place:springfield"

    def test_prefix_state_county_is_slugged(self):
        assert mint(subdivision("mi", "Emmett township", "St. Clair County")) == f"{MI}/county:st_clair/place:emmett"

    def test_unknown_ending_mints_full_name(self):
        assert mint(subdivision("nh", "Hart's Location", "Carroll County")) == (
            "ocd-division/country:us/state:nh/place:hart~s_location"
        )

    def test_state_without_rule_raises(self):
        with pytest.raises(ValueError, match="SUBDIV_RULES"):
            mint(subdivision("tx", "Foo town", "Bar County"))


class TestMintCounty:
    def test_county(self):
        assert mint_county("mi", "St. Clair County") == f"{MI}/county:st_clair"

    def test_parish(self):
        assert mint_county("la", "Orleans Parish") == "ocd-division/country:us/state:la/parish:orleans"


class TestMintDisambiguated:
    def test_keeps_type_word(self):
        assert mint_disambiguated(subdivision("me", "Lincoln town", "Penobscot County")) == (
            "ocd-division/country:us/state:me/place:lincoln_town"
        )

    def test_drops_county_in_prefix_state(self):
        assert mint_disambiguated(subdivision("nj", "Franklin township", "Somerset County")) == (
            f"{NJ}/place:franklin_township"
        )

    def test_county_keeps_its_type(self):
        row = CensusRow(state="la", geoid="0", census_type=CensusType.COUNTY, name="Orleans Parish")
        assert mint_disambiguated(row) == "ocd-division/country:us/state:la/parish:orleans_parish"
