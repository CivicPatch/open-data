from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from schemas import Jurisdiction
from scripts.jurisdictions.scrapers.wikipedia_utils import (
    _cell_text,
    find_candidates,
    get_entries,
    get_parse_url,
    get_wiki_url,
    match_jurisdictions,
    normalize_geoid,
    normalize_td,
    warn_unmatched_wiki_entries,
)


def make_td(html: str):
    return BeautifulSoup(html, "html.parser").find("td")


# ── normalize_geoid ───────────────────────────────────────────────────────────

class TestNormalizeGeoid:
    def test_strips_hyphen(self):
        assert normalize_geoid("45-00100") == "4500100"

    def test_no_hyphen_unchanged(self):
        assert normalize_geoid("4500100") == "4500100"

    def test_multiple_hyphens(self):
        assert normalize_geoid("45-001-00") == "4500100"

    def test_empty_string(self):
        assert normalize_geoid("") == ""


# ── get_parse_url ─────────────────────────────────────────────────────────────

class TestGetParseUrl:
    def test_wiki_path(self):
        assert get_parse_url("/wiki/Seattle,_Washington") == (
            "https://en.wikipedia.org/w/api.php?action=parse&page=Seattle,_Washington&format=json"
        )

    def test_bare_title(self):
        assert get_parse_url("Seattle,_Washington") == (
            "https://en.wikipedia.org/w/api.php?action=parse&page=Seattle,_Washington&format=json"
        )

    def test_trailing_slash_stripped(self):
        result = get_parse_url("/wiki/Seattle,_Washington/")
        assert "page=Seattle,_Washington" in result
        assert result.endswith("&format=json")


# ── get_wiki_url ──────────────────────────────────────────────────────────────

class TestGetWikiUrl:
    def test_converts_path_to_full_url(self):
        assert get_wiki_url("/wiki/Seattle,_Washington") == (
            "https://en.wikipedia.org/wiki/Seattle,_Washington"
        )

    def test_bare_title(self):
        assert get_wiki_url("Seattle,_Washington") == (
            "https://en.wikipedia.org/wiki/Seattle,_Washington"
        )


# ── normalize_td ──────────────────────────────────────────────────────────────

class TestNormalizeTd:
    def test_td_with_link(self):
        td = make_td('<td><a href="/wiki/Seattle,_Washington">Seattle</a></td>')
        result = normalize_td(td)
        assert result["text"] == "Seattle"
        assert result["url"] == "/wiki/Seattle,_Washington"

    def test_td_without_link(self):
        td = make_td("<td>Plain text</td>")
        result = normalize_td(td)
        assert result["text"] == "Plain text"
        assert result["url"] == ""

    def test_td_with_superscript(self):
        # Superscript footnote should not affect the main link text
        td = make_td('<td><a href="/wiki/Foo">Foo</a><sup>[1]</sup></td>')
        result = normalize_td(td)
        assert result["text"] == "Foo"
        assert result["url"] == "/wiki/Foo"

    def test_none_input(self):
        result = normalize_td(None)
        assert result == {"text": "", "url": ""}


# ── find_candidates ───────────────────────────────────────────────────────────

class TestFindCandidates:
    TABLE = {
        "Seattle": "https://en.wikipedia.org/wiki/Seattle",
        "Tacoma": "https://en.wikipedia.org/wiki/Tacoma,_Washington",
        "East Seattle": "https://en.wikipedia.org/wiki/East_Seattle",
    }

    def test_exact_base_name_match(self):
        results = find_candidates("Seattle city", self.TABLE)
        assert "https://en.wikipedia.org/wiki/Seattle" in results

    def test_partial_match(self):
        # "seattle" appears in both "Seattle" and "East Seattle"
        results = find_candidates("Seattle city", self.TABLE)
        assert len(results) == 2

    def test_no_match(self):
        results = find_candidates("Portland city", self.TABLE)
        assert results == []

    def test_single_word_name(self):
        # Single-word name: base_name = full name lowercased
        results = find_candidates("Tacoma", self.TABLE)
        assert "https://en.wikipedia.org/wiki/Tacoma,_Washington" in results

    def test_case_insensitive(self):
        results = find_candidates("TACOMA city", self.TABLE)
        assert "https://en.wikipedia.org/wiki/Tacoma,_Washington" in results


# ── warn_unmatched_wiki_entries ───────────────────────────────────────────────

class TestWarnUnmatchedWikiEntries:
    def test_no_warnings_when_all_matched(self):
        entries = {"1234567": {"wiki_url": "https://en.wikipedia.org/wiki/Foo"}}
        warnings = warn_unmatched_wiki_entries(entries, matched_geoids={"1234567"})
        assert warnings == []

    def test_warning_for_unmatched_geoid(self):
        entries = {"1234567": {"wiki_url": "https://en.wikipedia.org/wiki/Foo"}}
        warnings = warn_unmatched_wiki_entries(entries, matched_geoids=set())
        assert len(warnings) == 1
        assert "1234567" in warnings[0]

    def test_empty_geoid_skipped(self):
        entries = {"": {"wiki_url": "https://en.wikipedia.org/wiki/Foo"}}
        warnings = warn_unmatched_wiki_entries(entries, matched_geoids=set())
        assert warnings == []


# ── match_jurisdictions ───────────────────────────────────────────────────────

def make_jurisdiction(geoid: str, name: str = "Somewhere city", **kw) -> Jurisdiction:
    return Jurisdiction(id=f"ocd/{geoid}", name=name, geoid=geoid, **kw)


def entry(geoid: str, slug: str) -> dict:
    return {
        "geoid": geoid,
        "wiki_url": f"https://en.wikipedia.org/wiki/{slug}",
        "url": f"https://{slug.split(',')[0].lower()}.gov",
    }


class TestMatchJurisdictions:
    def test_direct_geoid_match(self):
        # Census place geoid exactly equals the wiki entry key.
        census = {"ocd/a": make_jurisdiction("3345140", "Manchester city")}
        entries = {"3345140": entry("3345140", "Manchester,_New_Hampshire")}
        result, warnings = match_jurisdictions(census, entries, table_names={})
        j = result["ocd/a"]
        assert j.wiki_url == "https://en.wikipedia.org/wiki/Manchester,_New_Hampshire"
        assert j.url == "https://manchester.gov"
        assert j.issues is None
        assert warnings == []

    def test_suffix_fallback_cousub_vs_place(self):
        # Census county-subdivision geoid (10-digit) vs a place geoid (7-digit) for the
        # same town: same state prefix + same last-5 → matched, flagged geoid_mismatch.
        census = {"ocd/a": make_jurisdiction("3300512340", "Anytown town")}
        entries = {"3312340": entry("3312340", "Anytown,_New_Hampshire")}
        result, _ = match_jurisdictions(census, entries, table_names={})
        j = result["ocd/a"]
        assert j.wiki_url.endswith("Anytown,_New_Hampshire")
        assert j.issues == ["geoid_mismatch"]
        assert "GEOID suffix fallback" in (j.generated_comments or "")

    def test_bare_place_fips_matches_place_geoid(self):
        # The Keene case: infobox lists the bare 5-digit place FIPS "39300" (no state
        # prefix); census place geoid is "3339300". Should match via the bare-code clause.
        census = {"ocd/keene": make_jurisdiction("3339300", "Keene city")}
        entries = {"39300": entry("39300", "Keene,_New_Hampshire")}
        result, _ = match_jurisdictions(census, entries, table_names={})
        j = result["ocd/keene"]
        assert j.wiki_url.endswith("Keene,_New_Hampshire")
        assert j.issues == ["geoid_mismatch"]

    def test_bare_place_fips_does_not_match_cousub(self):
        # DANGER GUARD: a bare 5-digit place code must NOT match a county-subdivision
        # census geoid (10-digit) that merely happens to end in the same 5 digits.
        census = {"ocd/cousub": make_jurisdiction("3300939300", "Elsewhere town")}
        entries = {"39300": entry("39300", "Keene,_New_Hampshire")}
        result, _ = match_jurisdictions(census, entries, table_names={})
        j = result["ocd/cousub"]
        assert j.wiki_url is None
        assert j.issues == ["no_wiki_match"]

    def test_no_match_flags_no_wiki_match(self):
        census = {"ocd/a": make_jurisdiction("3399999", "Nowhere city")}
        entries = {"3345140": entry("3345140", "Manchester,_New_Hampshire")}
        result, _ = match_jurisdictions(census, entries, table_names={})
        j = result["ocd/a"]
        assert j.wiki_url is None
        assert j.issues == ["no_wiki_match"]

    def test_places_only_state_is_exact_match(self):
        # For a places-only state every census geoid is 7-digit; the fallback reduces to
        # an exact match (state prefix + full place suffix), so it stays a safe no-op.
        census = {"ocd/a": make_jurisdiction("5300100", "Aberdeen city")}
        # A different place sharing neither prefix-region nor suffix must not match.
        entries = {"5312345": entry("5312345", "Bellevue,_Washington")}
        result, _ = match_jurisdictions(census, entries, table_names={})
        assert result["ocd/a"].issues == ["no_wiki_match"]

    def test_existing_no_wiki_match_cleared_on_match(self):
        # Re-run idempotency: a stale no_wiki_match issue is removed once a match is found.
        census = {"ocd/a": make_jurisdiction("3345140", "Manchester city", issues=["no_wiki_match"])}
        entries = {"3345140": entry("3345140", "Manchester,_New_Hampshire")}
        result, _ = match_jurisdictions(census, entries, table_names={})
        assert result["ocd/a"].issues is None


# ── _cell_text ────────────────────────────────────────────────────────────────

class TestCellText:
    def test_plain_text(self):
        assert _cell_text(make_td("<td>001</td>")) == "001"

    def test_prefers_link_text(self):
        # Texas links each county's FIPS code out to census.gov
        td = make_td('<td><a href="https://www.census.gov/x">001</a></td>')
        assert _cell_text(td) == "001"

    def test_strips_reference_superscripts(self):
        td = make_td('<td>001<sup class="reference">[1]</sup></td>')
        assert _cell_text(td) == "001"

    def test_none_returns_empty(self):
        assert _cell_text(None) == ""


# ── get_entries: table-sourced GEOIDs ─────────────────────────────────────────

COUNTY_LIST_HTML = """
<table class="wikitable">
  <tr><th>County</th><th>FIPS code</th></tr>
  <tr><td><a href="/wiki/Alpha_County">Alpha County</a></td><td>001</td></tr>
  <tr><td><a href="/wiki/Beta_County">Beta County</a></td><td>003</td></tr>
</table>
"""

INFOBOX_HTML = """
<table class="infobox">
  <tr><th>Website</th><td><a href="https://alpha.example">alpha.example</a></td></tr>
</table>
"""


def _fake_parse(html: str):
    mock = MagicMock()
    mock.json.return_value = {"parse": {"text": {"*": html}}}
    return mock


class TestGetEntriesTableGeoid:
    def _get(self, **kwargs):
        # First call fetches the list page, every later call an infobox
        responses = [_fake_parse(COUNTY_LIST_HTML)] + [_fake_parse(INFOBOX_HTML)] * 5
        with patch("scripts.jurisdictions.scrapers.wikipedia_utils.requests.get", side_effect=responses), \
             patch("scripts.jurisdictions.scrapers.wikipedia_utils.time.sleep"):
            return get_entries(
                title="List_of_counties_in_Example",
                table_index=0, rows_to_skip=1, entry_column=0,
                geoid_column=1, **kwargs,
            )

    def test_geoid_comes_from_table_and_is_prefixed(self):
        entries, _, warnings = self._get(geoid_prefix="45")
        assert set(entries) == {"45001", "45003"}
        assert warnings == []

    def test_url_still_comes_from_infobox(self):
        entries, _, _ = self._get(geoid_prefix="45")
        assert entries["45001"]["url"] == "https://alpha.example"
        assert entries["45001"]["wiki_url"] == "https://en.wikipedia.org/wiki/Alpha_County"

    def test_entries_survive_the_fetch_budget(self):
        # Only one infobox is fetched, but both counties are matchable because the
        # GEOID and wiki_url come from the table.
        entries, _, _ = self._get(geoid_prefix="45", limit=1)
        assert set(entries) == {"45001", "45003"}
        assert entries["45003"]["url"] == ""

    def test_no_prefix_uses_table_value_verbatim(self):
        entries, _, _ = self._get()
        assert set(entries) == {"001", "003"}

    def test_row_shorter_than_the_geoid_column_is_skipped_with_a_warning(self):
        html = """
        <table class="wikitable">
          <tr><th>County</th><th>FIPS code</th></tr>
          <tr><td><a href="/wiki/Short_County">Short County</a></td></tr>
        </table>
        """
        with patch("scripts.jurisdictions.scrapers.wikipedia_utils.requests.get",
                   side_effect=[_fake_parse(html)]), \
             patch("scripts.jurisdictions.scrapers.wikipedia_utils.time.sleep"):
            entries, _, warnings = get_entries(
                title="T", table_index=0, rows_to_skip=1, entry_column=0,
                geoid_column=1, geoid_prefix="45")
        assert entries == {}
        assert any("No GEOID column" in w for w in warnings)

    def test_empty_geoid_cell_is_skipped_with_a_warning(self):
        html = """
        <table class="wikitable">
          <tr><th>County</th><th>FIPS code</th></tr>
          <tr><td><a href="/wiki/Blank_County">Blank County</a></td><td></td></tr>
        </table>
        """
        with patch("scripts.jurisdictions.scrapers.wikipedia_utils.requests.get",
                   side_effect=[_fake_parse(html)]), \
             patch("scripts.jurisdictions.scrapers.wikipedia_utils.time.sleep"):
            entries, _, warnings = get_entries(
                title="T", table_index=0, rows_to_skip=1, entry_column=0,
                geoid_column=1, geoid_prefix="45")
        assert entries == {}
        assert any("Empty GEOID" in w for w in warnings)

    def test_row_shorter_than_the_entry_column_is_skipped(self):
        html = """
        <table class="wikitable">
          <tr><th>County</th><th>FIPS code</th></tr>
          <tr></tr>
          <tr><td><a href="/wiki/Alpha_County">Alpha County</a></td><td>001</td></tr>
        </table>
        """
        with patch("scripts.jurisdictions.scrapers.wikipedia_utils.requests.get",
                   side_effect=[_fake_parse(html), _fake_parse(INFOBOX_HTML)]), \
             patch("scripts.jurisdictions.scrapers.wikipedia_utils.time.sleep"):
            entries, _, _ = get_entries(
                title="T", table_index=0, rows_to_skip=1, entry_column=0,
                geoid_column=1, geoid_prefix="45")
        assert set(entries) == {"45001"}

    def test_failed_infobox_marks_url_unknown_and_warns(self):
        broken = MagicMock()
        broken.json.side_effect = ValueError("bad json")
        with patch("scripts.jurisdictions.scrapers.wikipedia_utils.requests.get",
                   side_effect=[_fake_parse(COUNTY_LIST_HTML), broken, broken]), \
             patch("scripts.jurisdictions.scrapers.wikipedia_utils.time.sleep"):
            entries, _, warnings = get_entries(
                title="T", table_index=0, rows_to_skip=1, entry_column=0,
                geoid_column=1, geoid_prefix="45")
        assert entries["45001"]["url_unknown"] is True
        assert entries["45001"]["url"] == ""
        assert any("official website unknown" in w for w in warnings)

    def test_budget_skipped_entry_is_url_unknown_but_not_warned(self):
        entries, _, warnings = self._get(geoid_prefix="45", limit=1)
        assert "url_unknown" not in entries["45001"]      # fetched
        assert entries["45003"]["url_unknown"] is True    # past the budget
        assert not any("official website unknown" in w for w in warnings)
