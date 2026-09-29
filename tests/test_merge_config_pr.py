from scripts.github_actions.merge_config_pr import (
    APP_BOT,
    VALIDATION_CHECK,
    labelled_by_app,
    only_config_files,
    refusal,
    validation_passed,
)

LABEL = "civicpatch:maintainer"


def _labeled(name: str, actor: str) -> dict:
    return {"event": "labeled", "label": {"name": name}, "actor": {"login": actor}}


def _check(conclusion: str, started_at: str = "2026-09-28T10:00:00Z") -> dict:
    return {"name": VALIDATION_CHECK, "status": "completed", "conclusion": conclusion, "started_at": started_at}


def _pull_request(**overrides) -> dict:
    return {
        "state": "open",
        "draft": False,
        "base": {"ref": "main"},
        "labels": [{"name": LABEL}],
        **overrides,
    }


def test_a_label_from_the_app_counts():
    assert labelled_by_app([_labeled(LABEL, APP_BOT)], {LABEL})


def test_a_label_a_person_added_does_not():
    assert not labelled_by_app([_labeled(LABEL, "someone")], {LABEL})


def test_the_most_recent_labelling_decides():
    """The app labelled it, then someone removed it and added it back."""
    events = [_labeled(LABEL, APP_BOT), _labeled(LABEL, "someone")]

    assert not labelled_by_app(events, {LABEL})


def test_a_removed_label_does_not_count():
    assert not labelled_by_app([_labeled(LABEL, APP_BOT)], set())


def test_config_paths_at_both_layers_and_levels():
    assert only_config_files(
        [
            "data_source/config.yml",
            "data_source/local/config.yml",
            "data_source/counties/config.yml",
            "data_source/tn/local/config.yml",
            "data_source/tn/counties/config.yml",
        ]
    )


def test_anything_else_is_not_config():
    assert not only_config_files(["data_source/tn/local/config.yml", "data_source/tn/local/jurisdictions.yml"])
    assert not only_config_files([".github/workflows/merge_config.yml"])
    assert not only_config_files(["data_source/wa/config.yml"])
    assert not only_config_files(["data_source/mi/local/county_alcona__place_alcona/config.yml"])
    assert not only_config_files([])


def test_the_latest_validation_run_decides():
    assert validation_passed([_check("failure", "2026-09-28T09:00:00Z"), _check("success")])
    assert not validation_passed([_check("success", "2026-09-28T09:00:00Z"), _check("failure")])


def test_no_validation_run_is_not_a_pass():
    assert not validation_passed([])


def test_a_pr_passing_every_check_merges():
    paths = ["data_source/tn/counties/config.yml"]

    assert refusal(_pull_request(), [_labeled(LABEL, APP_BOT)], paths, [_check("success")]) is None


def test_a_draft_stays_open():
    paths = ["data_source/tn/counties/config.yml"]

    assert refusal(_pull_request(draft=True), [_labeled(LABEL, APP_BOT)], paths, [_check("success")])
