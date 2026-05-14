import pytest
from bs4 import BeautifulSoup

from scripts.scrapers.wikipedia_utils import (
    find_candidates,
    get_parse_url,
    get_wiki_url,
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
