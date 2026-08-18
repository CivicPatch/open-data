#!/usr/bin/env python3
"""Validate every person in the given data files. Paths arrive on stdin, one per line.

The companion to validate_jurisdiction.py, which takes an OCD-ID and derives the file from
it. That is the wrong way round for a post-push sweep: the reviewed and unreviewed copies of
a jurisdiction share an OCD-ID but live at different paths, so only a path can say which one
to read.

Runs on `main` after every data change rather than as a pre-merge gate. Civicpatch commits
scrapes here directly — unreviewed ones with nobody looking at them — so this is the check
that catches malformed records regardless of how they arrived, including by hand.

Exits non-zero if any record fails, so the workflow goes red.

Usage:
    git diff --name-only BEFORE AFTER -- 'data/**/*.yml' | python scripts/github_actions/validate_data_files.py
"""

import sys

import yaml

from shared.schemas import Official

# Enough to see the shape of the problem without burying the log in one bad file.
MAX_ERRORS_SHOWN = 5


def validate_file(file_path: str) -> list[str]:
    """Every record's validation error, as reportable strings. Empty means the file is good."""
    try:
        with open(file_path) as f:
            people = yaml.safe_load(f)
    except FileNotFoundError:
        # Deleted in the same push — nothing to validate, and not an error.
        return []
    except Exception as e:
        return [f"{file_path}: could not be read: {e}"]

    if not isinstance(people, list):
        return [f"{file_path}: expected a list of people, got {type(people).__name__}"]

    errors = []
    for index, person in enumerate(people):
        if not isinstance(person, dict):
            errors.append(f"{file_path}[{index}]: expected a mapping, got {type(person).__name__}")
            continue
        try:
            Official(**person)
        except Exception as e:
            name = person.get("name", "Unknown")
            errors.append(f"{file_path}[{index}] ({name}): {e}")
    return errors


def main() -> int:
    paths = [line.strip() for line in sys.stdin if line.strip()]
    if not paths:
        print("No data files changed — nothing to validate.")
        return 0

    print(f"Validating {len(paths)} changed data file(s)...")
    failed_files = 0
    for path in paths:
        errors = validate_file(path)
        if not errors:
            print(f"OK   {path}")
            continue
        failed_files += 1
        print(f"FAIL {path}: {len(errors)} invalid record(s)")
        for error in errors[:MAX_ERRORS_SHOWN]:
            print(f"       {error}")
        if len(errors) > MAX_ERRORS_SHOWN:
            print(f"       ... and {len(errors) - MAX_ERRORS_SHOWN} more")

    if failed_files:
        print(f"\n{failed_files} of {len(paths)} file(s) failed validation.")
        return 1

    print(f"\nAll {len(paths)} file(s) passed validation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
