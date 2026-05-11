from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.generate_pmtiles import (
    _normalize_county_name,
    _FIPS_TO_STATE_CODE,
    _enrich_state_feature,
    _enrich_county_feature,
    _build_local_lookup,
    _enrich_local_feature,
)


class TestNormalizeCountyName:
    def test_strips_county_suffix(self):
        assert _normalize_county_name("Adams County") == "adams"

    def test_strips_parish_suffix(self):
        assert _normalize_county_name("Orleans Parish") == "orleans"

    def test_strips_borough_suffix(self):
        assert _normalize_county_name("Juneau City and Borough") == "juneau_city"

    def test_multi_word(self):
        assert _normalize_county_name("Rio Grande County") == "rio_grande"

    def test_removes_special_chars(self):
        assert _normalize_county_name("St. Louis County") == "st_louis"


class TestFipsToStateCode:
    def test_returns_correct_mapping(self):
        assert _FIPS_TO_STATE_CODE["08"] == "co"
        assert _FIPS_TO_STATE_CODE["26"] == "mi"
        assert _FIPS_TO_STATE_CODE["34"] == "nj"
        assert _FIPS_TO_STATE_CODE["45"] == "sc"
        assert _FIPS_TO_STATE_CODE["48"] == "tx"
        assert _FIPS_TO_STATE_CODE["53"] == "wa"


class TestEnrichStateFeature:
    def _feature(self):
        return {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[]]},
            "properties": {
                "STATEFP": "08", "STATENS": "01779779", "GEOID": "08",
                "GEOIDFQ": "0400000US08", "STUSPS": "CO", "NAME": "Colorado",
                "REGION": "4", "DIVISION": "8", "LSAD": "00",
                "MTFCC": "G4000", "FUNCSTAT": "A", "ALAND": 268596070292,
                "AWATER": 1174082548, "INTPTLAT": "+38.9938685",
                "INTPTLON": "-105.5090090",
            },
        }

    def test_sets_jurisdiction_ocdid(self):
        result = _enrich_state_feature(self._feature())
        assert result["properties"]["jurisdiction_ocdid"] == "ocd-division/country:us/state:co"

    def test_sets_geoid(self):
        result = _enrich_state_feature(self._feature())
        assert result["properties"]["geoid"] == "08"

    def test_sets_name(self):
        result = _enrich_state_feature(self._feature())
        assert result["properties"]["name"] == "Colorado"

    def test_sets_code(self):
        result = _enrich_state_feature(self._feature())
        assert result["properties"]["code"] == "co"

    def test_strips_census_properties(self):
        result = _enrich_state_feature(self._feature())
        assert "STATEFP" not in result["properties"]
        assert "ALAND" not in result["properties"]
        assert set(result["properties"].keys()) == {"jurisdiction_ocdid", "geoid", "name", "code"}


class TestEnrichCountyFeature:
    def _feature(self):
        return {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[]]},
            "properties": {
                "STATEFP": "08", "COUNTYFP": "001", "COUNTYNS": "00198120",
                "GEOID": "08001", "GEOIDFQ": "0500000US08001", "NAME": "Adams",
                "NAMELSAD": "Adams County", "LSAD": "06", "CLASSFP": "H1",
                "MTFCC": "G4020", "CSAFP": "216", "CBSAFP": "19740",
                "METDIVFP": "", "FUNCSTAT": "A", "ALAND": 1259928850,
                "AWATER": 3515060, "INTPTLAT": "+39.8722645",
                "INTPTLON": "-104.3358884",
            },
        }

    def test_sets_jurisdiction_ocdid(self):
        fips_to_state = {"08": "co"}
        result = _enrich_county_feature(self._feature(), fips_to_state)
        assert result["properties"]["jurisdiction_ocdid"] == "ocd-division/country:us/state:co/county:adams"

    def test_sets_geoid(self):
        fips_to_state = {"08": "co"}
        result = _enrich_county_feature(self._feature(), fips_to_state)
        assert result["properties"]["geoid"] == "08001"

    def test_sets_name_from_namelsad(self):
        fips_to_state = {"08": "co"}
        result = _enrich_county_feature(self._feature(), fips_to_state)
        assert result["properties"]["name"] == "Adams County"

    def test_strips_census_properties(self):
        fips_to_state = {"08": "co"}
        result = _enrich_county_feature(self._feature(), fips_to_state)
        assert "STATEFP" not in result["properties"]
        assert set(result["properties"].keys()) == {"jurisdiction_ocdid", "geoid", "name"}


class TestBuildLocalLookup:
    def test_maps_geoid_to_ocdid_and_name(self):
        jurisdictions = [
            {"id": "ocd-jurisdiction/country:us/state:co/place:denver/government",
             "name": "Denver city", "geoid": "0820000"},
        ]
        lookup = _build_local_lookup(jurisdictions)
        assert lookup["0820000"]["ocdid"] == "ocd-division/country:us/state:co/place:denver"
        assert lookup["0820000"]["name"] == "Denver city"

    def test_skips_entries_without_geoid(self):
        jurisdictions = [{"id": "ocd-jurisdiction/country:us/state:co/place:x/government", "name": "X"}]
        lookup = _build_local_lookup(jurisdictions)
        assert lookup == {}

    def test_integer_geoid_is_not_matched(self):
        # YAML may store geoids as integers if unquoted; str(820000) != "0820000"
        jurisdictions = [
            {"id": "ocd-jurisdiction/country:us/state:co/place:denver/government",
             "name": "Denver city", "geoid": 820000},  # integer, missing leading zero
        ]
        lookup = _build_local_lookup(jurisdictions)
        assert "0820000" not in lookup  # int geoid loses leading zero — not matched
        assert "820000" in lookup       # it gets stored as "820000" instead


class TestEnrichLocalFeature:
    def _lookup(self):
        return {
            "0820000": {
                "ocdid": "ocd-division/country:us/state:co/place:denver",
                "name": "Denver city",
            }
        }

    def _feature(self, geoid="0820000"):
        return {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[]]},
            "properties": {"GEOID": geoid, "NAME": "Denver", "ALAND": 12345},
        }

    def test_matched_feature_has_correct_properties(self):
        result = _enrich_local_feature(self._feature(), self._lookup())
        assert result is not None
        assert result["properties"]["jurisdiction_ocdid"] == "ocd-division/country:us/state:co/place:denver"
        assert result["properties"]["geoid"] == "0820000"
        assert result["properties"]["name"] == "Denver city"

    def test_matched_feature_strips_census_properties(self):
        result = _enrich_local_feature(self._feature(), self._lookup())
        assert "ALAND" not in result["properties"]
        assert set(result["properties"].keys()) == {"jurisdiction_ocdid", "geoid", "name"}

    def test_unmatched_feature_returns_none(self):
        result = _enrich_local_feature(self._feature("9999999"), self._lookup())
        assert result is None

    def test_handles_lowercase_geoid_key(self):
        feature = {
            "type": "Feature",
            "geometry": {},
            "properties": {"geoid": "0820000"},
        }
        result = _enrich_local_feature(feature, self._lookup())
        assert result is not None


class TestRunTippecanoe:
    def test_calls_tippecanoe_with_correct_args(self, tmp_path):
        from scripts.generate_pmtiles import _run_tippecanoe
        geojson = tmp_path / "input.geojson"
        output = tmp_path / "output.pmtiles"
        geojson.write_text("{}")

        with patch("scripts.generate_pmtiles.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            _run_tippecanoe(geojson, output, "jurisdictions")

        args = mock_run.call_args[0][0]
        assert args[0] == "tippecanoe"
        assert "-o" in args
        assert str(output) in args
        assert "--layer" in args
        assert "jurisdictions" in args
        assert str(geojson) in args


class TestUploadToR2:
    def test_uploads_and_returns_cdn_url(self, tmp_path):
        from scripts.generate_pmtiles import _upload_to_r2
        pmtiles = tmp_path / "co.pmtiles"
        pmtiles.write_bytes(b"fake")

        env = {
            "STORAGE_ENDPOINT": "https://endpoint.example.com",
            "STORAGE_ACCESS_KEY_ID": "key",
            "STORAGE_SECRET_ACCESS_KEY": "secret",
            "FRIENDLY_STORAGE_HOST": "https://cdn.civicpatch.org",
        }
        with patch.dict("os.environ", env), \
             patch("scripts.generate_pmtiles.boto3.client") as mock_boto:
            mock_s3 = MagicMock()
            mock_boto.return_value = mock_s3

            url = _upload_to_r2(pmtiles, "maps/co.pmtiles")

        assert url == "https://cdn.civicpatch.org/maps/co.pmtiles"
        mock_s3.upload_file.assert_called_once_with(
            str(pmtiles),
            "civicpatch",
            "maps/co.pmtiles",
            ExtraArgs={"ContentType": "application/octet-stream"},
        )
