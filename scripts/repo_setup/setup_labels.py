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

LABELS = (
    [f"state:{code}" for code in STATE_CODES]
    + ["env:production", "env:development"]
)


def create_label(name: str, repo_flag: list[str]) -> None:
    result = subprocess.run(
        ["gh", "label", "create", name] + repo_flag,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"  created  {name}")
    elif "already exists" in result.stderr:
        print(f"  exists   {name}")
    else:
        print(f"  ERROR    {name}: {result.stderr.strip()}", file=sys.stderr)


if __name__ == "__main__":
    repo_flag = ["--repo", sys.argv[1]] if len(sys.argv) > 1 else []
    for label in LABELS:
        create_label(label, repo_flag)
