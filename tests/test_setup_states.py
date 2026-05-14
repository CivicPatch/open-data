from unittest.mock import patch, MagicMock
from pathlib import Path
import yaml

from scripts.setup_states import pull_state_jurisdiction_data


def _fake_acs_response(name: str, population: int, fips: str):
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = [
        ["NAME", "B01003_001E", "state"],
        [name, str(population), fips],
    ]
    return mock


class TestPullStateJurisdictionData:
    def _run(self, tmp_path: Path, name="South Carolina", pop=5282634):
        fake_response = _fake_acs_response(name, pop, "45")
        with patch("scripts.setup_states.requests.get", return_value=fake_response), \
             patch("scripts.setup_states.PROJECT_ROOT", tmp_path):
            pull_state_jurisdiction_data("sc")
        return tmp_path / "data_source" / "sc" / "state" / "jurisdictions.yml"

    def test_creates_jurisdictions_file(self, tmp_path):
        assert self._run(tmp_path).exists()

    def test_single_entry(self, tmp_path):
        doc = yaml.safe_load(self._run(tmp_path).read_text())
        assert len(doc["jurisdictions"]) == 1

    def test_ocdid_format(self, tmp_path):
        doc = yaml.safe_load(self._run(tmp_path).read_text())
        assert doc["jurisdictions"][0]["id"] == "ocd-jurisdiction/country:us/state:sc/government"

    def test_geoid_is_state_fips(self, tmp_path):
        doc = yaml.safe_load(self._run(tmp_path).read_text())
        assert doc["jurisdictions"][0]["geoid"] == "45"

    def test_population_written(self, tmp_path):
        doc = yaml.safe_load(self._run(tmp_path).read_text())
        assert doc["jurisdictions"][0]["population"] == 5282634

    def test_population_updated_on_rerun(self, tmp_path):
        self._run(tmp_path, pop=5282634)
        fake_response = _fake_acs_response("South Carolina", 5400000, "45")
        with patch("scripts.setup_states.requests.get", return_value=fake_response), \
             patch("scripts.setup_states.PROJECT_ROOT", tmp_path):
            pull_state_jurisdiction_data("sc")
        path = tmp_path / "data_source" / "sc" / "state" / "jurisdictions.yml"
        doc = yaml.safe_load(path.read_text())
        assert doc["jurisdictions"][0]["population"] == 5400000

    def test_ocdid_stable_across_reruns(self, tmp_path):
        self._run(tmp_path)
        self._run(tmp_path, pop=9999999)
        doc = yaml.safe_load(self._run(tmp_path).read_text())
        assert doc["jurisdictions"][0]["id"] == "ocd-jurisdiction/country:us/state:sc/government"

    def test_api_failure_does_not_write(self, tmp_path):
        bad_response = MagicMock()
        bad_response.status_code = 500
        with patch("scripts.setup_states.requests.get", return_value=bad_response), \
             patch("scripts.setup_states.PROJECT_ROOT", tmp_path):
            pull_state_jurisdiction_data("sc")
        assert not (tmp_path / "data_source" / "sc" / "state" / "jurisdictions.yml").exists()
