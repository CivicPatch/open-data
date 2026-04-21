"""
Fix reformatted jurisdictions.yml in old data-intake PRs.

For each PR branch matching job/*, resets data_source/{state}/jurisdictions.yml
to main, then re-runs update_jurisdiction_url.py (with the best_width fix) so
only the real URL change (if any) is kept.

Usage:
    uv run python scripts/one_off/fix_jurisdictions_formatting.py              # dry run
    uv run python scripts/one_off/fix_jurisdictions_formatting.py --apply     # make changes
    uv run python scripts/one_off/fix_jurisdictions_formatting.py --apply --limit 3  # test on 3
"""

import asyncio
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
MAIN_BRANCH = "main"
REPO = "CivicPatch/open-data"
MAX_PARALLEL = 8       # concurrent git fetch/push operations
MAX_GH_API = 3        # concurrent GitHub API calls (rate limit: 5000 req/hr authenticated)


@dataclass
class PrInfo:
    number: str
    branch: str
    state: str
    folder: str

    @property
    def context_path(self) -> str:
        return f"data_source/{self.folder}/pipeline_run_context.json"

    @property
    def jurisdictions_path(self) -> str:
        return f"data_source/{self.state}/jurisdictions.yml"


async def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> str:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd or REPO_ROOT,
    )
    stdout, stderr = await proc.communicate()
    if check and proc.returncode != 0:
        raise RuntimeError(f"{cmd[0]} {cmd[1]} failed: {stderr.decode().strip()}")
    return stdout.decode().strip()


async def fetch_branch(branch: str, gh_semaphore: asyncio.Semaphore) -> None:
    async with gh_semaphore:
        await run(
            ["git", "fetch", "origin", f"{branch}:refs/remotes/origin/{branch}"],
            check=False,
        )


def parse_branch(branch: str) -> tuple[str, str]:
    """Returns (state, folder) from a job/* branch name."""
    remainder = branch.removeprefix("job/")
    parts = remainder.split("/")
    state = parts[0]
    folder = "/".join(parts[:-1])  # strip trailing request_id
    return state, folder


async def list_prs() -> list[PrInfo]:
    prs = []
    page = 1
    while True:
        raw = await run([
            "gh", "api",
            f"repos/{REPO}/pulls",
            "--method", "GET",
            "-f", "state=open",
            "-f", "per_page=100",
            "-f", f"page={page}",
            "--jq", '.[] | select(.head.ref | startswith("job/")) | [(.number | tostring), .head.ref] | join(" ")',
        ])
        lines = [l for l in raw.splitlines() if l.strip()]
        if not lines:
            break
        for line in lines:
            number, branch = line.split(" ", 1)
            state, folder = parse_branch(branch)
            prs.append(PrInfo(number=number, branch=branch, state=state, folder=folder))
        page += 1
    return prs


async def dry_run_pr(semaphore: asyncio.Semaphore, gh_semaphore: asyncio.Semaphore, pr: PrInfo) -> bool:
    async with semaphore:
        await fetch_branch(pr.branch, gh_semaphore)
        diff = await run(
            ["git", "diff", f"origin/{MAIN_BRANCH}...origin/{pr.branch}", "--", pr.jurisdictions_path],
            check=False,
        )
        diff_lines = len(diff.splitlines())
        changed = diff_lines > 0
        status = f"CHANGED ({diff_lines} lines) — would rewrite" if changed else "unchanged — would skip"
        print(f"PR #{pr.number:>5}  {pr.branch}\n             jurisdictions.yml: {status}")
        return changed


async def apply_pr(semaphore: asyncio.Semaphore, gh_semaphore: asyncio.Semaphore, pr: PrInfo, worktree_base: Path) -> str:
    worktree = worktree_base / f"pr-{pr.number}"
    async with semaphore:
        try:
            await fetch_branch(pr.branch, gh_semaphore)
            await run(["git", "worktree", "add", str(worktree), f"origin/{pr.branch}"])

            # Reset jurisdictions.yml to main
            await run(
                ["git", "checkout", f"origin/{MAIN_BRANCH}", "--", pr.jurisdictions_path],
                cwd=worktree,
            )

            # Re-run update_jurisdiction_url.py with the fix in place
            context_file = worktree / pr.context_path
            if context_file.exists():
                data = json.loads(context_file.read_text())
                ocdid = data["data"]["jurisdiction_ocdid"]
                await run(
                    ["uv", "run", "python", "scripts/github_actions/update_jurisdiction_url.py",
                     ocdid, pr.context_path],
                    cwd=worktree,
                    check=False,
                )
            else:
                print(f"PR #{pr.number}  WARNING: context not found at {pr.context_path}")

            await run(["git", "add", pr.jurisdictions_path], cwd=worktree)
            diff = await run(
                ["git", "diff", "--cached", "--", pr.jurisdictions_path],
                cwd=worktree, check=False,
            )
            url_lines = [l for l in diff.splitlines() if l.startswith(("+url:", "-url:")) and "url:" in l]
            url_summary = "  ".join(url_lines) if url_lines else "no URL change"
            await run(["git", "commit", "--amend", "--no-edit"], cwd=worktree)
            async with gh_semaphore:
                await run(["git", "push", "--force-with-lease", "origin", f"HEAD:{pr.branch}"], cwd=worktree)
            return f"PR #{pr.number}  done  ({url_summary})"
        except Exception as e:
            return f"PR #{pr.number}  ERROR: {e}"
        finally:
            await run(["git", "worktree", "remove", str(worktree), "--force"], check=False)


async def main(apply: bool, limit: int | None) -> None:
    print(f"=== fix_jurisdictions_formatting ({'APPLY' if apply else 'DRY RUN'}) ===\n")

    await run(["git", "fetch", "origin", MAIN_BRANCH, "--quiet"])

    prs = await list_prs()
    if limit:
        prs = prs[:limit]
    print(f"Found {len(prs)} matching PRs\n")

    semaphore = asyncio.Semaphore(MAX_PARALLEL)
    gh_semaphore = asyncio.Semaphore(MAX_GH_API)

    if not apply:
        results = await asyncio.gather(*[dry_run_pr(semaphore, gh_semaphore, pr) for pr in prs])
        changed = sum(results)
        print(f"\n=== Summary ===")
        print(f"Total:         {len(prs)}")
        print(f"Would rewrite: {changed}")
        print(f"Would skip:    {len(prs) - changed}")
        print(f"\nRun with --apply to make changes.")
    else:
        worktree_base = Path(tempfile.mkdtemp(prefix="fix-jur-"))
        try:
            results = await asyncio.gather(*[apply_pr(semaphore, gh_semaphore, pr, worktree_base) for pr in prs])
            for r in results:
                print(r)
        finally:
            shutil.rmtree(worktree_base, ignore_errors=True)
        errors = [r for r in results if "ERROR" in r]
        print(f"\n=== Summary ===")
        print(f"Total:  {len(prs)}")
        print(f"Errors: {len(errors)}")


if __name__ == "__main__":
    apply = "--apply" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    asyncio.run(main(apply, limit))
