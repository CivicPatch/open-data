"""Tests for scraper-level logic that can be exercised without network calls."""
import pytest


# ── NJ GEOID suffix fallback ──────────────────────────────────────────────────
# Extracted from nj.py: when a census GEOID doesn't directly match a wiki entry,
# NJ falls back to matching by state prefix (first 2 chars) + place suffix (last 5 chars).

def geoid_suffix_match(geoid: str, entries: dict) -> list[str]:
    """Mirror of the fallback logic in nj.py scrape()."""
    state_prefix = geoid[:2]
    place_suffix = geoid[-5:]
    return [k for k in entries if k.startswith(state_prefix) and k.endswith(place_suffix)]


class TestNjGeoidSuffixFallback:
    def test_matches_when_prefix_and_suffix_align(self):
        # Census GEOID 3436000, wiki has 3401736000 (extra county digits in middle)
        entries = {"3401736000": {}}
        assert geoid_suffix_match("3436000", entries) == ["3401736000"]

    def test_no_match_when_suffix_differs(self):
        entries = {"3401799999": {}}
        assert geoid_suffix_match("3436000", entries) == []

    def test_no_match_when_state_prefix_differs(self):
        entries = {"4501736000": {}}  # SC prefix, not NJ
        assert geoid_suffix_match("3436000", entries) == []

    def test_multiple_matches_returns_all(self):
        # Two wiki entries share the same state prefix and place suffix
        entries = {
            "3401736000": {},
            "3402236000": {},
        }
        matches = geoid_suffix_match("3436000", entries)
        assert len(matches) == 2

    def test_short_geoid_uses_available_chars(self):
        # Should not crash on short GEOIDs; slice behaviour is defined
        entries = {"3400100": {}}
        result = geoid_suffix_match("3400100", entries)
        assert isinstance(result, list)


# ── Scraper return contract ───────────────────────────────────────────────────
# Every state scraper must return (dict, list). Test this contract with minimal
# mock census_data so we don't make real network calls.

from unittest.mock import patch
from schemas import Jurisdiction


def _census(ocdid, geoid, name="Test city"):
    return {ocdid: Jurisdiction(id=ocdid, name=name, geoid=geoid, population=1000)}


SCRAPERS = [
    ("scripts.scrapers.co",  "co"),
    ("scripts.scrapers.mi",  "mi"),
    ("scripts.scrapers.nj",  "nj"),
    ("scripts.scrapers.sc",  "sc"),
    ("scripts.scrapers.wa",  "wa"),
]

@pytest.mark.parametrize("module_path,state", SCRAPERS)
def test_scraper_return_type(module_path, state):
    """Each scraper must return (dict, list) and not crash on empty census_data."""
    import importlib
    mod = importlib.import_module(module_path)

    empty_cache = {}
    empty_entries = ({}, {}, [])  # (entries_by_geoid, table_names, warnings)

    with patch("scripts.scrapers.wikipedia_utils.get_entries", return_value=empty_entries), \
         patch("scripts.scrapers.wikipedia_utils._load_cache", return_value=empty_cache), \
         patch("scripts.scrapers.wikipedia_utils._save_cache"):
        result, warnings = mod.scrape({}, limit=0)

    assert isinstance(result, dict)
    assert isinstance(warnings, list)


@pytest.mark.parametrize("module_path,state", SCRAPERS)
def test_scraper_no_data_loss(module_path, state):
    """Scraper must return all census entries even when none match wiki."""
    import importlib
    mod = importlib.import_module(module_path)

    ocdid = f"ocd-jurisdiction/country:us/state:{state}/place:testville/government"
    census = _census(ocdid, "9900001")

    empty_entries = ({}, {}, [])

    with patch("scripts.scrapers.wikipedia_utils.get_entries", return_value=empty_entries), \
         patch("scripts.scrapers.wikipedia_utils._load_cache", return_value={}), \
         patch("scripts.scrapers.wikipedia_utils._save_cache"):
        result, _ = mod.scrape(census, limit=0)

    assert ocdid in result, f"{state}: census entry was dropped by scraper"
