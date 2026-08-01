"""One-time script to create all expected GitHub labels for this repo.

Usage:
    GH_TOKEN=<token> uv run python scripts/repo_setup/setup_labels.py [--repo owner/repo]
"""

import subprocess
import sys

STATE_CODES = [
    "al", "ak", "az", "ar", "ca", "co", "ct", "dc", "de", "fl",
    "ga", "hi", "id", "il", "in", "ia", "ks", "ky", "la", "me",
    "md", "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh",
    "nj", "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri",
    "sc", "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy",
]

EDIT_SOURCE_LABELS = {
    "civicpatch:admin": "Manual edits by an admin user from civicpatch.org.",
    "civicpatch:contributor": "Manual edits by a verified user from civicpatch.org.",
    "civicpatch:maintainer": "Manual edits by a state maintainer from civicpatch.org.",
    "civicpatch:system": "Automated edits by civicpatch.",
    "civicpatch:unverified": (
        "Manual edits by an unverified user from civicpatch.org. Please review."
    ),
}

# name -> description ("" when the label has no description)
LABELS: dict[str, str] = {
    **{name: "" for name in ["env:development", "data-quality", "user-reported"]},
    **{f"state:{code}": "" for code in STATE_CODES},
    **EDIT_SOURCE_LABELS,
}


def create_label(name: str, description: str, repo_flag: list[str]) -> None:
    desc_flag = ["--description", description] if description else []
    result = subprocess.run(
        ["gh", "label", "create", name] + desc_flag + repo_flag,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"  created  {name}")
        return
    if "already exists" not in result.stderr:
        print(f"  ERROR    {name}: {result.stderr.strip()}", file=sys.stderr)
        return
    if not description:
        print(f"  exists   {name}")
        return
    # Keep the description in sync on labels that already exist.
    result = subprocess.run(
        ["gh", "label", "edit", name] + desc_flag + repo_flag,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"  updated  {name}")
    else:
        print(f"  ERROR    {name}: {result.stderr.strip()}", file=sys.stderr)


if __name__ == "__main__":
    repo_flag = ["--repo", sys.argv[1]] if len(sys.argv) > 1 else []
    for label, description in LABELS.items():
        create_label(label, description, repo_flag)
