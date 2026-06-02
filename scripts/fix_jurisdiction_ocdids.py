#!/usr/bin/env python3
"""
One-off: validate every jurisdiction OCD-ID and interactively fix the broken ones.

Run it AFTER (re)generating a state's jurisdictions.yml (see DEVELOPMENT.md). The
generator (`get_names` in setup_local.py) builds OCD-IDs by lowercasing the Census
name and swapping spaces for underscores — it does NOT restrict the result to the
legal OCD-ID character set, so names with apostrophes ("O'Brien"), diacritics
("Cañon City"), slashes ("Hartsville/Trousdale") or no LSAD suffix ("Lynchburg" ->
empty place) leak straight through into invalid IDs.

A legal jurisdiction OCD-ID looks like:
    ocd-jurisdiction/country:us/state:tx/place:odonnell/government
    ocd-jurisdiction/country:us/state:il/county:dupage/place:naperville/government
where every `label:value` segment's value matches [a-z0-9_.~-]+ and the trailing
segment is the jurisdiction type (no colon).

Usage:
    uv run python scripts/fix_jurisdiction_ocdids.py              # all states
    uv run python scripts/fix_jurisdiction_ocdids.py --state tn   # one state
    uv run python scripts/fix_jurisdiction_ocdids.py --dry-run    # report only, no prompts
    uv run python scripts/fix_jurisdiction_ocdids.py --yes        # auto-accept every proposal

For each invalid ID you get: [a]ccept proposal / [e]dit by hand / [s]kip / [q]uit.
Accepting rewrites the ID in jurisdictions.yml, renames/repoints the matching key in
jurisdictions_metadata.yml, and migrates any data/<state>/local/*.yml officials file
that references the old ID (file rename + jurisdiction_ocdid field).
"""

import argparse
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

# Structural validation is delegated to shared (the owner of OCD-ID grammar); we
# layer charset + empty checks on top because parse_jurisdiction_ocdid is a tolerant
# round-trip parser, not a validator — it happily parses place:o'brien and place:<empty>.
from shared.utils.id_utils import parse_jurisdiction_ocdid
# Read/write through the shared YAML manager so files stay in the canonical format
# the pipeline produces (don't hand-roll a ruamel config here).
from shared.utils.yaml_utils import yaml_load, yaml_dump

PROJECT_ROOT = Path(__file__).parent.parent


def _read_yaml(path: Path):
    with open(path) as f:
        return yaml_load(f.read())


def _write_yaml(path: Path, data) -> None:
    with open(path, "w") as f:
        f.write(yaml_dump(data))


# Legal characters for a single OCD-ID segment value (after the `label:`).
_SEGMENT_RE = re.compile(r"^[a-z0-9_.~-]+$")
# Labels that carry a place-like value (mirrors shared.utils.id_utils.KNOWN_PLACE_KEYS).
_PLACE_LABELS = {"place", "special_district"}
_OCD_PREFIX = "ocd-jurisdiction/"


def validate_jurisdiction_ocdid(ocdid: str) -> list[str]:
    """Return a list of human-readable problems with `ocdid`; empty list == valid.

    Liftable into shared.utils.id_utils as the strict counterpart to the tolerant
    parse_jurisdiction_ocdid (which this calls for the structural check).
    """
    problems: list[str] = []

    if not ocdid.startswith(_OCD_PREFIX):
        return [f"does not start with {_OCD_PREFIX!r}"]

    # Structural shape — delegate to shared. It raises on a stray slash that splits
    # a segment ("place:hartsville/trousdale/government") or other malformed shapes.
    try:
        _ = parse_jurisdiction_ocdid(ocdid)
    except ValueError as e:
        problems.append(f"bad structure ({e})")

    # Charset + emptiness per labeled segment (the part shared does not check).
    for label, value in _labeled_segments(ocdid):
        if value == "":
            problems.append(f"{label} component is empty")
        elif not _SEGMENT_RE.match(value):
            bad = "".join(sorted({c for c in value if not _SEGMENT_RE.match(c)}))
            problems.append(f"{label}={value!r} has illegal char(s): {bad!r}")

    return problems


def _labeled_segments(ocdid: str) -> list[list[str]]:
    """[[label, value], ...] for the labeled segments (drops the trailing type).

    A colon-less segment is treated as a slash that leaked into the previous
    value (e.g. ".../place:hartsville/trousdale/government") and is folded back in.
    """
    body = ocdid[len(_OCD_PREFIX):] if ocdid.startswith(_OCD_PREFIX) else ocdid
    segs = body.split("/")
    labeled = segs[:-1]  # last segment is the jurisdiction type
    out: list[list[str]] = []
    for seg in labeled:
        if ":" in seg:
            label, value = seg.split(":", 1)
            out.append([label, value])
        elif out:
            out[-1][1] += "/" + seg  # continuation of a slashed value
    return out


def _slugify(text: str) -> str:
    """Canonical OCD-ID segment value: ascii-fold, lowercase, drop apostrophes,
    map any other illegal run to a single underscore."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"['’`]", "", text)          # O'Brien -> obrien
    text = re.sub(r"[^a-z0-9_.~-]+", "_", text)       # slashes, spaces, parens -> _
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def propose_fix(ocdid: str, name: str | None) -> str:
    """Build a canonical OCD-ID. Empty place-like values are reconstructed from `name`."""
    type_ = ocdid.rsplit("/", 1)[-1]
    rebuilt = []
    for label, value in _labeled_segments(ocdid):
        if value == "" and label in _PLACE_LABELS and name:
            value = name
        rebuilt.append(f"{label}:{_slugify(value)}")
    return _OCD_PREFIX + "/".join(rebuilt) + "/" + type_


# ---------------------------------------------------------------------------
# Applying a fix across the three places an OCD-ID can live
# ---------------------------------------------------------------------------

def _apply_to_jurisdictions(path: Path, old: str, new: str) -> bool:
    doc = _read_yaml(path)
    changed = False
    for entry in (doc or {}).get("jurisdictions", []) or []:
        if entry.get("id") == old:
            entry["id"] = new
            changed = True
    if changed:
        _write_yaml(path, doc)
    return changed


def _apply_to_metadata(state: str, old: str, new: str) -> bool:
    path = PROJECT_ROOT / "data_source" / state / "local" / "jurisdictions_metadata.yml"
    if not path.exists():
        return False
    doc = _read_yaml(path)
    by_id = (doc or {}).get("jurisdictions_by_id")
    if not by_id or old not in by_id:
        return False
    entry = by_id.pop(old)
    if isinstance(entry, dict) and entry.get("jurisdiction_ocdid") == old:
        entry["jurisdiction_ocdid"] = new
    by_id[new] = entry
    _write_yaml(path, doc)
    return True


def _apply_to_data_file(state: str, old: str, new: str) -> bool:
    """Migrate the officials file if one references the old ID (rename + repoint)."""
    from scripts.utils import jurisdiction_to_file

    try:
        old_path = PROJECT_ROOT / jurisdiction_to_file(old)
    except ValueError:
        old_path = None  # e.g. the empty-place ID can't resolve to a file
    try:
        new_path = PROJECT_ROOT / jurisdiction_to_file(new)
    except ValueError:
        return False

    if not old_path or not old_path.exists():
        return False

    records = _read_yaml(old_path)
    for rec in records or []:
        if rec.get("jurisdiction_ocdid") == old:
            rec["jurisdiction_ocdid"] = new
    _write_yaml(old_path, records)
    if new_path != old_path:
        new_path.parent.mkdir(parents=True, exist_ok=True)
        old_path.rename(new_path)
    return True


def apply_fix(state: str, jurisdictions_path: Path, old: str, new: str) -> None:
    touched = []
    if _apply_to_jurisdictions(jurisdictions_path, old, new):
        touched.append(jurisdictions_path.relative_to(PROJECT_ROOT).as_posix())
    if _apply_to_metadata(state, old, new):
        touched.append(f"data_source/{state}/local/jurisdictions_metadata.yml")
    if _apply_to_data_file(state, old, new):
        touched.append(f"data/{state}/local/* (officials file migrated)")
    print(f"    ✓ updated: {', '.join(touched) if touched else '(no files matched)'}")


# ---------------------------------------------------------------------------
# Discovery + driver
# ---------------------------------------------------------------------------

def _jurisdiction_files(state: str | None) -> list[tuple[str, Path]]:
    states = [state] if state else sorted(
        p.name for p in (PROJECT_ROOT / "data_source").iterdir() if p.is_dir()
    )
    files: list[tuple[str, Path]] = []
    for st in states:
        for sub in ("local", "counties", "state"):
            path = PROJECT_ROOT / "data_source" / st / sub / "jurisdictions.yml"
            if path.exists():
                files.append((st, path))
    return files


def _id_line(entry) -> int | None:
    """1-based source line of the entry's `id:` key, via ruamel's line/col data."""
    try:
        return entry.lc.data["id"][0] + 1
    except (AttributeError, KeyError, TypeError):
        try:
            return entry.lc.line + 1
        except (AttributeError, TypeError):
            return None


def _all_ocdids(state: str | None) -> set[str]:
    """Every OCD-ID currently present across the in-scope jurisdiction files."""
    ids: set[str] = set()
    for _st, path in _jurisdiction_files(state):
        doc = _read_yaml(path)
        for entry in (doc or {}).get("jurisdictions", []) or []:
            oid = entry.get("id")
            if oid:
                ids.add(oid)
    return ids


def _find_problems(state: str | None):
    """Yield (state, path, line, entry_id, name, problems) for every invalid OCD-ID."""
    for st, path in _jurisdiction_files(state):
        doc = _read_yaml(path)
        for entry in (doc or {}).get("jurisdictions", []) or []:
            oid = entry.get("id", "")
            problems = validate_jurisdiction_ocdid(oid)
            if problems:
                yield st, path, _id_line(entry), oid, entry.get("name"), problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--state", help="Limit to one state code (default: all states)")
    parser.add_argument("--dry-run", action="store_true", help="Report problems only; make no changes")
    parser.add_argument("--yes", action="store_true", help="Auto-accept every proposed fix (non-interactive)")
    args = parser.parse_args()

    found = list(_find_problems(args.state))
    scope = f"state '{args.state}'" if args.state else "all states"
    if not found:
        print(f"✅ No invalid jurisdiction OCD-IDs found in {scope}.")
        return 0

    print(f"Found {len(found)} invalid jurisdiction OCD-ID(s) in {scope}.\n")

    # Pre-compute proposals so we can flag collisions: a suggested ID that already
    # exists, or two different bad IDs that slugify to the same suggestion.
    existing_ids = _all_ocdids(args.state)
    proposals = [propose_fix(old, name) for (_st, _p, _ln, old, name, _pr) in found]
    proposal_counts = Counter(proposals)

    fixed = skipped = 0

    for i, (st, path, line, old, name, problems) in enumerate(found, 1):
        proposed = proposals[i - 1]
        loc = f"{path.relative_to(PROJECT_ROOT).as_posix()}:{line}" if line else path.relative_to(PROJECT_ROOT).as_posix()

        collisions = []
        if proposed in existing_ids and proposed != old:
            collisions.append("an existing jurisdiction already uses this ID")
        if proposal_counts[proposed] > 1:
            collisions.append("another suggested fix maps to the same ID")

        print(f"[{i}/{len(found)}] state={st}  {loc}  (name: {name!r})")
        print(f"    current:   {old}")
        for p in problems:
            print(f"      ! {p}")
        print(f"    suggested: {proposed}")
        for c in collisions:
            print(f"    ⚠ COLLISION: {c} — needs a manual unique ID")

        if args.dry_run:
            print()
            continue

        if collisions and args.yes:
            print("    skipped (collision; rerun without --yes to resolve by hand)\n")
            skipped += 1
            continue

        new = proposed
        if not args.yes:
            choice = input("    [a]ccept / [e]dit / [s]kip / [q]uit > ").strip().lower()
            if choice in ("q", "quit"):
                print("Aborted.")
                break
            if choice in ("s", "skip", ""):
                skipped += 1
                print()
                continue
            if choice in ("e", "edit"):
                while True:
                    new = input("    new OCD-ID > ").strip()
                    errs = validate_jurisdiction_ocdid(new)
                    if not errs:
                        break
                    print(f"      still invalid: {'; '.join(errs)}")

        apply_fix(st, path, old, new)
        existing_ids.discard(old)
        existing_ids.add(new)
        fixed += 1
        print()

    if args.dry_run:
        print(f"Dry run: {len(found)} problem(s) reported, nothing changed.")
    else:
        print(f"Done. Fixed {fixed}, skipped {skipped}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
