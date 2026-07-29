from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import yaml

from scripts.jurisdictions.counties import pull_county_jurisdiction_data


def _fake_acs_response(fips: str, counties: list[tuple[str, int, str]]):
    """Build a mock ACS API response for counties."""
    header = ["NAME", "B01003_001E", "state", "county"]
    rows = [[name, str(pop), fips, code] for name, pop, code in counties]
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = [header] + rows
    return mock


SC_COUNTIES = [
    ("Greenville County, South Carolina", 545000, "045"),
    ("Richland County, South Carolina", 420000, "079"),
    ("Charleston County, South Carolina", 420000, "019"),
]


class TestPullCountyJurisdictionData:
    def _run(self, tmp_path: Path, counties=SC_COUNTIES):
        fake_response = _fake_acs_response("45", counties)
        # skip_wiki: these cover the census → YAML path. Patching requests.get here also
        # patches it for wikipedia_utils (same module object), so the scrape would
        # otherwise be handed the ACS payload. Wiki enrichment is covered separately.
        with patch("scripts.jurisdictions.counties.requests.get", return_value=fake_response), \
             patch("scripts.jurisdictions.counties.PROJECT_ROOT", tmp_path):
            pull_county_jurisdiction_data("sc", skip_wiki=True)

        return tmp_path / "data_source" / "sc" / "counties" / "jurisdictions.yml"

    def test_creates_jurisdictions_file(self, tmp_path):
        path = self._run(tmp_path)
        assert path.exists()

    def test_correct_number_of_entries(self, tmp_path):
        path = self._run(tmp_path)
        doc = yaml.safe_load(path.read_text())
        assert len(doc["jurisdictions"]) == len(SC_COUNTIES)

    def test_ocdid_format(self, tmp_path):
        path = self._run(tmp_path)
        doc = yaml.safe_load(path.read_text())
        for j in doc["jurisdictions"]:
            assert j["id"].startswith("ocd-jurisdiction/country:us/state:sc/county:")
            assert j["id"].endswith("/government")

    def test_geoid_format(self, tmp_path):
        path = self._run(tmp_path)
        doc = yaml.safe_load(path.read_text())
        geoids = {j["geoid"] for j in doc["jurisdictions"]}
        assert "45045" in geoids   # Greenville
        assert "45079" in geoids   # Richland
        assert "45019" in geoids   # Charleston

    def test_sorted_by_population_descending(self, tmp_path):
        path = self._run(tmp_path)
        doc = yaml.safe_load(path.read_text())
        populations = [j["population"] for j in doc["jurisdictions"]]
        assert populations == sorted(populations, reverse=True)

    def test_zero_population_excluded(self, tmp_path):
        counties_with_zero = SC_COUNTIES + [("Empty County, South Carolina", 0, "999")]
        path = self._run(tmp_path, counties_with_zero)
        doc = yaml.safe_load(path.read_text())
        assert len(doc["jurisdictions"]) == len(SC_COUNTIES)

    def test_preserves_existing_ocdid_on_rerun(self, tmp_path):
        # First run
        self._run(tmp_path)
        path = tmp_path / "data_source" / "sc" / "counties" / "jurisdictions.yml"
        doc = yaml.safe_load(path.read_text())
        original_ids = {j["geoid"]: j["id"] for j in doc["jurisdictions"]}

        # Second run with same data — OCD-IDs must be unchanged
        self._run(tmp_path)
        doc2 = yaml.safe_load(path.read_text())
        for j in doc2["jurisdictions"]:
            assert j["id"] == original_ids[j["geoid"]]

    def test_census_rename_keeps_the_original_ocdid(self, tmp_path):
        """A Census name change must not mint a new OCD-ID — GEOID is the stable key.

        Distinct from the re-run test above: there the OCD-ID is untouched because the
        name is identical, so the reconciliation branch never runs. Here the name
        changes, which would otherwise produce `county:greenville_county/government`.
        """
        self._run(tmp_path)
        path = tmp_path / "data_source" / "sc" / "counties" / "jurisdictions.yml"

        renamed = [("Greenville County County, South Carolina", 545000, "045")] + SC_COUNTIES[1:]
        self._run(tmp_path, renamed)

        doc = yaml.safe_load(path.read_text())
        by_geoid = {j["geoid"]: j for j in doc["jurisdictions"]}
        assert by_geoid["45045"]["id"] == (
            "ocd-jurisdiction/country:us/state:sc/county:greenville/government"
        )
        # The renamed county must not appear twice under two OCD-IDs
        assert len(doc["jurisdictions"]) == len(SC_COUNTIES)
        # …and the display name does follow Census
        assert by_geoid["45045"]["name"] == "Greenville County County"

    def test_api_failure_does_not_write(self, tmp_path):
        bad_response = MagicMock()
        bad_response.status_code = 500
        with patch("scripts.jurisdictions.counties.requests.get", return_value=bad_response), \
             patch("scripts.jurisdictions.counties.PROJECT_ROOT", tmp_path):
            pull_county_jurisdiction_data("sc", skip_wiki=True)
        path = tmp_path / "data_source" / "sc" / "counties" / "jurisdictions.yml"
        assert not path.exists()


class TestCountyWikipediaEnrichment:
    """The county scrape sources its GEOID from the list table, not the infobox."""

    def _run_with_wiki(self, tmp_path: Path, scraped):
        """Run the pipeline with the wiki scrape stubbed to apply `scraped`."""
        fake_response = _fake_acs_response("45", SC_COUNTIES)

        def fake_scrape(census_data, state, state_name, fips, limit=None):
            for ocdid, jurisdiction in census_data.items():
                for field, value in scraped.get(ocdid, {}).items():
                    setattr(jurisdiction, field, value)
            return census_data, []

        with patch("scripts.jurisdictions.counties.requests.get", return_value=fake_response), \
             patch("scripts.jurisdictions.counties.PROJECT_ROOT", tmp_path), \
             patch("scripts.jurisdictions.counties.counties_scraper.scrape", side_effect=fake_scrape):
            pull_county_jurisdiction_data("sc")

        path = tmp_path / "data_source" / "sc" / "counties" / "jurisdictions.yml"
        return yaml.safe_load(path.read_text())

    GREENVILLE = "ocd-jurisdiction/country:us/state:sc/county:greenville/government"

    def test_writes_url_and_wiki_url(self, tmp_path):
        doc = self._run_with_wiki(tmp_path, {
            self.GREENVILLE: {
                "url": "https://www.greenvillecounty.org",
                "wiki_url": "https://en.wikipedia.org/wiki/Greenville_County,_South_Carolina",
            },
        })
        entry = next(j for j in doc["jurisdictions"] if j["id"] == self.GREENVILLE)
        assert entry["url"] == "https://www.greenvillecounty.org"
        assert entry["wiki_url"].endswith("Greenville_County,_South_Carolina")

    # The tests below seed a bare run first, so the second run takes the *existing
    # entry* branch of the writeback. That is what every real first-enrichment run
    # does — an entry already in the YAML that the scraper is filling in for the
    # first time — and it is a different code path from creating a new record.

    def test_enriches_an_existing_bare_entry(self, tmp_path):
        self._run_with_wiki(tmp_path, {})  # entry exists with no url/wiki_url
        doc = self._run_with_wiki(tmp_path, {
            self.GREENVILLE: {"url": "https://found.example", "wiki_url": "https://wiki/found"},
        })
        entry = next(j for j in doc["jurisdictions"] if j["id"] == self.GREENVILLE)
        assert entry["url"] == "https://found.example"
        assert entry["wiki_url"] == "https://wiki/found"

    def test_sets_issues_on_an_existing_entry(self, tmp_path):
        self._run_with_wiki(tmp_path, {})
        doc = self._run_with_wiki(tmp_path, {
            self.GREENVILLE: {"issues": ["no_wiki_match"]},
        })
        entry = next(j for j in doc["jurisdictions"] if j["id"] == self.GREENVILLE)
        assert entry["issues"] == ["no_wiki_match"]

    def test_sets_and_clears_generated_comments_on_an_existing_entry(self, tmp_path):
        self._run_with_wiki(tmp_path, {})
        doc = self._run_with_wiki(tmp_path, {
            self.GREENVILLE: {"generated_comments": "Wiki URL candidates: https://wiki/a"},
        })
        entry = next(j for j in doc["jurisdictions"] if j["id"] == self.GREENVILLE)
        assert entry["generated_comments"] == "Wiki URL candidates: https://wiki/a"

        # Resolved on the next run — the stale note must not linger
        doc = self._run_with_wiki(tmp_path, {
            self.GREENVILLE: {"wiki_url": "https://wiki/found"},
        })
        entry = next(j for j in doc["jurisdictions"] if j["id"] == self.GREENVILLE)
        assert "generated_comments" not in entry

    def test_human_comments_survive_enrichment(self, tmp_path):
        self._run_with_wiki(tmp_path, {})
        path = tmp_path / "data_source" / "sc" / "counties" / "jurisdictions.yml"
        doc = yaml.safe_load(path.read_text())
        for j in doc["jurisdictions"]:
            if j["id"] == self.GREENVILLE:
                j["comments"] = "hand-checked 2026-07"
        path.write_text(yaml.safe_dump(doc))

        doc = self._run_with_wiki(tmp_path, {
            self.GREENVILLE: {"url": "https://found.example", "wiki_url": "https://wiki/found"},
        })
        entry = next(j for j in doc["jurisdictions"] if j["id"] == self.GREENVILLE)
        assert entry["comments"] == "hand-checked 2026-07"
        assert entry["url"] == "https://found.example"

    def test_url_is_write_once_but_wiki_url_refreshes(self, tmp_path):
        self._run_with_wiki(tmp_path, {
            self.GREENVILLE: {"url": "https://original.example", "wiki_url": "https://wiki/v1"},
        })
        # Second run finds a different website — the existing url must survive
        doc = self._run_with_wiki(tmp_path, {
            self.GREENVILLE: {"url": "https://replacement.example", "wiki_url": "https://wiki/v2"},
        })
        entry = next(j for j in doc["jurisdictions"] if j["id"] == self.GREENVILLE)
        assert entry["url"] == "https://original.example"
        assert entry["wiki_url"] == "https://wiki/v2"

    def test_issues_are_cleared_when_resolved(self, tmp_path):
        self._run_with_wiki(tmp_path, {self.GREENVILLE: {"issues": ["no_wiki_match"]}})
        doc = self._run_with_wiki(tmp_path, {
            self.GREENVILLE: {"wiki_url": "https://wiki/found"},
        })
        entry = next(j for j in doc["jurisdictions"] if j["id"] == self.GREENVILLE)
        assert "issues" not in entry
