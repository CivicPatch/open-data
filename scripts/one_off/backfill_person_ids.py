#!/usr/bin/env python3
"""
Backfill missing `id` fields for person entries in YAML files by adding a UUID4 string.

Usage:
  python3 scripts/backfill_person_ids.py [path]
"""
from pathlib import Path
import sys
import uuid
import yaml

def add_ids_to_list(lst):
    changed = 0
    for item in lst:
        if isinstance(item, dict) and "id" not in item:
            item["id"] = str(uuid.uuid4())
            changed += 1
    return changed

def process_file(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        return 0
    changed = 0
    if isinstance(data, list):
        changed += add_ids_to_list(data)
    if changed:
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
    return changed

def find_files(start: Path):
    if start.is_file() and start.suffix in (".yml", ".yaml"):
        yield start
    elif start.is_dir():
        for p in start.rglob("*.yml"):
            yield p

def main(argv):
    root = Path(__file__).resolve().parents[2]  # open-data directory
    if len(argv) > 1:
        start = Path(argv[1])
    else:
        start = root / "data"
    total = 0
    files_changed = 0
    for f in find_files(start):
        # Only process files where "local" is in the path parts
        if "local" not in f.parts:
            continue
        try:
            c = process_file(f)
        except Exception as e:
            print(f"error processing {f}: {e}")
            continue
        if c:
            print(f"updated {f} (+{c})")
            total += c
            files_changed += 1
    print(f"done: {total} ids added in {files_changed} files")

if __name__ == "__main__":
    main(sys.argv)