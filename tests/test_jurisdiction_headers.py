from scripts.jurisdictions import headers as h
from scripts.jurisdictions.config import state_configs

ALL_HEADERS = "all"


def _every_header():
    """One header of each kind, for invariants that must hold across all of them."""
    return [
        h.state_header("nc", "37"),
        h.county_header("nc", "37", "North Carolina"),
        h.local_header("nh", "33", "New Hampshire", ["places", "county_subdivisions"]),
    ]


class TestSecrets:
    def test_api_key_is_a_shell_variable_never_a_value(self):
        """Headers are committed to git — the key must only ever appear as $CENSUS_API_KEY."""
        for header in _every_header():
            assert "key=$CENSUS_API_KEY" in header
            # A real Census key is a 40-char hex string; make sure nothing like one is here
            assert "key=" not in header.replace("key=$CENSUS_API_KEY", "")


class TestProvenance:
    def test_every_header_names_its_generating_script_by_real_path(self):
        """The path is what a reader runs to regenerate — it must not go stale on a move."""
        import pathlib

        cases = [
            ("scripts/jurisdictions/states.py", h.state_header("nc", "37")),
            ("scripts/jurisdictions/counties.py", h.county_header("nc", "37", "North Carolina")),
            ("scripts/jurisdictions/local.py", h.local_header("nc", "37", "North Carolina", ["places"])),
        ]
        repo_root = pathlib.Path(__file__).resolve().parent.parent
        for script_path, header in cases:
            assert script_path in header
            assert (repo_root / script_path).exists(), f"{script_path} cited but does not exist"

    def test_every_header_has_a_sources_section(self):
        for header in _every_header():
            assert "Sources:" in header

    def test_county_header_cites_the_acs_call_and_wiki_page(self):
        header = h.county_header("nc", "37", "North Carolina")
        assert 'curl "https://api.census.gov/data/2024/acs/acs5?get=NAME,B01003_001E&for=county:*&in=state:37&key=$CENSUS_API_KEY"' in header
        assert "https://en.wikipedia.org/wiki/List_of_counties_in_North_Carolina" in header
        assert "tl_2025_us_county.zip" in header
        assert "scripts/jurisdictions/scrapers/cache/nc_counties_wikipedia.json" in header

    def test_multiword_state_names_become_wiki_titles(self):
        assert "List_of_counties_in_North_Carolina" in h.county_header("nc", "37", "North Carolina")
        assert "List_of_municipalities_in_New_Hampshire" in h.local_header(
            "nh", "33", "New Hampshire", ["places"])

    def test_state_header_cites_the_state_scoped_acs_call(self):
        header = h.state_header("wa", "53")
        assert "for=state:53" in header
        assert "tl_2025_us_state.zip" in header


class TestLocalHeaderFollowsCensusSources:
    def test_places_only_state_cites_one_call_and_one_gazetteer(self):
        header = h.local_header("nc", "37", "North Carolina", ["places"])
        assert "for=place:*" in header
        assert "2025_gaz_place_37.txt" in header
        # No county-subdivision sources for a places-only state
        assert "county%20subdivision" not in header
        assert "gaz_cousubs" not in header
        assert "cousub.zip" not in header

    def test_mcd_state_cites_both_calls_and_both_gazetteers(self):
        header = h.local_header("nh", "33", "New Hampshire", ["places", "county_subdivisions"])
        assert "for=place:*" in header
        assert "for=county%20subdivision:*" in header
        assert "2025_gaz_place_33.txt" in header
        assert "2025_gaz_cousubs_33.txt" in header
        assert "tl_2025_33_place.zip" in header
        assert "tl_2025_33_cousub.zip" in header

    def test_notes_the_county_file_the_spatial_join_depends_on(self):
        header = h.local_header("nc", "37", "North Carolina", ["places"])
        assert "data_source/nc/counties/jurisdictions.yml" in header


class TestEveryConfiguredStateRenders:
    def test_all_three_headers_render_for_every_registered_state(self):
        """Guards against a state config missing `name` or an unknown census source."""
        for state, config in state_configs.items():
            h.state_header(state, config["fips"])
            h.county_header(state, config["fips"], config["name"])
            h.local_header(state, config["fips"], config["name"], config["pull_from_census"])
