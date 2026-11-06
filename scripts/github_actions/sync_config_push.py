#!/usr/bin/env python3
"""Tell civicpatch.org which config files a push to main changed, for merges the labelled-PR
workflow did not make (a person's PR, a direct commit). civicpatch.org orders level files first."""

import os
import subprocess
import sys

from scripts.github_actions.merge_config_pr import CONFIG_PATH, sync_civicpatch


def changed_config_paths(names: list[str]) -> list[str]:
    return [name for name in names if CONFIG_PATH.match(name)]


def _changed_files(before_sha: str, after_sha: str) -> list[str]:
    # Deleted files are left out: civicpatch.org reads each path at the commit.
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=d", before_sha, after_sha],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.splitlines()


def main() -> int:
    after_sha = os.environ["AFTER_SHA"]
    paths = changed_config_paths(_changed_files(os.environ["BEFORE_SHA"], after_sha))
    if not paths:
        print("No config files changed; nothing to sync.")
        return 0

    sync_civicpatch(after_sha, None, paths)
    print(f"civicpatch.org synced {len(paths)} config file(s) at {after_sha}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
