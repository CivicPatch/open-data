from scripts.github_actions.merge_jurisdiction_pr import (
    VALIDATION_CHECK,
    labelled_by_app,
    only_jurisdiction_files,
    refusal,
)

LABEL = "civicpatch:system"
APP_OWNER = "CivicPatch"
PATHS = ["data_source/wa/local/jurisdictions.yml"]


def _labeled(name: str, app_owner: str | None) -> dict:
    app = {"slug": "civicpatch", "owner": {"login": app_owner}} if app_owner else None
    return {"event": "labeled", "label": {"name": name}, "performed_via_github_app": app}


def _check(conclusion: str) -> dict:
    return {"name": VALIDATION_CHECK, "status": "completed", "conclusion": conclusion, "started_at": "2026-10-01T10:00:00Z"}


def _pull_request(**overrides) -> dict:
    return {
        "state": "open",
        "draft": False,
        "base": {"ref": "main"},
        "labels": [{"name": LABEL}],
        **overrides,
    }


def test_every_edit_source_label_from_the_app_counts():
    for label in ("civicpatch:system", "civicpatch:maintainer", "civicpatch:admin"):
        assert labelled_by_app([_labeled(label, APP_OWNER)], {label})


def test_a_label_a_person_added_does_not():
    assert not labelled_by_app([_labeled(LABEL, None)], {LABEL})


def test_jurisdictions_files_at_every_level():
    assert only_jurisdiction_files(
        [
            "data_source/wa/local/jurisdictions.yml",
            "data_source/wa/counties/jurisdictions.yml",
            "data_source/wa/state/jurisdictions.yml",
        ]
    )


def test_anything_else_is_not_a_jurisdiction_edit():
    assert not only_jurisdiction_files(["data_source/wa/local/jurisdictions.yml", "data_source/config.yml"])
    assert not only_jurisdiction_files(["data/wa/local/seattle.yml"])
    assert not only_jurisdiction_files([])


def test_a_pr_passing_every_check_merges():
    assert refusal(_pull_request(), [_labeled(LABEL, APP_OWNER)], PATHS, [_check("success")]) is None


def test_a_failed_validation_stays_open():
    assert refusal(_pull_request(), [_labeled(LABEL, APP_OWNER)], PATHS, [_check("failure")])


def test_a_draft_stays_open():
    assert refusal(_pull_request(draft=True), [_labeled(LABEL, APP_OWNER)], PATHS, [_check("success")])
