from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.generate_pmtiles import (
    _build_county_lookup,
    _build_state_lookup,
    _build_local_lookup,
    _enrich_state_feature,
    _enrich_county_feature,
    _enrich_local_feature,
)


class TestBuildStateLookup:
    def test_returns_geoid_to_ocdid_mapping(self):
        lookup = _build_state_lookup("co")
        assert lookup["08"] == "ocd-jurisdiction/country:us/state:co/government"

    def test_all_active_states(self):
        expected = {
            "co": "08",
            "mi": "26",
            "nj": "34",
            "sc": "45",
            "tx": "48",
            "wa": "53",
        }
        for state, geoid in expected.items():
            lookup = _build_state_lookup(state)
            assert geoid in lookup, f"{state} missing geoid {geoid}"


class TestBuildCountyLookup:
    def test_returns_geoid_to_ocdid_mapping(self):
        lookup = _build_county_lookup("co")
        # Adams County CO GEOID is 08001
        assert "08001" in lookup
        assert lookup["08001"].startswith("ocd-jurisdiction/country:us/state:co/county:")

    def test_ocdid_format_is_jurisdiction(self):
        lookup = _build_county_lookup("co")
        for ocdid in lookup.values():
            assert ocdid.startswith("ocd-jurisdiction/"), f"expected ocd-jurisdiction, got: {ocdid}"
            assert ocdid.endswith("/government"), f"expected /government suffix, got: {ocdid}"


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

    def _lookup(self):
        return {"08": "ocd-jurisdiction/country:us/state:co/government"}

    def test_sets_jurisdiction_ocdid_from_lookup(self):
        result = _enrich_state_feature(self._feature(), self._lookup())
        assert result["properties"]["jurisdiction_ocdid"] == "ocd-jurisdiction/country:us/state:co/government"

    def test_sets_geoid(self):
        result = _enrich_state_feature(self._feature(), self._lookup())
        assert result["properties"]["geoid"] == "08"

    def test_sets_name(self):
        result = _enrich_state_feature(self._feature(), self._lookup())
        assert result["properties"]["name"] == "Colorado"

    def test_sets_code(self):
        result = _enrich_state_feature(self._feature(), self._lookup())
        assert result["properties"]["code"] == "co"

    def test_strips_census_properties(self):
        result = _enrich_state_feature(self._feature(), self._lookup())
        assert "STATEFP" not in result["properties"]
        assert "ALAND" not in result["properties"]
        assert set(result["properties"].keys()) == {"jurisdiction_ocdid", "geoid", "name", "code"}

    def test_empty_string_when_geoid_not_in_lookup(self):
        result = _enrich_state_feature(self._feature(), {})
        assert result["properties"]["jurisdiction_ocdid"] == ""


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

    def _lookup(self):
        return {"08001": "ocd-jurisdiction/country:us/state:co/county:adams/government"}

    def test_sets_jurisdiction_ocdid_from_lookup(self):
        result = _enrich_county_feature(self._feature(), self._lookup())
        assert result["properties"]["jurisdiction_ocdid"] == "ocd-jurisdiction/country:us/state:co/county:adams/government"

    def test_sets_geoid(self):
        result = _enrich_county_feature(self._feature(), self._lookup())
        assert result["properties"]["geoid"] == "08001"

    def test_sets_name_from_namelsad(self):
        result = _enrich_county_feature(self._feature(), self._lookup())
        assert result["properties"]["name"] == "Adams County"

    def test_strips_census_properties(self):
        result = _enrich_county_feature(self._feature(), self._lookup())
        assert "STATEFP" not in result["properties"]
        assert set(result["properties"].keys()) == {"jurisdiction_ocdid", "geoid", "name"}

    def test_empty_string_when_geoid_not_in_lookup(self):
        result = _enrich_county_feature(self._feature(), {})
        assert result["properties"]["jurisdiction_ocdid"] == ""


class TestBuildLocalLookup:
    def test_maps_geoid_to_ocdid_and_name(self):
        jurisdictions = [
            {"id": "ocd-jurisdiction/country:us/state:co/place:denver/government",
             "name": "Denver city", "geoid": "0820000"},
        ]
        lookup = _build_local_lookup(jurisdictions)
        assert lookup["0820000"]["ocdid"] == "ocd-jurisdiction/country:us/state:co/place:denver/government"
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
                "ocdid": "ocd-jurisdiction/country:us/state:co/place:denver/government",
                "name": "Denver city",
            }
        }

    def _feature(self, geoid="0820000", parent_ocdids=None):
        props = {"GEOID": geoid, "NAME": "Denver", "ALAND": 12345}
        if parent_ocdids is not None:
            props["parent_ocdids"] = parent_ocdids
        return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[]]}, "properties": props}

    def test_matched_feature_has_correct_properties(self):
        result = _enrich_local_feature(self._feature(), self._lookup())
        assert result is not None
        assert result["properties"]["jurisdiction_ocdid"] == "ocd-jurisdiction/country:us/state:co/place:denver/government"
        assert result["properties"]["geoid"] == "0820000"
        assert result["properties"]["name"] == "Denver city"
        assert result["properties"]["parent_ocdids"] == []

    def test_passes_through_parent_ocdids(self):
        parents = ["ocd-jurisdiction/country:us/state:co/county:denver/government"]
        result = _enrich_local_feature(self._feature(parent_ocdids=parents), self._lookup())
        assert result is not None
        assert result["properties"]["parent_ocdids"] == parents

    def test_matched_feature_strips_census_properties(self):
        result = _enrich_local_feature(self._feature(), self._lookup())
        assert "ALAND" not in result["properties"]
        assert set(result["properties"].keys()) == {"jurisdiction_ocdid", "geoid", "name", "parent_ocdids"}

    def test_unmatched_feature_returns_none(self):
        result = _enrich_local_feature(self._feature("9999999"), self._lookup())
        assert result is None

    def test_handles_lowercase_geoid_key(self):
        feature = {"type": "Feature", "geometry": {}, "properties": {"geoid": "0820000"}}
        result = _enrich_local_feature(feature, self._lookup())
        assert result is not None


class TestRunTippecanoe:
    def test_calls_tippecanoe_with_named_layers(self, tmp_path):
        from scripts.generate_pmtiles import _run_tippecanoe
        states = tmp_path / "states.geojson"
        counties = tmp_path / "counties.geojson"
        output = tmp_path / "co.pmtiles"
        states.write_text("{}")
        counties.write_text("{}")

        mock_proc = MagicMock()
        mock_proc.stderr = iter(["94.1%  14/3702/6902\n"])
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0

        with patch("scripts.generate_pmtiles.subprocess.Popen") as mock_popen:
            mock_popen.return_value = mock_proc
            _run_tippecanoe(
                [("states", states, 0), ("counties", counties, 5)],
                output,
                label="co",
            )

        args = mock_popen.call_args[0][0]
        assert args[0] == "tippecanoe"
        assert "-o" in args
        assert str(output) in args
        assert "--no-feature-limit" in args
        assert "--drop-densest-as-needed" not in args
        full_cmd = " ".join(args)
        assert '"layer": "states"' in full_cmd
        assert '"layer": "counties"' in full_cmd
        assert '"minzoom": 0' in full_cmd
        assert '"minzoom": 5' in full_cmd


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
