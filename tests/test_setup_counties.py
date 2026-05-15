from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import yaml

from scripts.setup_counties import pull_county_jurisdiction_data


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
        with patch("scripts.setup_counties.requests.get", return_value=fake_response), \
             patch("scripts.setup_counties.PROJECT_ROOT", tmp_path):
            pull_county_jurisdiction_data("sc")

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

    def test_api_failure_does_not_write(self, tmp_path):
        bad_response = MagicMock()
        bad_response.status_code = 500
        with patch("scripts.setup_counties.requests.get", return_value=bad_response), \
             patch("scripts.setup_counties.PROJECT_ROOT", tmp_path):
            pull_county_jurisdiction_data("sc")
        path = tmp_path / "data_source" / "sc" / "counties" / "jurisdictions.yml"
        assert not path.exists()
