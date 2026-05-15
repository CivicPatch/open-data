#!/usr/bin/env python3
"""
One-off: copy images from civicpatch-artifacts → civicpatch bucket and
rewrite cdn_image URLs in all data YAML files.

Requires env vars: STORAGE_ENDPOINT, STORAGE_ACCESS_KEY_ID,
                   STORAGE_SECRET_ACCESS_KEY, FRIENDLY_STORAGE_HOST

Usage:
  python3 scripts/one_off/migrate_cdn_images.py [--dry-run] [jurisdiction_ocdid]

Examples:
  uv run python scripts/one_off/migrate_cdn_images.py --dry-run
  uv run python scripts/one_off/migrate_cdn_images.py ocd-jurisdiction/country:us/state:tx/place:hollywood_park/government
"""
import glob
import sys
from pathlib import Path
from ruamel.yaml import YAML

# Allow importing from the scripts package
sys.path.insert(0, str(Path(__file__).parents[2]))
from scripts.github_actions.local.post_merge.process_jurisdiction_data import update_images
from shared.utils.id_utils import jurisdiction_ocdid_to_folder

DRY_RUN = "--dry-run" in sys.argv
FILTER_OCDID = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
SOURCE_BUCKET = "civicpatch-artifacts"

yaml_io = YAML()
yaml_io.preserve_quotes = True

ROOT = Path(__file__).parents[2]
DATA_PATTERN = str(ROOT / "data" / "**" / "local" / "*.yml")


def needs_migration(people) -> bool:
    return any(
        isinstance(person, dict) and SOURCE_BUCKET in (person.get("cdn_image") or "")
        for person in people
    )


def main():
    if FILTER_OCDID:
        folder = jurisdiction_ocdid_to_folder(FILTER_OCDID)
        all_files = [str(ROOT / "data" / f"{folder}.yml")]
    else:
        all_files = sorted(glob.glob(DATA_PATTERN, recursive=True))

    candidates = []
    for path in all_files:
        if not Path(path).exists():
            print(f"File not found: {path}")
            continue
        with open(path) as f:
            people = yaml_io.load(f)
        if people and needs_migration(people):
            candidates.append((path, people))

    print(f"Found {len(candidates)} files with {SOURCE_BUCKET} cdn_image URLs")

    if DRY_RUN:
        for path, _ in candidates:
            print(f"  [dry-run] {path}")
        return

    updated_count = 0
    for path, people in candidates:
        images_updated = update_images(people)
        if images_updated:
            with open(path, "w") as f:
                yaml_io.dump(people, f)
            print(f"Updated: {path}")
            updated_count += 1
        else:
            print(f"Skipped (copy failed): {path}")

    print(f"\nDone. {updated_count}/{len(candidates)} files updated.")


if __name__ == "__main__":
    main()
