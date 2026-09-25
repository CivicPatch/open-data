#!/usr/bin/env python3
"""
Move a state's stored OCD-IDs to the ones the generators now assign: the registry's ID by
Census GEOID, else one minted with the registry's rules (scripts/ocdids/assign.py).

The generators keep an existing entry's ID when its GEOID is already known, so older IDs
stay put until this script moves them. For every entry whose ID changes it updates:

  - data_source/<st>/{state,counties,local}/jurisdictions.yml — `id`, `parent_ocdids`
  - data/<st>/local/*.yml — renamed; every OCD-ID in the records (and their children,
    e.g. /ward:2) rewritten
  - data_source/<st>/local/<folder>/ — renamed; OCD-IDs in its *.json files rewritten

An ID shared by two entries (a past collision) gets its jurisdictions.yml entries fixed,
but its files are left alone: they belong to one of the entries and the ID can't say which.

Generated outputs (scripts/track_progress/data, data_source/<st>/local/validation) are not
touched — regenerate them afterwards.

Usage:
    uv run python -m scripts.ocdids.migrate_to_registry ma --dry-run
    uv run python -m scripts.ocdids.migrate_to_registry ma
"""

import argparse
import json
import sys
from typing import List

from shared.utils.yaml_utils import yaml_dump, yaml_load

from scripts.jurisdictions.yaml_io import ryaml
from scripts.ocdids.migrate_plan import MigrationPlan, Rename, entry_changes, plan_migration, rewrite_tree
from scripts.ocdids.registry import load_registry
from scripts.ocdids.registry_report import assign_state
from scripts.ocdids.stored import Level, jurisdictions_path
from scripts.paths import PROJECT_ROOT


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("state", help="State code, e.g. ma")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change; change nothing")
    args = parser.parse_args()
    state = args.state.lower()

    stored, assignments = assign_state(state, load_registry())
    plan = plan_migration(state, stored, assignments)
    if not plan.moves:
        print(f"{state}: all OCD-IDs already match.")
        return 0

    renames = renames_on_disk(plan)
    problems = find_problems(plan, renames)
    if problems:
        print(f"{state}: refusing to migrate —")
        for problem in problems:
            print(f"  {problem}")
        return 1

    print_plan(plan, renames)
    if not args.dry_run:
        apply_plan(plan, renames)
        print("Done. Next: uv run pytest tests/test_ocdid_registry.py, and regenerate track_progress/validation outputs.")
    return 0


def renames_on_disk(plan: MigrationPlan) -> List[Rename]:
    return [rename for rename in plan.renames if rename.source.exists() and rename.source != rename.target]


def find_problems(plan: MigrationPlan, renames: List[Rename]) -> List[str]:
    problems = [f"two entries would share {ocdid}" for ocdid in plan.collisions]
    for rename in renames:
        if rename.target.exists():
            problems.append(f"{rename.target.relative_to(PROJECT_ROOT)} already exists")
    return problems


def print_plan(plan: MigrationPlan, renames: List[Rename]) -> None:
    for move in plan.moves:
        print(f"  {move.old_id}\n    → {move.new_id}")
    print(f"\n{plan.state}: {len(plan.moves)} OCD-IDs change, {len(renames)} files/folders renamed.")
    for move in plan.moves:
        if move.ambiguous:
            print(f"  ⚠ {move.old_id} was shared by several entries — its files were left in place; "
                  f"check they belong to the entry that kept it")


def apply_plan(plan: MigrationPlan, renames: List[Rename]) -> None:
    update_jurisdiction_files(plan)
    for rename in renames:
        rename.source.rename(rename.target)
    rewrite_officials_files(plan)
    rewrite_pipeline_files(plan, renames)


def update_jurisdiction_files(plan: MigrationPlan) -> None:
    for level in Level:
        path = jurisdictions_path(plan.state, level)
        if not path.exists():
            continue
        # Edited in place rather than rebuilt: ruamel keeps the file's comments on these objects
        document = ryaml.load(path.read_text())
        changed = False
        for entry in document.get("jurisdictions") or []:
            changes = entry_changes(plan, entry.get("geoid"), entry.get("parent_ocdids"))
            if changes:
                entry.update(changes)
                changed = True
        if changed:
            with open(path, "w") as f:
                ryaml.dump(document, f)


def rewrite_officials_files(plan: MigrationPlan) -> None:
    # Every file in the state: a file can reference an ID other than its own
    for path in sorted((PROJECT_ROOT / "data" / plan.state / "local").glob("*.yml")):
        records = yaml_load(path.read_text())
        rewritten = rewrite_tree(records, plan.rewrites)
        if rewritten != records:
            path.write_text(yaml_dump(rewritten))


def rewrite_pipeline_files(plan: MigrationPlan, renames: List[Rename]) -> None:
    for rename in renames:
        if not rename.target.is_dir():
            continue
        for path in sorted(rename.target.glob("*.json")):
            data = json.loads(path.read_text())
            rewritten = rewrite_tree(data, plan.rewrites)
            if rewritten != data:
                path.write_text(json.dumps(rewritten, indent=4, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
