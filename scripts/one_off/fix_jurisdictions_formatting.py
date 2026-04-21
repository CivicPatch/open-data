"""
Fix reformatted jurisdictions.yml in old data-intake PRs.

For each open PR branch matching job/*, resets data_source/{state}/jurisdictions.yml
to main's version, then re-applies only the real URL change (if any) using the
pipeline_run_context.json already committed to the branch.

Only touches jurisdictions.yml — all other files in each PR are left untouched.

Usage:
    uv run python scripts/one_off/fix_jurisdictions_formatting.py              # dry run
    uv run python scripts/one_off/fix_jurisdictions_formatting.py --apply     # make changes
    uv run python scripts/one_off/fix_jurisdictions_formatting.py --apply --limit 5
"""

import asyncio
import base64
import json
import subprocess
import sys
from dataclasses import dataclass
from io import StringIO

import requests
from ruamel.yaml import YAML

REPO = "CivicPatch/open-data"
MAIN_BRANCH = "main"
API_BASE = "https://api.github.com"
MAX_CONCURRENT = 10


def yaml_instance() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096
    return y


@dataclass
class PrInfo:
    number: int
    branch: str
    state: str
    folder: str

    @property
    def context_api_path(self) -> str:
        return f"data_source/{self.folder}/pipeline_run_context.json"

    @property
    def jurisdictions_api_path(self) -> str:
        return f"data_source/{self.state}/jurisdictions.yml"


def parse_branch(branch: str) -> tuple[str, str]:
    remainder = branch.removeprefix("job/")
    parts = remainder.split("/")
    state = parts[0]
    folder = "/".join(parts[:-1])
    return state, folder


def get_token() -> str:
    return subprocess.check_output(["gh", "auth", "token"]).decode().strip()


def make_session(token: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    return s


def list_prs_sync(session: requests.Session) -> list[PrInfo]:
    prs = []
    page = 1
    while True:
        r = session.get(
            f"{API_BASE}/repos/{REPO}/pulls",
            params={"state": "open", "per_page": 100, "page": page},
        )
        r.raise_for_status()
        items = r.json()
        if not items:
            break
        for item in items:
            branch = item["head"]["ref"]
            if not branch.startswith("job/"):
                continue
            state, folder = parse_branch(branch)
            prs.append(PrInfo(number=item["number"], branch=branch, state=state, folder=folder))
        page += 1
    return prs


def get_file_sync(session: requests.Session, path: str, ref: str) -> tuple[str, str] | None:
    """Returns (decoded_content, blob_sha) or None if not found."""
    r = session.get(
        f"{API_BASE}/repos/{REPO}/contents/{path}",
        params={"ref": ref},
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    data = r.json()
    content = base64.b64decode(data["content"]).decode("utf-8")
    return content, data["sha"]


def put_file_sync(session: requests.Session, path: str, content: str, sha: str, branch: str, message: str) -> None:
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    r = session.put(
        f"{API_BASE}/repos/{REPO}/contents/{path}",
        json={"message": message, "content": encoded, "sha": sha, "branch": branch},
    )
    r.raise_for_status()


def compute_new_content(branch_content: str, ocdid: str, resolved_url: str) -> tuple[str, str | None, str | None]:
    """
    Loads the branch's jurisdictions.yml, re-dumps it with width=4096 (fixing
    line-wrapping), and updates only the one URL entry for this PR's ocdid.
    Returns (new_yaml_str, old_url, new_url). old/new_url are None if URL unchanged.
    """
    y = yaml_instance()
    data = y.load(branch_content)
    old_url = None
    for entry in data.get("jurisdictions", []):
        if entry.get("id") != ocdid:
            continue
        old_url = entry.get("url")
        if old_url != resolved_url:
            entry["url"] = resolved_url
        break
    stream = StringIO()
    y.dump(data, stream)
    new_content = stream.getvalue()
    if old_url != resolved_url:
        return new_content, old_url, resolved_url
    return new_content, None, None


async def process_pr(
    semaphore: asyncio.Semaphore,
    session: requests.Session,
    pr: PrInfo,
    apply: bool,
) -> str:
    async with semaphore:
        try:
            # Get pipeline_run_context.json from the branch
            ctx_result = await asyncio.to_thread(get_file_sync, session, pr.context_api_path, pr.branch)
            if ctx_result is None:
                return f"PR #{pr.number}  ERROR: context not found at {pr.context_api_path}"
            ctx = json.loads(ctx_result[0])
            ocdid = ctx["data"]["jurisdiction_ocdid"]
            resolved_url = ctx["data"]["config"]["url"]

            # Get branch's jurisdictions.yml — used as base and for its SHA
            branch_result = await asyncio.to_thread(get_file_sync, session, pr.jurisdictions_api_path, pr.branch)
            if branch_result is None:
                return f"PR #{pr.number}  ERROR: jurisdictions.yml not found on branch"
            branch_content, branch_sha = branch_result

            # Re-dump branch content with width=4096 (fixes wrapping), update one URL
            new_content, old_url, new_url = compute_new_content(branch_content, ocdid, resolved_url)
            url_summary = f"{old_url} → {new_url}" if old_url else "formatting only"

            if new_content == branch_content:
                return f"PR #{pr.number}  already clean — skipped"

            if not apply:
                return f"PR #{pr.number}  would update  ({url_summary})"

            await asyncio.to_thread(
                put_file_sync, session, pr.jurisdictions_api_path, new_content,
                branch_sha, pr.branch, "Fix jurisdictions.yml formatting (preserve line width)",
            )
            return f"PR #{pr.number}  done  ({url_summary})"

        except Exception as e:
            return f"PR #{pr.number}  ERROR: {e}"


async def main(apply: bool, limit: int | None) -> None:
    print(f"=== fix_jurisdictions_formatting ({'APPLY' if apply else 'DRY RUN'}) ===\n")

    token = get_token()
    session = make_session(token)

    prs = await asyncio.to_thread(list_prs_sync, session)
    if limit:
        prs = prs[:limit]
    print(f"Found {len(prs)} matching PRs\n")

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    results = await asyncio.gather(*[
        process_pr(semaphore, session, pr, apply) for pr in prs
    ])

    for r in sorted(results):
        print(r)

    errors = [r for r in results if "ERROR" in r]
    skipped = [r for r in results if "skipped" in r]
    print(f"\n=== Summary ===")
    print(f"Total:   {len(prs)}")
    if apply:
        print(f"Done:    {len(prs) - len(errors) - len(skipped)}")
        print(f"Skipped: {len(skipped)}")
        print(f"Errors:  {len(errors)}")
    else:
        print(f"\nRun with --apply to make changes.")


if __name__ == "__main__":
    apply = "--apply" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    asyncio.run(main(apply, limit))
