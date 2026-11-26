"""Unit tests for the FHIR helpers. These need no data and run in CI."""
import gzip
import json
from datetime import datetime

from etl.fhir_io import (find_resource_file, identifier_value, iter_ndjson,
                         observation_value, parse_time, ref_id)


def test_times_keep_boston_wall_clock_in_summer_and_winter():
    assert parse_time("2156-05-02T02:00:00-04:00") == datetime(2156, 5, 2, 2, 0)
    assert parse_time("2120-01-30T22:51:00-05:00") == datetime(2120, 1, 30, 22, 51)


def test_other_offsets_are_converted_back_to_boston_time():
    # 06:00 UTC on 2 May is 02:00 in Boston (daylight time)
    assert parse_time("2156-05-02T06:00:00Z") == datetime(2156, 5, 2, 2, 0)
    assert parse_time("2156-05-02T16:00:00+10:00") == datetime(2156, 5, 2, 2, 0)


def test_dates_and_bad_values():
    assert parse_time("2075-07-14") == datetime(2075, 7, 14)
    assert parse_time("2150-05") is None
    assert parse_time(None) is None


def test_find_resource_file_accepts_physionet_and_plain_names(tmp_path):
    (tmp_path / "MimicPatient.ndjson.gz").write_bytes(b"")
    (tmp_path / "ObservationChartevents.ndjson").write_text("")
    assert find_resource_file(tmp_path, "Patient").name == "MimicPatient.ndjson.gz"
    assert find_resource_file(tmp_path, "ObservationChartevents").name == "ObservationChartevents.ndjson"
    assert find_resource_file(tmp_path, "Condition") is None


def test_identifier_matching_ignores_the_url_base():
    old = {"identifier": [{"system": "http://fhir.mimic.mit.edu/identifier/encounter-icu", "value": "1"}]}
    new = {"identifier": [{"system": "http://mimic.mit.edu/fhir/mimic/identifier/encounter-icu", "value": "2"}]}
    hosp = {"identifier": [{"system": "http://mimic.mit.edu/fhir/mimic/identifier/encounter-hosp", "value": "3"}]}
    assert identifier_value(old, "encounter-icu") == "1"
    assert identifier_value(new, "encounter-icu") == "2"
    assert identifier_value(hosp, "encounter-icu") is None
    assert identifier_value(hosp, "encounter-hosp", "identifier/encounter") == "3"


def test_observation_values():
    assert observation_value({"valueQuantity": {"value": 98.1, "unit": "°F"}}) == (98.1, None, "°F")
    assert observation_value({"valueString": "Dry "}) == (None, "Dry", None)
    assert observation_value({"valueString": "7"}) == (7.0, "7", None)
    assert observation_value({}) == (None, None, None)


def test_ref_id():
    assert ref_id({"reference": "Encounter/abc"}) == "abc"
    assert ref_id(None) is None


def test_iter_ndjson_prefilter(tmp_path):
    path = tmp_path / "MimicObservationChartevents.ndjson.gz"
    rows = [{"id": "1", "subject": {"reference": "Patient/a"}},
            {"id": "2", "subject": {"reference": "Patient/b"}}]
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write("\n".join(json.dumps(r) for r in rows) + "\n")
    assert [r["id"] for r in iter_ndjson(path)] == ["1", "2"]
    assert [r["id"] for r in iter_ndjson(path, contains=["Patient/b"])] == ["2"]
