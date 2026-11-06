from scripts.github_actions.sync_config_push import changed_config_paths


def test_keeps_only_config_files_in_order():
    names = [
        "data_source/or/local/config.yml",
        "data_source/or/local/jurisdictions.yml",
        "data_source/local/config.yml",
        "data/or/local/albany.yml",
        "data_source/or/counties/config.yml",
        "README.md",
    ]

    assert changed_config_paths(names) == [
        "data_source/or/local/config.yml",
        "data_source/local/config.yml",
        "data_source/or/counties/config.yml",
    ]


def test_nothing_changed_gives_nothing():
    assert changed_config_paths([]) == []
