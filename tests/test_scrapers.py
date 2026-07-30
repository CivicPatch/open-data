"""Generic municipality scraper: config handling and the shared matching path.

Replaces per-state scraper tests. Those asserted a `(dict, list)` return contract against
five of eleven modules with `get_entries` mocked to return nothing, so no matching was
ever exercised — and a hand-copied reimplementation of the GEOID fallback that would have
passed even if the production code were deleted. Matching itself is covered against the
real `match_jurisdictions` in test_wikipedia_utils.py.
"""

from unittest.mock import patch

import pytest

from schemas import Jurisdiction
from scripts.jurisdictions.config import state_configs
from scripts.jurisdictions.scrapers import municipalities, wikipedia_utils

EMPTY_PAGE = ({}, {}, [])   # (entries_by_geoid, table_names, warnings)


def _census(state="nh", geoid="3345140", name="Testville city"):
    ocdid = f"ocd-jurisdiction/country:us/state:{state}/place:testville/government"
    return ocdid, {ocdid: Jurisdiction(id=ocdid, name=name, geoid=geoid, population=1000)}


def _scrape(census=None, state="nh", state_name="New Hampshire", wiki=None, page=EMPTY_PAGE):
    """Run the scraper with the page fetch stubbed; return (result, warnings, get_entries kwargs)."""
    stub = patch.object(wikipedia_utils, "get_entries", return_value=page)
    with stub as mock:
        result, warnings = municipalities.scrape(census or {}, state, state_name, wiki)
    return result, warnings, mock.call_args.kwargs


class TestPageTitle:
    def test_derived_from_the_state_name(self):
        _, _, kwargs = _scrape(state_name="New Hampshire")
        assert kwargs["title"] == "List_of_municipalities_in_New_Hampshire"

    def test_title_override_wins(self):
        """Georgia's conventional title is a disambiguation page (country vs U.S. state)."""
        _, _, kwargs = _scrape(
            state="ga", state_name="Georgia",
            wiki={"title": "List_of_municipalities_in_Georgia_(U.S._state)"},
        )
        assert kwargs["title"] == "List_of_municipalities_in_Georgia_(U.S._state)"


class TestTableCoordinates:
    def test_defaults_when_no_overrides(self):
        _, _, kwargs = _scrape(wiki={})
        assert (kwargs["table_index"], kwargs["rows_to_skip"], kwargs["entry_column"]) == (0, 1, 0)

    def test_overrides_are_applied(self):
        _, _, kwargs = _scrape(wiki={"table_index": 1, "rows_to_skip": 2, "entry_column": 1})
        assert (kwargs["table_index"], kwargs["rows_to_skip"], kwargs["entry_column"]) == (1, 2, 1)

    def test_partial_override_keeps_other_defaults(self):
        _, _, kwargs = _scrape(wiki={"rows_to_skip": 2})
        assert kwargs["rows_to_skip"] == 2
        assert kwargs["table_index"] == 0
        assert kwargs["entry_column"] == 0


class TestParserSelection:
    def test_table_is_the_default(self):
        _, _, kwargs = _scrape(wiki={})
        assert kwargs["extract_refs"] is None      # get_entries builds a table reader

    def test_bullet_list_parser_is_passed_through(self):
        _, _, kwargs = _scrape(wiki={"parser": "bullet_list"})
        assert kwargs["extract_refs"] is wikipedia_utils.bullet_list_refs


class TestConfigValidation:
    """Typos should fail loudly at scrape time, not silently do the wrong thing."""

    def test_unknown_parser_raises(self):
        with pytest.raises(ValueError, match="unknown local_wiki parser"):
            _scrape(wiki={"parser": "bullet-list"})    # hyphen, not underscore

    def test_unknown_key_raises(self):
        with pytest.raises(ValueError, match="unknown local_wiki keys"):
            _scrape(wiki={"rows_to_skips": 2})         # trailing s


class TestNoDataLoss:
    def test_census_entries_survive_when_nothing_matches(self):
        ocdid, census = _census()
        result, _, _ = _scrape(census=census)
        assert ocdid in result, "census entry was dropped by the scraper"

    def test_unmatched_entry_is_flagged_not_dropped(self):
        ocdid, census = _census()
        result, _, _ = _scrape(census=census)
        assert result[ocdid].issues == ["no_wiki_match"]


@pytest.mark.parametrize("state", sorted(state_configs))
def test_every_configured_state_scrapes(state):
    """Guards each state's local_wiki against typos and unsupported keys.

    Replaces the old per-module contract tests, and covers all states rather than five.
    """
    config = state_configs[state]
    ocdid, census = _census(state=state)
    result, warnings, _ = _scrape(
        census=census, state=state, state_name=config["name"], wiki=config.get("local_wiki"),
    )
    assert ocdid in result
    assert isinstance(warnings, list)
