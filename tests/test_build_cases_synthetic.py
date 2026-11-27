"""End-to-end test of build_cases.py on a tiny hand-made FHIR folder.

It checks the parts that are easy to get wrong: time windows, calculated MAP,
GCS total, urine output per kg, drip titration, line day counts and lab flags.
No real data needed, so it runs in CI.
"""
import gzip
import json

import pytest

from etl import build_cases, config

BASE = "http://mimic.mit.edu/fhir/mimic"


def obs(rid, pid, item, when, value, unit=None, **extra):
    res = {"resourceType": "Observation", "id": rid, "status": "final",
           "subject": {"reference": f"Patient/{pid}"},
           "code": {"coding": [{"system": f"{BASE}/CodeSystem/mimic-chartevents-d-items", "code": str(item)}]},
           "effectiveDateTime": when, "valueQuantity": {"value": value, "unit": unit}}
    res.update(extra)
    return res


def write(folder, stem, rows):
    with gzip.open(folder / f"Mimic{stem}.ndjson.gz", "wt", encoding="utf-8") as handle:
        handle.write("\n".join(json.dumps(r) for r in rows) + "\n")


@pytest.fixture()
def built(tmp_path):
    fhir = tmp_path / "fhir"
    fhir.mkdir()
    write(fhir, "Patient", [
        {"resourceType": "Patient", "id": "p1", "gender": "female", "birthDate": "2080-03-01",
         "identifier": [{"system": f"{BASE}/identifier/patient", "value": "100"}]},
        {"resourceType": "Patient", "id": "p2", "gender": "male", "birthDate": "2070-01-01",
         "identifier": [{"system": f"{BASE}/identifier/patient", "value": "101"}]}])
    write(fhir, "Encounter", [
        {"resourceType": "Encounter", "id": "h1", "class": {"code": "EW EMER."},
         "identifier": [{"system": f"{BASE}/identifier/encounter-hosp", "value": "200"}],
         "subject": {"reference": "Patient/p1"},
         "period": {"start": "2150-01-01T08:00:00-05:00", "end": "2150-01-10T08:00:00-05:00"}}])
    write(fhir, "EncounterICU", [
        {"resourceType": "Encounter", "id": "i1",
         "identifier": [{"system": f"{BASE}/identifier/encounter-icu", "value": "300"}],
         "subject": {"reference": "Patient/p1"}, "partOf": {"reference": "Encounter/h1"},
         "period": {"start": "2150-01-02T10:00:00-05:00", "end": "2150-01-06T10:00:00-05:00"},
         "location": [{"location": {"reference": "Location/l1"}}]}])
    write(fhir, "Location", [{"resourceType": "Location", "id": "l1", "name": "Medical Intensive Care Unit (MICU)"}])
    write(fhir, "ObservationChartevents", [
        obs("hr-old", "p1", 220045, "2150-01-02T10:00:00-05:00", 130, "bpm"),   # before the 24 h lookback
        obs("hr1", "p1", 220045, "2150-01-03T18:00:00-05:00", 88, "bpm"),
        obs("sbp", "p1", 220179, "2150-01-03T18:00:00-05:00", 100, "mmHg"),
        obs("dbp", "p1", 220180, "2150-01-03T18:00:00-05:00", 50, "mmHg"),
        obs("eye", "p1", 220739, "2150-01-03T16:00:00-05:00", 4),
        obs("verbal", "p1", 223900, "2150-01-03T16:00:00-05:00", 5),
        obs("motor", "p1", 223901, "2150-01-03T16:00:00-05:00", 6),
        obs("goal", "p1", 228299, "2150-01-03T08:00:00-05:00", 2),             # stored without its minus sign
        obs("wt", "p1", 226512, "2150-01-02T11:00:00-05:00", 80, "kg"),        # outside 24 h, inside the admission
        obs("other", "p2", 220045, "2150-01-03T18:00:00-05:00", 60, "bpm")])   # another patient
    write(fhir, "ObservationOutputevents", [
        obs("uo-12h", "p1", 226559, "2150-01-03T07:00:00-05:00", 50, "ml"),   # charted at the 12 h edge: hour before
        obs("uo-6h", "p1", 226559, "2150-01-03T13:00:00-05:00", 400, "ml"),   # charted at the 6 h edge: hour before
        obs("uo1", "p1", 226559, "2150-01-03T15:00:00-05:00", 200, "ml"),
        obs("uo2", "p1", 226559, "2150-01-03T18:00:00-05:00", 100, "ml")])
    write(fhir, "ObservationLabevents", [
        obs("k", "p1", 50971, "2150-01-03T04:00:00-05:00", 5.6, "mEq/L",
            interpretation=[{"coding": [{"code": "abnormal"}]}],
            referenceRange=[{"low": {"value": 3.3}, "high": {"value": 5.1}}])])
    drip = {"coding": [{"code": "01-Drips"}]}
    write(fhir, "MedicationAdministrationICU", [
        {"resourceType": "MedicationAdministration", "id": "ne1", "status": "completed", "category": drip,
         "subject": {"reference": "Patient/p1"},
         "medicationCodeableConcept": {"coding": [{"code": "221906", "display": "Norepinephrine"}]},
         "effectivePeriod": {"start": "2150-01-03T05:00:00-05:00", "end": "2150-01-03T12:00:00-05:00"},
         "dosage": {"rateQuantity": {"value": 0.05, "unit": "mcg/kg/min"}, "dose": {"value": 1, "unit": "mg"}}},
        {"resourceType": "MedicationAdministration", "id": "ne2", "status": "completed", "category": drip,
         "subject": {"reference": "Patient/p1"},
         "medicationCodeableConcept": {"coding": [{"code": "221906", "display": "Norepinephrine"}]},
         "effectivePeriod": {"start": "2150-01-03T12:00:00-05:00", "end": "2150-01-04T02:00:00-05:00"},
         "dosage": {"rateQuantity": {"value": 0.1, "unit": "mcg/kg/min"}, "dose": {"value": 2, "unit": "mg"}}},
        {"resourceType": "MedicationAdministration", "id": "ns", "status": "completed",
         "category": {"coding": [{"code": "03-IV Fluid Bolus"}]}, "subject": {"reference": "Patient/p1"},
         "medicationCodeableConcept": {"coding": [{"code": "225158", "display": "NaCl 0.9%"}]},
         "effectiveDateTime": "2150-01-03T14:00:00-05:00", "dosage": {"dose": {"value": 500, "unit": "ml"}}}])
    write(fhir, "ProcedureICU", [
        {"resourceType": "Procedure", "id": "aline", "status": "completed", "subject": {"reference": "Patient/p1"},
         "code": {"coding": [{"code": "225752", "display": "Arterial Line"}]},
         "performedPeriod": {"start": "2150-01-02T12:00:00-05:00", "end": "2150-01-05T12:00:00-05:00"}}])
    write(fhir, "Condition", [
        {"resourceType": "Condition", "id": "dx", "encounter": {"reference": "Encounter/h1"},
         "subject": {"reference": "Patient/p1"},
         "identifier": [{"system": f"{BASE}/identifier/condition", "value": "200-1-A419"}],
         "code": {"coding": [{"system": f"{BASE}/CodeSystem/mimic-diagnosis-icd10", "code": "A419",
                              "display": "Sepsis, unspecified organism"}]}}])

    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps({"cases": [{"case_id": "S1", "complexity": "standard", "subject_id": 100,
                                            "hadm_id": 200, "stay_id": 300,
                                            "handoff_time": "2150-01-03T19:00:00"}]}))
    out = tmp_path / "out"
    assert build_cases.main(["--fhir-dir", str(fhir), "--cases", str(cases), "--out-dir", str(out),
                             "--elements", str(config.DATA_ELEMENTS_FILE)]) == 0
    return json.loads((out / "case_S1.json").read_text())


def test_stay_and_patient(built):
    assert built["stay"]["careunit"] == "Medical Intensive Care Unit (MICU)"
    assert built["stay"]["icu_day"] == 2
    assert built["stay"]["hadm_id"] == "200"
    assert built["patient"]["age_at_handoff"] == 69
    assert built["diagnoses"][0]["seq"] == 1 and built["diagnoses"][0]["version"] == "ICD-10"


def test_window_and_other_patients_excluded(built):
    hr = built["elements"]["heart_rate"]
    assert hr["latest"]["value"] == 88 and hr["n_12h"] == 1
    assert all(o["fhir_id"] != "other" for o in built["observations"])


def test_calculated_values(built):
    el = built["elements"]
    assert el["map"]["latest"]["value"] == pytest.approx(66.7)
    assert el["map"]["abnormal"] is False
    assert el["gcs_total"]["latest"]["value"] == 15
    assert el["rass_goal"]["latest"]["value"] == -2
    assert el["weight"]["latest"]["value"] == 80
    assert el["urine_output_6h"]["latest"]["value"] == 300
    assert el["urine_rate_6h"]["latest"]["value"] == pytest.approx(0.625, abs=0.01)
    assert el["intake_12h"]["latest"]["value"] == 500
    assert el["output_12h"]["latest"]["value"] == 700     # 400 + 200 + 100; the 07:00 entry is the hour before
    assert el["net_12h"]["latest"]["value"] == -200


def test_output_windows_are_open_at_their_start(built):
    """An output entry covers the time since the previous one, so one charted exactly at a window's start
    belongs to the hour before it. 6 h of hourly charting is 6 entries, not 7."""
    assert built["elements"]["urine_output_6h"]["latest"]["value"] == 300   # 15:00 and 18:00, not the 13:00 entry
    uo = next(o for o in built["observations"] if o["item_id"] == "UO_6H")
    assert uo["note"].startswith("2 urine entries")


def test_drip_titration_and_lines(built):
    running = built["elements"]["vasoactive_drips"]["running"]
    assert len(running) == 1
    assert running[0]["rate"] == 0.1 and running[0]["since"] == "2150-01-03T12:00:00"
    assert running[0]["rate_12h_ago"] == 0.05
    lines = built["elements"]["lines"]["in_place"]
    assert lines[0]["label"] == "Arterial line" and lines[0]["day"] == 2


def test_lab_flag_and_unmapped_element(built):
    k = built["elements"]["potassium"]
    assert k["abnormal"] is True and "reference" in k["abnormal_reason"]
    assert built["elements"]["allergies"]["mappable"] is False
