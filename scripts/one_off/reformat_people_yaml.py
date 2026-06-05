"""
One-time bulk reformat of people files onto the shared YAML manager's style.

Runs every data/**/*.yml through shared `yaml_load` -> `yaml_dump`, which keeps long
scalars on one line (no PyYAML width-80 folding) and renders nulls as explicit `null`.
This is the format-only commit that lets manual people-edits produce clean diffs — only
the edited fields move, instead of also unwrapping folded lines on first touch.

With the `null` representer in `shared` this is unwrap-only (~1135 files; nulls don't
change). Run `uv lock --upgrade-package shared && uv sync` FIRST so `shared` has the
representer — otherwise nulls would flip to blank.

Self-verifying: a file is rewritten only if the reparsed data is semantically identical
to the original, so it can never corrupt data. Idempotent: a second run is a no-op.

Usage:
    uv run python scripts/one_off/reformat_people_yaml.py            # dry run
    uv run python scripts/one_off/reformat_people_yaml.py --apply    # write changes
"""

import sys
from pathlib import Path

from shared.utils.yaml_utils import yaml_dump, yaml_load


def main(apply: bool) -> None:
    files = sorted(Path("data").rglob("*.yml"))
    changed, unsafe = [], []
    for path in files:
        original = path.read_text(encoding="utf-8")
        reformatted = yaml_dump(yaml_load(original))
        if reformatted == original:
            continue
        if yaml_load(reformatted) != yaml_load(original):  # data would change — never write
            unsafe.append(path)
            continue
        changed.append(path)
        if apply:
            path.write_text(reformatted, encoding="utf-8")

    print(f"Scanned {len(files)} files")
    print(f"{'Reformatted' if apply else 'Would reformat'}: {len(changed)}")
    if unsafe:
        print(f"SKIPPED — reparse differs, investigate: {len(unsafe)}")
        for p in unsafe[:20]:
            print(f"  {p}")
    if not apply:
        print("\nDry run — rerun with --apply to write.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
