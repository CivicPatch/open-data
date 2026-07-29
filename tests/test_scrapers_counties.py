from unittest.mock import MagicMock, patch

from schemas import Jurisdiction
from scripts.jurisdictions.scrapers.counties import _flag_missing_urls, scrape


def _j(name, **kwargs):
    return Jurisdiction(id=f"ocd/{name}", name=name, **kwargs)


# ── _flag_missing_urls ────────────────────────────────────────────────────────

class TestFlagMissingUrls:
    def test_flags_matched_county_without_a_website(self):
        j = _j("Suffolk County", wiki_url="https://wiki/suffolk")
        _flag_missing_urls({"a": j})
        assert j.issues == ["no_official_url"]

    def test_does_not_flag_when_a_url_was_found(self):
        j = _j("Norfolk County", wiki_url="https://wiki/norfolk", url="https://norfolkcounty.org")
        _flag_missing_urls({"a": j})
        assert j.issues is None

    def test_does_not_flag_an_unmatched_county(self):
        """An unmatched county already carries no_wiki_match — don't double-report."""
        j = _j("Ghost County", issues=["no_wiki_match"])
        _flag_missing_urls({"a": j})
        assert j.issues == ["no_wiki_match"]

    def test_does_not_flag_when_the_infobox_was_never_read(self):
        """A failed or budget-skipped fetch means 'unknown', not 'has no website'."""
        j = _j("Unchecked County", wiki_url="https://wiki/unchecked")
        _flag_missing_urls({"a": j}, unknown_url_pages={"https://wiki/unchecked"})
        assert j.issues is None

    def test_preserves_other_issues(self):
        j = _j("Odd County", wiki_url="https://wiki/odd", issues=["geoid_mismatch"])
        _flag_missing_urls({"a": j})
        assert j.issues == ["geoid_mismatch", "no_official_url"]

    def test_is_idempotent(self):
        j = _j("Suffolk County", wiki_url="https://wiki/suffolk", issues=["no_official_url"])
        _flag_missing_urls({"a": j})
        assert j.issues == ["no_official_url"]


# ── scrape ────────────────────────────────────────────────────────────────────

class TestScrape:
    def _scrape(self, census_data, entries, warnings=None):
        stub = MagicMock(return_value=(entries, {}, warnings or []))
        with patch("scripts.jurisdictions.scrapers.counties.wikipedia_utils.get_entries", stub):
            result, warns = scrape(census_data, "ma", "Massachusetts", "25")
        return result, warns, stub.call_args.kwargs

    def test_builds_the_page_title_from_the_state_name(self):
        _, _, kwargs = self._scrape({}, {})
        assert kwargs["title"] == "List_of_counties_in_Massachusetts"

    def test_sources_the_geoid_from_the_table_prefixed_by_fips(self):
        _, _, kwargs = self._scrape({}, {})
        assert kwargs["geoid_column"] == 1
        assert kwargs["geoid_prefix"] == "25"

    def test_namespaces_the_cache_away_from_the_municipality_scrape(self):
        _, _, kwargs = self._scrape({}, {})
        assert kwargs["cache_key"] == "ma_counties"
        assert kwargs["state"] == "ma"

    def test_attaches_url_and_flags_a_county_with_no_website(self):
        census = {
            "with": _j("Norfolk County", geoid="25021"),
            "without": _j("Suffolk County", geoid="25025"),
        }
        entries = {
            "25021": {"wiki_url": "https://wiki/norfolk", "geoid": "25021",
                      "url": "https://norfolkcounty.org"},
            "25025": {"wiki_url": "https://wiki/suffolk", "geoid": "25025", "url": ""},
        }
        result, _, _ = self._scrape(census, entries)
        assert result["with"].url == "https://norfolkcounty.org"
        assert result["with"].issues is None
        assert result["without"].issues == ["no_official_url"]

    def test_does_not_flag_a_county_whose_infobox_failed_to_load(self):
        census = {"a": _j("Unchecked County", geoid="25025")}
        entries = {
            "25025": {"wiki_url": "https://wiki/unchecked", "geoid": "25025",
                      "url": "", "url_unknown": True},
        }
        result, _, _ = self._scrape(census, entries)
        assert result["a"].wiki_url == "https://wiki/unchecked"
        assert result["a"].issues is None

    def test_propagates_scrape_warnings(self):
        _, warns, _ = self._scrape({}, {}, warnings=["infobox boom"])
        assert "infobox boom" in warns
