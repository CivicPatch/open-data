"""The data validator accepts records in the shape civicpatch.org publishes, and rejects a bad one."""

from pathlib import Path

import yaml

from scripts.github_actions.validate_data_files import validate_file

PUBLISHED_PERSON = {
    "id": "a8ec1bbd-bad7-43fa-aeda-dedcb0562d71",
    "name": "Emma Mulvaney-Stanak",
    "other_names": [],
    "phones": ["(802) 865-7272"],
    "emails": [],
    "urls": ["https://www.burlingtonvt.gov/476/Mayor-Emma-Mulvaney-Stanak"],
    "source_urls": ["https://www.burlingtonvt.gov/476/Mayor-Emma-Mulvaney-Stanak"],
    "updated_at": "2026-11-20T19:25:27+00:00",
    "roles": [
        {
            "name": "Mayor",
            "role_id": "mayor",
            "jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:vt/place:burlington/government",
            "division_ocdid": "ocd-division/country:us/state:vt/place:burlington",
        }
    ],
}


def _write(tmp_path: Path, people: list[dict]) -> str:
    path = tmp_path / "place_burlington.yml"
    path.write_text(yaml.safe_dump(people))
    return str(path)


def test_a_published_record_is_valid(tmp_path: Path):
    assert validate_file(_write(tmp_path, [PUBLISHED_PERSON])) == []


def test_a_record_without_a_name_is_reported(tmp_path: Path):
    nameless = {key: value for key, value in PUBLISHED_PERSON.items() if key != "name"}
    errors = validate_file(_write(tmp_path, [nameless]))
    assert len(errors) == 1
