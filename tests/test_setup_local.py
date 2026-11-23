import pytest
from scripts.jurisdictions import local
from scripts.jurisdictions.local import (
    create_geoid,
    census_row,
    get_api_data_by_geoid,
)
from scripts.jurisdictions.yaml_io import get_names


# ── get_names ─────────────────────────────────────────────────────────────────

class TestGetNames:
    def test_simple_place(self):
        assert get_names("Gervais city, Oregon") == ("gervais", "Gervais city")

    def test_multi_word_place(self):
        assert get_names("El Paso city, Texas") == ("el_paso", "El Paso city")

    def test_two_word_place(self):
        assert get_names("New York city, New York") == ("new_york", "New York city")

    def test_township(self):
        assert get_names("Springfield township, Morris County, New Jersey") == (
            "springfield",
            "Springfield township",
        )

    def test_multi_word_township(self):
        assert get_names("Buena Vista township, Mercer County, New Jersey") == (
            "buena_vista",
            "Buena Vista township",
        )

    def test_single_word_place(self):
        assert get_names("Portland city, Oregon") == ("portland", "Portland city")

    def test_friendly_name_preserves_case(self):
        _, friendly = get_names("Mount Pleasant city, South Carolina")
        assert friendly == "Mount Pleasant city"

    def test_jurisdiction_name_is_lowercase(self):
        jurisdiction, _ = get_names("Mount Pleasant city, South Carolina")
        assert jurisdiction == "mount_pleasant"


# ── create_geoid ──────────────────────────────────────────────────────────────

class TestCreateGeoid:
    def test_place(self):
        # ACS row: [NAME, population, state, place]
        row = ["Seattle city, Washington", "741440", "53", "63000"]
        assert create_geoid("53", "place", row) == "5363000"

    def test_place_zero_padded(self):
        row = ["Abbeville city, South Carolina", "4874", "45", "00100"]
        assert create_geoid("45", "place", row) == "4500100"

    def test_county_subdivision(self):
        # ACS row: [NAME, population, state, county, cousub]
        row = ["Springfield township, Morris County, New Jersey", "12345", "34", "027", "70450"]
        assert create_geoid("34", "county_subdivision", row) == "3402770450"


# ── census_row ────────────────────────────────────────────────────────────────

class TestCensusRow:
    def test_place(self):
        row = census_row("wa", "5363000", "Seattle city, Washington", "place")
        assert (row.name, row.county_name) == ("Seattle city", None)

    def test_county_subdivision_keeps_county(self):
        row = census_row("nj", "3402770450", "Springfield township, Morris County, New Jersey", "county_subdivision")
        assert (row.name, row.county_name) == ("Springfield township", "Morris County")


# ── get_api_data_by_geoid ─────────────────────────────────────────────────────

class TestGetApiDataByGeoid:
    def _make_row(self, name, population, state, place):
        return [name, str(population), state, place]

    def test_basic_structure(self):
        rows = [self._make_row("Seattle city, Washington", 741440, "53", "63000")]
        result = get_api_data_by_geoid("wa", "53", rows, 1, "place")
        assert "5363000" in result
        entry = result["5363000"]
        assert entry["friendly_name"] == "Seattle city"
        assert entry["population"] == 741440
        assert entry["jurisdiction_ocdid"] == "ocd-jurisdiction/country:us/state:wa/place:seattle/government"

    def test_ocdid_collision_flagged(self, capsys):
        # Two places with different GEOIDs that resolve to the same OCD-ID
        rows = [
            self._make_row("Springfield city, Washington", 1000, "53", "11111"),
            self._make_row("Springfield city, Washington", 2000, "53", "22222"),
        ]
        result = get_api_data_by_geoid("wa", "53", rows, 1, "place")
        assert result["5311111"]["ocdid_collision"] is True
        assert result["5322222"]["ocdid_collision"] is True

    def test_registry_id_wins_over_generated_slug(self):
        # Registry drops the county segment for New England towns
        rows = [["Concord town, Middlesex County, Massachusetts", "18223", "25", "017", "15060"]]
        registry = {"2501715060": "ocd-division/country:us/state:ma/place:concord"}
        result = get_api_data_by_geoid("ma", "25", rows, 1, "county_subdivision", registry_by_geoid=registry)
        assert result["2501715060"]["jurisdiction_ocdid"] == (
            "ocd-jurisdiction/country:us/state:ma/place:concord/government"
        )

    def test_generated_slug_when_geoid_not_in_registry(self):
        rows = [self._make_row("Seattle city, Washington", 741440, "53", "63000")]
        result = get_api_data_by_geoid("wa", "53", rows, 1, "place", registry_by_geoid={})
        assert result["5363000"]["jurisdiction_ocdid"] == (
            "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
        )

    def test_no_collision_when_names_differ(self):
        rows = [
            self._make_row("Portland city, Washington", 1000, "53", "11111"),
            self._make_row("Seattle city, Washington", 2000, "53", "22222"),
        ]
        result = get_api_data_by_geoid("wa", "53", rows, 1, "place")
        assert "ocdid_collision" not in result["5311111"]
        assert "ocdid_collision" not in result["5322222"]


# ── _fetch_census_jurisdictions ───────────────────────────────────────────────

ACS_PLACES = [
    ["NAME", "B01003_001E", "state", "place"],
    ["Mountain House CDP, California", "25513", "06", "49582"],
    ["La Cañada Flintridge city, California", "19935", "06", "39003"],
]
GAZETTEER_PLACES = (
    "USPS|GEOID|GEOIDFQ|ANSICODE|NAME|LSAD|FUNCSTAT|ALAND|AWATER|ALAND_SQMI|AWATER_SQMI|INTPTLAT|INTPTLONG\n"
    "CA|0649582|1600000US0649582|02832399|Mountain House city|25|A|19259222|11895|7.436|0.005|37.779716|-121.537195\n"
    "CA|0639003|1600000US0639003|02411565|La Cañada Flintridge city|25|A|22354266|42498|8.631|0.016|34.20969|-118.200139\n"
)


class _CensusResponse:
    def __init__(self, url: str):
        self.status_code = 200
        # The Gazetteer is UTF-8 served as text/plain with no charset, so requests' .text decodes it as Latin-1.
        self.content = b"" if "api.census.gov" in url else GAZETTEER_PLACES.encode("utf-8")
        self.text = self.content.decode("iso-8859-1")

    def json(self):
        return ACS_PLACES


def _fetch_places(monkeypatch):
    monkeypatch.setenv("CENSUS_API_KEY", "test-key")
    monkeypatch.setattr(local.requests, "get", _CensusResponse)
    jurisdictions, _warnings = local._fetch_census_jurisdictions("ca", "06", local._PLACE)
    return {j.geoid: j for j in jurisdictions}


class TestFetchCensusJurisdictions:
    def test_name_comes_from_the_gazetteer_and_population_from_acs(self, monkeypatch):
        mountain_house = _fetch_places(monkeypatch)["0649582"]
        assert (mountain_house.name, mountain_house.population) == ("Mountain House city", 25513)

    def test_the_gazetteer_is_read_as_utf8(self, monkeypatch):
        assert _fetch_places(monkeypatch)["0639003"].name == "La Cañada Flintridge city"
