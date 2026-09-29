#!/usr/bin/env python3
"""Merge a config PR from civicpatch.org once it passes open-data's gate, then tell
civicpatch.org which files changed. Runs from the base branch: nothing here reads the PR's code.

The gate, all required:
1. the PR is open, into main, and not a draft
2. its most recent maintainer label was added by civicpatch.org's app (anyone with triage can
   add a label, so the label alone proves nothing)
3. every changed file is a config file
4. the validation check passed on the PR's current head

A PR that fails any of them stays open for a person. Merging with the head sha means a push after
the checks ran makes the merge fail instead of merging unchecked content.
"""

import os
import re
import sys

import requests

API = "https://api.github.com"
APP_BOT = "civicpatch[bot]"
MAINTAINER_LABELS = {"civicpatch:maintainer", "civicpatch:admin"}
CONFIG_PATH = re.compile(r"^data_source/(([a-z]{2}/)?(local|counties)/)?config\.yml$")
VALIDATION_CHECK = "config-tests"
MAX_FILES = 100


def labelled_by_app(events: list[dict], labels_on_pr: set[str]) -> bool:
    last_actor_by_label: dict[str, str] = {}
    for event in events:
        if event.get("event") == "labeled":
            last_actor_by_label[event["label"]["name"]] = event["actor"]["login"]
    return any(
        label in labels_on_pr and last_actor_by_label.get(label) == APP_BOT
        for label in MAINTAINER_LABELS
    )


def only_config_files(paths: list[str]) -> bool:
    return bool(paths) and all(CONFIG_PATH.match(path) for path in paths)


def validation_passed(check_runs: list[dict]) -> bool:
    runs = [run for run in check_runs if run["name"] == VALIDATION_CHECK]
    if not runs:
        return False
    latest = max(runs, key=lambda run: run["started_at"])
    return latest["status"] == "completed" and latest["conclusion"] == "success"


def refusal(pull_request: dict, events: list[dict], paths: list[str], check_runs: list[dict]) -> str | None:
    """Why this PR must not merge, or None when it may."""
    if pull_request["state"] != "open" or pull_request["draft"] or pull_request["base"]["ref"] != "main":
        return "not an open, ready PR into main"
    labels = {label["name"] for label in pull_request["labels"]}
    if not labelled_by_app(events, labels):
        return f"no maintainer label added by {APP_BOT}"
    if len(paths) >= MAX_FILES or not only_config_files(paths):
        return "changes files other than config files"
    if not validation_passed(check_runs):
        return f"{VALIDATION_CHECK} has not passed on the head commit"
    return None


def _get(session: requests.Session, url: str):
    response = session.get(url, params={"per_page": MAX_FILES})
    response.raise_for_status()
    return response.json()


def _github_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "X-GitHub-Api-Version": "2022-11-28"}
    )
    return session


def _merge(session: requests.Session, base: str, number: str, head_sha: str) -> str:
    response = session.put(f"{base}/pulls/{number}/merge", json={"sha": head_sha, "merge_method": "squash"})
    response.raise_for_status()
    return response.json()["sha"]


def _sync_civicpatch(commit_sha: str, number: str, paths: list[str]) -> None:
    response = requests.post(
        f"{os.environ['CIVICPATCH_ORG_URL']}/api/admin/jurisdiction_configs/sync",
        headers={"Authorization": os.environ["SERVICE_API_KEY"]},
        json={"commit_sha": commit_sha, "pull_request_number": int(number), "paths": paths},
        timeout=60,
    )
    response.raise_for_status()


def main() -> int:
    number = os.environ.get("PULL_REQUEST_NUMBER", "")
    if not number:
        print("No pull request for this run; nothing to merge.")
        return 0

    session = _github_session()
    base = f"{API}/repos/{os.environ['REPOSITORY']}"
    pull_request: dict = _get(session, f"{base}/pulls/{number}")
    head_sha: str = pull_request["head"]["sha"]
    events: list[dict] = _get(session, f"{base}/issues/{number}/events")
    paths = [file["filename"] for file in _get(session, f"{base}/pulls/{number}/files")]
    check_runs: list[dict] = _get(session, f"{base}/commits/{head_sha}/check-runs")["check_runs"]

    reason = refusal(pull_request, events, paths, check_runs)
    if reason:
        print(f"PR #{number} stays open: {reason}.")
        return 0

    commit_sha = _merge(session, base, number, head_sha)
    print(f"Merged PR #{number} as {commit_sha}.")
    _sync_civicpatch(commit_sha, number, paths)
    print(f"civicpatch.org synced {len(paths)} config file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
