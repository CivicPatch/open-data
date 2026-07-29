from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from scripts.jurisdictions.counties import pull_county_jurisdiction_data

MODULE = "scripts.jurisdictions.counties"
STATE = "sc"
FIPS = "45"

SC_COUNTIES = [
    ("Greenville County, South Carolina", 545000, "045"),
    ("Richland County, South Carolina", 420000, "079"),
    ("Charleston County, South Carolina", 420000, "019"),
]

GREENVILLE = f"ocd-jurisdiction/country:us/state:{STATE}/county:greenville/government"
RICHLAND = f"ocd-jurisdiction/country:us/state:{STATE}/county:richland/government"


def acs_response(counties=SC_COUNTIES, fips=FIPS, status=200):
    """Mock Census ACS county response."""
    mock = MagicMock()
    mock.status_code = status
    mock.json.return_value = [["NAME", "B01003_001E", "state", "county"]] + [
        [name, str(pop), fips, code] for name, pop, code in counties
    ]
    return mock


def yml_path(tmp_path: Path) -> Path:
    return tmp_path / "data_source" / STATE / "counties" / "jurisdictions.yml"


def read_yml(tmp_path: Path):
    return yaml.safe_load(yml_path(tmp_path).read_text())


def entry_for(doc, ocdid: str):
    return next(j for j in doc["jurisdictions"] if j["id"] == ocdid)


@contextmanager
def patched(tmp_path: Path, response, scrape=None):
    """Redirect the ACS call and output root; optionally stub the wiki scrape.

    Note `requests.get` is patched on the module object, so wikipedia_utils sees the
    mock too — which is why runs that don't stub the scrape must pass skip_wiki.
    """
    patches = [
        patch(f"{MODULE}.requests.get", return_value=response),
        patch(f"{MODULE}.PROJECT_ROOT", tmp_path),
    ]
    if scrape is not None:
        patches.append(patch(f"{MODULE}.counties_scraper.scrape", side_effect=scrape))
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        yield


def run_census_only(tmp_path: Path, counties=SC_COUNTIES, status=200) -> Path:
    """Census → YAML with no wiki enrichment. Also how a bare file legitimately appears."""
    with patched(tmp_path, acs_response(counties, status=status)):
        pull_county_jurisdiction_data(STATE, skip_wiki=True)
    return yml_path(tmp_path)


def run_with_scrape(tmp_path: Path, overrides=None):
    """Run with the wiki scrape stubbed.

    Every county matches by default, mirroring a real run where nearly all do — and
    keeping tests clear of the zero-match guard. Pass `overrides` to set fields on
    specific counties; use `wiki_url=None` to model one that did not match.
    """
    overrides = overrides or {}

    def fake_scrape(census_data, state, state_name, fips, limit=None):
        for ocdid, jurisdiction in census_data.items():
            slug = ocdid.split("county:")[1].split("/")[0]
            jurisdiction.wiki_url = f"https://wiki/{slug}"
            for field, value in overrides.get(ocdid, {}).items():
                setattr(jurisdiction, field, value)
        return census_data, []

    with patched(tmp_path, acs_response(), scrape=fake_scrape):
        pull_county_jurisdiction_data(STATE)
    return read_yml(tmp_path)


class TestCensusToYaml:
    def test_creates_jurisdictions_file(self, tmp_path):
        assert run_census_only(tmp_path).exists()

    def test_correct_number_of_entries(self, tmp_path):
        run_census_only(tmp_path)
        assert len(read_yml(tmp_path)["jurisdictions"]) == len(SC_COUNTIES)

    def test_ocdid_format(self, tmp_path):
        run_census_only(tmp_path)
        for j in read_yml(tmp_path)["jurisdictions"]:
            assert j["id"].startswith(f"ocd-jurisdiction/country:us/state:{STATE}/county:")
            assert j["id"].endswith("/government")

    def test_geoid_is_state_fips_plus_county_code(self, tmp_path):
        run_census_only(tmp_path)
        geoids = {j["geoid"] for j in read_yml(tmp_path)["jurisdictions"]}
        assert geoids == {"45045", "45079", "45019"}

    def test_sorted_by_population_descending(self, tmp_path):
        run_census_only(tmp_path)
        populations = [j["population"] for j in read_yml(tmp_path)["jurisdictions"]]
        assert populations == sorted(populations, reverse=True)

    def test_zero_population_excluded(self, tmp_path):
        run_census_only(tmp_path, SC_COUNTIES + [("Empty County, South Carolina", 0, "999")])
        assert len(read_yml(tmp_path)["jurisdictions"]) == len(SC_COUNTIES)

    def test_api_failure_does_not_write(self, tmp_path):
        run_census_only(tmp_path, status=500)
        assert not yml_path(tmp_path).exists()

    def test_preserves_existing_ocdid_on_rerun(self, tmp_path):
        run_census_only(tmp_path)
        original = {j["geoid"]: j["id"] for j in read_yml(tmp_path)["jurisdictions"]}

        run_census_only(tmp_path)
        for j in read_yml(tmp_path)["jurisdictions"]:
            assert j["id"] == original[j["geoid"]]

    def test_census_rename_keeps_the_original_ocdid(self, tmp_path):
        """A Census name change must not mint a new OCD-ID — GEOID is the stable key.

        Distinct from the re-run test above: there the name is identical so the
        reconciliation branch never runs. Here the name changes, which would otherwise
        produce `county:greenville_county/government`.
        """
        run_census_only(tmp_path)
        renamed = [("Greenville County County, South Carolina", 545000, "045")] + SC_COUNTIES[1:]
        run_census_only(tmp_path, renamed)

        doc = read_yml(tmp_path)
        by_geoid = {j["geoid"]: j for j in doc["jurisdictions"]}
        assert by_geoid["45045"]["id"] == GREENVILLE
        assert len(doc["jurisdictions"]) == len(SC_COUNTIES)   # not duplicated
        assert by_geoid["45045"]["name"] == "Greenville County County"  # name does follow


class TestWikipediaEnrichment:
    """Field-by-field write-back semantics of the wiki scrape."""

    def test_writes_url_and_wiki_url(self, tmp_path):
        doc = run_with_scrape(tmp_path, {
            GREENVILLE: {"url": "https://www.greenvillecounty.org"},
        })
        assert entry_for(doc, GREENVILLE)["url"] == "https://www.greenvillecounty.org"
        assert entry_for(doc, GREENVILLE)["wiki_url"] == "https://wiki/greenville"

    # The tests below seed a census-only file first, so the enriching run takes the
    # *existing entry* branch of the write-back. That is what every real
    # first-enrichment run does, and it is a different path from creating a new record.

    def test_enriches_an_existing_bare_entry(self, tmp_path):
        run_census_only(tmp_path)
        doc = run_with_scrape(tmp_path, {GREENVILLE: {"url": "https://found.example"}})
        assert entry_for(doc, GREENVILLE)["url"] == "https://found.example"
        assert entry_for(doc, GREENVILLE)["wiki_url"] == "https://wiki/greenville"

    def test_url_is_write_once_but_wiki_url_refreshes(self, tmp_path):
        run_with_scrape(tmp_path, {GREENVILLE: {"url": "https://original.example"}})
        doc = run_with_scrape(tmp_path, {
            GREENVILLE: {"url": "https://replacement.example", "wiki_url": "https://wiki/v2"},
        })
        assert entry_for(doc, GREENVILLE)["url"] == "https://original.example"
        assert entry_for(doc, GREENVILLE)["wiki_url"] == "https://wiki/v2"

    def test_sets_issues_on_an_existing_entry(self, tmp_path):
        run_census_only(tmp_path)
        doc = run_with_scrape(tmp_path, {
            GREENVILLE: {"wiki_url": None, "issues": ["no_wiki_match"]},
        })
        assert entry_for(doc, GREENVILLE)["issues"] == ["no_wiki_match"]

    def test_issues_are_cleared_when_resolved(self, tmp_path):
        run_census_only(tmp_path)
        run_with_scrape(tmp_path, {GREENVILLE: {"wiki_url": None, "issues": ["no_wiki_match"]}})
        doc = run_with_scrape(tmp_path)
        assert "issues" not in entry_for(doc, GREENVILLE)

    def test_sets_and_clears_generated_comments(self, tmp_path):
        run_census_only(tmp_path)
        doc = run_with_scrape(tmp_path, {
            GREENVILLE: {"wiki_url": None, "generated_comments": "Wiki URL candidates: x"},
        })
        assert entry_for(doc, GREENVILLE)["generated_comments"] == "Wiki URL candidates: x"

        doc = run_with_scrape(tmp_path)          # resolved — stale note must not linger
        assert "generated_comments" not in entry_for(doc, GREENVILLE)

    def test_human_comments_survive_enrichment(self, tmp_path):
        path = run_census_only(tmp_path)
        doc = yaml.safe_load(path.read_text())
        entry_for(doc, GREENVILLE)["comments"] = "hand-checked 2026-07"
        path.write_text(yaml.safe_dump(doc))

        doc = run_with_scrape(tmp_path, {GREENVILLE: {"url": "https://found.example"}})
        assert entry_for(doc, GREENVILLE)["comments"] == "hand-checked 2026-07"
        assert entry_for(doc, GREENVILLE)["url"] == "https://found.example"


class TestZeroMatchGuard:
    """A misread list table must not be persisted as an all-unmatched file."""

    def test_refuses_to_write_when_nothing_matched(self, tmp_path):
        def matches_nothing(census_data, state, state_name, fips, limit=None):
            for jurisdiction in census_data.values():
                jurisdiction.issues = ["no_wiki_match"]
            return census_data, ["No Wikipedia URL found for: Abbeville"]

        with patched(tmp_path, acs_response(), scrape=matches_nothing):
            with pytest.raises(SystemExit) as exc:
                pull_county_jurisdiction_data(STATE)

        assert "0/3 counties matched" in str(exc.value)
        assert not yml_path(tmp_path).exists()

    def test_writes_when_only_some_matched(self, tmp_path):
        doc = run_with_scrape(tmp_path, {GREENVILLE: {"wiki_url": None}})
        assert "wiki_url" not in entry_for(doc, GREENVILLE)
        assert entry_for(doc, RICHLAND)["wiki_url"] == "https://wiki/richland"
