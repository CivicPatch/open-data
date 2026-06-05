"""
Quote unquoted numeric geoids in jurisdiction files so they're parser-independent strings.

A geoid is a FIPS identifier (e.g. 0820000 for Denver) — leading zeros are significant.
Unquoted, YAML 1.2 (ruamel) parses `0820000` as the int 820000, losing the zero, while
YAML 1.1 (PyYAML) keeps it a string. Quoting makes every parser agree it's a string, and
matches the single-quote style the already-quoted geoids use.

Surgical line transform: only rewrites `geoid: <bare digits>` -> `geoid: '<digits>'`.
Already-quoted geoids and null/empty geoids are left untouched. Idempotent.

Usage:
    uv run python scripts/one_off/quote_geoids.py            # dry run
    uv run python scripts/one_off/quote_geoids.py --apply    # write changes
"""

import re
import sys
from pathlib import Path

GEOID_LINE = re.compile(r"(?m)^([ \t]*geoid:[ \t]+)(\d+)[ \t]*$")


def main(apply: bool) -> None:
    files = sorted(Path("data_source").rglob("jurisdictions.yml"))
    total = 0
    touched = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        new_text, count = GEOID_LINE.subn(r"\1'\2'", text)
        if count:
            total += count
            touched.append((path, count))
            if apply:
                path.write_text(new_text, encoding="utf-8")

    print(f"Scanned {len(files)} jurisdiction files")
    print(f"{'Quoted' if apply else 'Would quote'}: {total} geoids in {len(touched)} file(s)")
    for path, count in touched:
        print(f"  {count:5d}  {path}")
    if not apply:
        print("\nDry run — rerun with --apply to write.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
