import pytest
from scripts.track_progress.compare import (
    build_locality_entry,
    compare_fields,
    is_vacant,
    to_place_jurisdiction,
)


# ── is_vacant ─────────────────────────────────────────────────────────────────

class TestIsVacant:
    def test_vacant(self):
        assert is_vacant("Vacant") is True

    def test_vacancy(self):
        assert is_vacant("Vacancy") is True

    def test_position_vacant(self):
        assert is_vacant("Position Vacant") is True

    def test_case_insensitive(self):
        assert is_vacant("VACANT") is True
        assert is_vacant("vacant") is True

    def test_real_name_not_vacant(self):
        assert is_vacant("Jane Smith") is False

    def test_empty_string(self):
        assert is_vacant("") is False


# ── to_place_jurisdiction ─────────────────────────────────────────────────────

class TestToPlaceJurisdiction:
    def test_already_at_place_level(self):
        jid = "ocd-jurisdiction/country:us/state:tx/place:austin/government"
        assert to_place_jurisdiction(jid) == jid

    def test_strips_sub_division(self):
        jid = "ocd-jurisdiction/country:us/state:tx/place:austin/council_district:5/government"
        assert to_place_jurisdiction(jid) == (
            "ocd-jurisdiction/country:us/state:tx/place:austin/government"
        )

    def test_no_place_segment_returns_none(self):
        jid = "ocd-jurisdiction/country:us/state:tx/government"
        assert to_place_jurisdiction(jid) is None

    def test_county_subdivision_with_place(self):
        jid = "ocd-jurisdiction/country:us/state:nj/county:morris/place:springfield/government"
        assert to_place_jurisdiction(jid) == jid

    def test_multi_word_place(self):
        jid = "ocd-jurisdiction/country:us/state:sc/place:mount_pleasant/government"
        assert to_place_jurisdiction(jid) == jid

    def test_empty_string_returns_none(self):
        assert to_place_jurisdiction("") is None


# ── compare_fields ────────────────────────────────────────────────────────────

class TestCompareFields:
    def _record(self, role=None, division=None, phones=None, emails=None):
        r = {}
        if role or division:
            r["office"] = {}
            if role:
                r["office"]["name"] = role
            if division:
                r["office"]["division_ocdid"] = division
        if phones is not None:
            r["phones"] = phones
        if emails is not None:
            r["emails"] = emails
        return r

    def test_no_diffs_when_identical(self):
        r = self._record(role="Mayor", phones=["(503) 555-0100"])
        assert compare_fields(r, r) == {}

    def test_role_diff_detected(self):
        cp  = self._record(role="Mayor")
        ext = self._record(role="City Manager")
        diffs = compare_fields(cp, ext)
        assert "role" in diffs
        assert diffs["role"] == ("Mayor", "City Manager")

    def test_no_diff_when_one_side_missing_role(self):
        cp  = self._record(role="Mayor")
        ext = self._record()
        assert compare_fields(cp, ext) == {}

    def test_phone_diff_detected(self):
        cp  = self._record(phones=["(503) 555-0100"])
        ext = self._record(phones=["(503) 555-0199"])
        diffs = compare_fields(cp, ext)
        assert "phone" in diffs

    def test_no_diff_when_both_phones_empty(self):
        cp  = self._record(phones=[])
        ext = self._record(phones=[])
        assert compare_fields(cp, ext) == {}

    def test_email_diff_detected(self):
        cp  = self._record(emails=["a@example.com"])
        ext = self._record(emails=["b@example.com"])
        diffs = compare_fields(cp, ext)
        assert "email" in diffs

    def test_division_diff_detected(self):
        cp  = self._record(division="ocd-division/country:us/state:wa/place:seattle")
        ext = self._record(division="ocd-division/country:us/state:wa/place:tacoma")
        diffs = compare_fields(cp, ext)
        assert "division" in diffs


# ── build_locality_entry ──────────────────────────────────────────────────────

def _official(name, role="Mayor"):
    return {"name": name, "office": {"name": role}, "phones": [], "emails": []}

JURISDICTION = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"


class TestBuildLocalityEntry:
    def test_matched_record(self):
        cp  = [_official("Jane Smith")]
        ext = [_official("Jane Smith")]
        result = build_locality_entry(cp, ext, JURISDICTION)
        assert result["name_matched"] == 1
        assert result["name_match_pct"] == 1.0
        assert result["status"] == "good"

    def test_only_external(self):
        ext = [_official("Jane Smith")]
        result = build_locality_entry([], ext, JURISDICTION)
        assert result["civicpatch_count"] == 0
        assert result["only_external"] == 1
        assert result["status"] == "missing"

    def test_only_civicpatch(self):
        cp = [_official("Jane Smith")]
        result = build_locality_entry(cp, [], JURISDICTION)
        assert result["only_civicpatch"] == 1
        assert result["name_match_pct"] == 0.0
        assert result["status"] == "poor"

    def test_status_good_at_80_pct(self):
        cp  = [_official(f"Person {i}") for i in range(8)]
        ext = [_official(f"Person {i}") for i in range(10)]
        result = build_locality_entry(cp, ext, JURISDICTION)
        assert result["status"] == "good"

    def test_status_partial_between_40_and_80(self):
        cp  = [_official(f"Person {i}") for i in range(5)]
        ext = [_official(f"Person {i}") for i in range(10)]
        result = build_locality_entry(cp, ext, JURISDICTION)
        assert result["status"] == "partial"

    def test_status_poor_below_40_with_cp_data(self):
        cp  = [_official("Only One")]
        ext = [_official(f"Person {i}") for i in range(10)]
        result = build_locality_entry(cp, ext, JURISDICTION)
        assert result["status"] == "poor"

    def test_vacancies_excluded_from_matching(self):
        cp  = [_official("Vacant"), _official("Jane Smith")]
        ext = [_official("Jane Smith")]
        result = build_locality_entry(cp, ext, JURISDICTION)
        assert result["name_matched"] == 1
        assert result["civicpatch_count"] == 1  # Vacant excluded

    def test_place_extracted_from_jurisdiction(self):
        result = build_locality_entry([], [], JURISDICTION)
        assert result["place"] == "seattle"
