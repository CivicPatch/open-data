"""Every config file merges: the country's roles (data_source/config.yml), the country's forms
for a level (data_source/{level}/config.yml), then a state's (data_source/{state}/{level}/config.yml).
The check a config edit must pass before it merges."""

from pathlib import Path

import pytest
import yaml

from shared.schemas import JurisdictionLevel
from shared.utils.layered_config import ConfigFile, check_roles_distinct_across, merged_config

DATA_SOURCE = Path(__file__).parent.parent / "data_source"
LEVELS = [JurisdictionLevel.LOCAL, JurisdictionLevel.COUNTIES]
CONFIG_FILE = "config.yml"


def _load(path: Path) -> ConfigFile:
    if not path.exists():
        return ConfigFile()
    return ConfigFile.model_validate(yaml.safe_load(path.read_text()) or {})


def _country_roles() -> ConfigFile:
    return _load(DATA_SOURCE / CONFIG_FILE)


def _country_forms(level: str) -> ConfigFile:
    return _load(DATA_SOURCE / level / CONFIG_FILE)


def _state_files() -> list[Path]:
    return sorted(path for level in LEVELS for path in DATA_SOURCE.glob(f"*/{level}/{CONFIG_FILE}"))


@pytest.mark.parametrize("level", LEVELS)
def test_country_files_are_valid(level: JurisdictionLevel):
    merged_config(_country_roles(), _country_forms(level), None)


@pytest.mark.parametrize("state_file", _state_files(), ids=lambda path: str(path.relative_to(DATA_SOURCE)))
def test_state_file_merges_with_the_country_files(state_file: Path):
    merged_config(_country_roles(), _country_forms(state_file.parent.name), _load(state_file))


def test_no_two_files_share_a_role_id_label_or_alias():
    check_roles_distinct_across([_country_roles(), *(_load(path) for path in _state_files())])


def _jurisdiction_files() -> list[Path]:
    return sorted(path for level in LEVELS for path in DATA_SOURCE.glob(f"*/{level}/jurisdictions.yml"))


@pytest.mark.parametrize("jurisdictions_file", _jurisdiction_files(), ids=lambda path: str(path.relative_to(DATA_SOURCE)))
def test_every_government_form_is_a_form_of_its_level(jurisdictions_file: Path):
    """Any form of the level, not only those the state's file allows: a charter county can
    differ from the rest of its state."""
    level_forms = _country_forms(jurisdictions_file.parent.name).government_forms
    entries = (yaml.safe_load(jurisdictions_file.read_text()) or {}).get("jurisdictions") or []
    level_values = {form.value for form in level_forms}
    wrong = []
    for entry in entries:
        form = (entry.get("extras") or {}).get("government_form")
        if form is not None and form not in level_values:
            wrong.append((entry["id"], form))
    assert wrong == [], f"not a {jurisdictions_file.parent.name} form: {wrong}"
