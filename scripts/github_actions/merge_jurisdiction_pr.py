#!/usr/bin/env python3
"""Merge a jurisdiction-edit PR from civicpatch.org once it passes the gate. Runs from the base
branch: nothing here reads the PR's code. civicpatch.org's hourly sync reads the merge itself.

Self-contained on purpose: it moves to the jurisdictions repo with its workflow.

The gate, all required:
1. the PR is open, into main, and not a draft
2. its most recent edit-source label was added by an app the CivicPatch org owns, dev's or
   prod's (anyone with triage can add a label, so the label alone proves nothing)
3. every changed file is a jurisdictions.yml
4. the validation check passed on the PR's current head

The PRs come from a fork, and a workflow_run for a fork's PR does not name it, so the PR is
found from the fork's owner and branch when no number is given.
"""

import os
import re
import sys

import requests

API = "https://api.github.com"
APP_OWNER = "CivicPatch"
MERGE_LABELS = {"civicpatch:maintainer", "civicpatch:admin", "civicpatch:system"}
JURISDICTIONS_PATH = re.compile(r"^data_source/[a-z]{2}/(state|counties|local)/jurisdictions\.yml$")
VALIDATION_CHECK = "ocdid-tests"
MAX_FILES = 100


def labelled_by_app(events: list[dict], labels_on_pr: set[str]) -> bool:
    last_app_owner_by_label: dict[str, str | None] = {}
    for event in events:
        if event.get("event") == "labeled":
            app = event.get("performed_via_github_app") or {}
            last_app_owner_by_label[event["label"]["name"]] = (app.get("owner") or {}).get("login")
    return any(
        label in labels_on_pr and last_app_owner_by_label.get(label) == APP_OWNER
        for label in MERGE_LABELS
    )


def only_jurisdiction_files(paths: list[str]) -> bool:
    return bool(paths) and all(JURISDICTIONS_PATH.match(path) for path in paths)


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
        return f"no edit-source label added by an app {APP_OWNER} owns"
    if len(paths) >= MAX_FILES or not only_jurisdiction_files(paths):
        return "changes files other than jurisdictions.yml"
    if not validation_passed(check_runs):
        return f"{VALIDATION_CHECK} has not passed on the head commit"
    return None


def _get(session: requests.Session, url: str, params: dict | None = None):
    response = session.get(url, params={"per_page": MAX_FILES, **(params or {})})
    response.raise_for_status()
    return response.json()


def _github_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "X-GitHub-Api-Version": "2022-11-28"}
    )
    return session


def _find_number(session: requests.Session, base: str, head_owner: str, head_branch: str) -> str:
    if not head_owner or not head_branch:
        return ""
    open_pull_requests = _get(session, f"{base}/pulls", {"head": f"{head_owner}:{head_branch}", "state": "open"})
    return str(open_pull_requests[0]["number"]) if open_pull_requests else ""


def _merge(session: requests.Session, base: str, number: str, head_sha: str) -> str:
    response = session.put(f"{base}/pulls/{number}/merge", json={"sha": head_sha, "merge_method": "squash"})
    response.raise_for_status()
    return response.json()["sha"]


def main() -> int:
    session = _github_session()
    base = f"{API}/repos/{os.environ['REPOSITORY']}"
    number = os.environ.get("PULL_REQUEST_NUMBER") or _find_number(
        session, base, os.environ.get("HEAD_OWNER", ""), os.environ.get("HEAD_BRANCH", "")
    )
    if not number:
        print("No open pull request for this run; nothing to merge.")
        return 0

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
    return 0


if __name__ == "__main__":
    sys.exit(main())
