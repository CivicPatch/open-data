"""Check every generated jurisdiction OCD-ID against the official OCD division registry.

Reads the pinned registry copy (see scripts/ocdids/registry.py).
"""

from pathlib import Path

import pytest

from scripts.jurisdictions.yaml_io import load_existing_jurisdictions, ryaml
from scripts.ocdids import registry_report
from scripts.ocdids.ids import to_division_ocdid
from scripts.ocdids.migrate_plan import find_moves
from scripts.ocdids.registry import load_registry
from scripts.ocdids.stored import stored_states
from scripts.paths import PROJECT_ROOT

JURISDICTION_FILES = sorted(PROJECT_ROOT.glob("data_source/*/*/jurisdictions.yml"))


@pytest.fixture(scope="module")
def known_unregistered():
    """Division IDs data_source/ocdid_mismatches.yml records as minted by us, not in the registry."""
    report = ryaml.load(registry_report.REPORT_PATH.read_text())
    return {row["minted"] for rows in report["not_in_registry"].values() for row in rows}


@pytest.mark.parametrize(
    "path", JURISDICTION_FILES, ids=lambda p: str(p.parent.relative_to(PROJECT_ROOT / "data_source"))
)
def test_jurisdiction_ocdids_in_registry(path: Path, known_unregistered):
    registry_ids = load_registry().division_ocdids
    _doc, existing_by_id = load_existing_jurisdictions(path)

    missing = []
    for jurisdiction_ocdid in existing_by_id:
        division_ocdid = to_division_ocdid(jurisdiction_ocdid)
        if division_ocdid not in registry_ids and division_ocdid not in known_unregistered:
            missing.append(division_ocdid)
    assert not missing, (
        f"{len(missing)}/{len(existing_by_id)} OCD-IDs in {path.relative_to(PROJECT_ROOT)} are "
        f"neither in the OCD registry nor listed in data_source/ocdid_mismatches.yml — run "
        f"`uv run python -m scripts.ocdids.migrate_to_registry <state>`:\n  " + "\n  ".join(sorted(missing))
    )


@pytest.mark.parametrize("state", stored_states())
def test_stored_ocdids_match_assigned(state: str):
    """Stronger than being in the registry: each ID is the one assigned for its own GEOID."""
    stored, assignments = registry_report.assign_state(state, load_registry())
    moves = find_moves(stored, assignments)
    assert not moves, (
        f"{len(moves)} OCD-IDs in {state} differ from the ID assigned for their GEOID — run "
        f"`uv run python -m scripts.ocdids.migrate_to_registry {state}`:\n  "
        + "\n  ".join(f"{move.old_id} → {move.new_id}" for move in moves)
    )


def test_mismatch_report_is_current():
    assert registry_report.REPORT_PATH.read_text() == registry_report.current_report(), (
        "data_source/ocdid_mismatches.yml is stale — run `uv run python -m scripts.ocdids.registry_report`"
    )
