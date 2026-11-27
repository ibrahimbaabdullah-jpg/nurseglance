#!/usr/bin/env python3
"""Build one JSON file per handoff case from the MIMIC-IV Clinical Database Demo on FHIR.

    python etl/build_cases.py --fhir-dir data/raw/physionet.org/files/mimic-iv-fhir-demo/2.1.0/fhir

Reads etl/cases.json (from select_cases.py, after your review) and
docs/data_elements.csv. Writes data/processed/case_<case_id>.json.

Every value keeps the id of the FHIR resource it came from, so the app can show
its source. All times are MIMIC's date-shifted local (Boston) wall-clock times.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

if __package__ in (None, ""):  # allow "python etl/build_cases.py"
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from etl import config  # noqa: E402
from etl.fhir_io import (RESOURCE_FILES, find_resource_file, first_coding,  # noqa: E402
                         identifier_value, iso, iter_ndjson, lab_flag_and_range,
                         observation_value, parse_time, period_of, quantity, ref_id)

SKIP_STATUSES = {"entered-in-error", "not-done"}
WEIGHT_IDS = {str(i) for i in config.WEIGHT_ITEMS}
URINE_IDS = {str(i) for i in config.URINE_ITEMS}
IRRIGANT_IN = str(config.GU_IRRIGANT_IN)
NON_VOLUME_OUTPUT = {str(i) for i in config.NON_VOLUME_OUTPUT_ITEMS}
DEVICE_IDS = {str(i): label for i, label in config.DEVICE_ITEMS.items()}
BRADEN_IDS = ("224054", "224055", "224056", "224057", "224058", "224059")
# Morse Fall Scale items; MIMIC stores each item's points in valuenum (history 25, IV 20, ...).
MORSE_IDS = ("227341", "227342", "227343", "227344", "227345", "227346")
NEGATE_IDS = {str(i) for i in config.NEGATE_ITEMS}


def load_value_codes(path: Path = config.VALUE_CODES_FILE) -> dict[tuple[str, float], str]:
    """(item_id, numeric code) -> charted text, from docs/value_codes.csv."""
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as handle:
        return {(row["itemid"], float(row["code"])): row["text"] for row in csv.DictReader(handle)}


VALUE_CODES = load_value_codes()
CARRIER_IDS = {str(i) for i in config.CARRIER_FLUIDS}
OBSERVATION_SOURCES = {"chart": "chartevents", "lab": "labevents", "output": "outputevents"}


@dataclass
class Case:
    spec: dict
    handoff: datetime
    lookback_start: datetime
    trend_start: datetime
    lab_start: datetime
    lookahead_end: datetime
    patient: dict | None = None
    icu_encounter: dict | None = None
    hospital_encounter: dict | None = None
    careunit: str | None = None
    observations: list = field(default_factory=list)
    weights: list = field(default_factory=list)
    infusions: list = field(default_factory=list)
    med_admins: list = field(default_factory=list)
    med_orders: list = field(default_factory=list)
    devices: list = field(default_factory=list)
    diagnoses: list = field(default_factory=list)
    admission: dict = field(default_factory=dict)

    @property
    def case_id(self) -> str:
        return self.spec["case_id"]

    @property
    def patient_id(self) -> str | None:
        return self.patient["id"] if self.patient else None

    @property
    def hospital_id(self) -> str | None:
        return ref_id((self.icu_encounter or {}).get("partOf"))

    @property
    def weight_start(self) -> datetime:
        start = period_of(self.hospital_encounter or {}, "period")[0]
        return start or self.lookback_start - timedelta(days=7)


# ---------------------------------------------------------------- loading

def load_cases(path: Path) -> list[Case]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    hours = {key: data.get(key, getattr(config, key.upper()))
             for key in ("lookback_hours", "trend_hours", "lab_lookback_hours", "lookahead_hours")}
    cases = []
    for spec in data["cases"]:
        handoff = datetime.fromisoformat(spec["handoff_time"])
        cases.append(Case(
            spec=spec, handoff=handoff,
            lookback_start=handoff - timedelta(hours=hours["lookback_hours"]),
            trend_start=handoff - timedelta(hours=hours["trend_hours"]),
            lab_start=handoff - timedelta(hours=hours["lab_lookback_hours"]),
            lookahead_end=handoff + timedelta(hours=hours["lookahead_hours"]),
        ))
    return cases


def load_elements(path: Path) -> list[dict]:
    if not Path(path).exists():
        return []
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["ids"] = [x.strip() for x in (row.get("item_ids") or "").split("|") if x.strip()]
        for key in ("low", "high"):
            row[key] = float(row[key]) if (row.get(key) or "").strip() else None
    return rows


def resource_path(fhir_dir: Path, key: str, required: bool = True) -> Path | None:
    path = find_resource_file(fhir_dir, RESOURCE_FILES[key])
    if path is None and required:
        raise SystemExit(f"Missing Mimic{RESOURCE_FILES[key]}.ndjson(.gz) in {fhir_dir}")
    return path


def attach_encounters(fhir_dir: Path, cases: list[Case]) -> None:
    by_subject, by_stay = defaultdict(list), defaultdict(list)
    for case in cases:
        by_subject[str(case.spec["subject_id"])].append(case)
        by_stay[str(case.spec["stay_id"])].append(case)

    for res in iter_ndjson(resource_path(fhir_dir, "patient")):
        for case in by_subject.get(identifier_value(res, "identifier/patient"), []):
            case.patient = res
    for res in iter_ndjson(resource_path(fhir_dir, "encounter_icu")):
        for case in by_stay.get(identifier_value(res, "encounter-icu"), []):
            case.icu_encounter = res

    hospital_ids = {c.hospital_id for c in cases if c.hospital_id}
    if hospital_ids:
        for res in iter_ndjson(resource_path(fhir_dir, "encounter"), contains=hospital_ids):
            for case in cases:
                if case.hospital_id == res.get("id"):
                    case.hospital_encounter = res

    location_ids = {ref_id(loc.get("location")) for c in cases
                    for loc in (c.icu_encounter or {}).get("location", [])}
    location_ids.discard(None)
    names = {}
    path = resource_path(fhir_dir, "location", required=False)
    if path and location_ids:
        names = {r["id"]: r.get("name") for r in iter_ndjson(path, contains=location_ids)}
    for case in cases:
        locations = (case.icu_encounter or {}).get("location", [])
        if locations:
            case.careunit = names.get(ref_id(locations[0].get("location")))


# ---------------------------------------------------------------- streaming

def read_observations(path: Path, source: str, by_patient: dict, needles: list[str]) -> None:
    for res in iter_ndjson(path, contains=needles):
        if res.get("status") in SKIP_STATUSES:
            continue
        for case in by_patient.get(ref_id(res.get("subject")), []):
            moment = parse_time(res.get("effectiveDateTime")) or period_of(res, "effectivePeriod")[0]
            if moment is None or moment > case.handoff:
                continue
            coding = first_coding(res.get("code"))
            item = coding.get("code")
            number, text, unit = observation_value(res)
            if source == "chartevents" and item in WEIGHT_IDS and moment >= case.weight_start and number:
                case.weights.append({"t": iso(moment), "item_id": item, "label": coding.get("display"),
                                     "value": number, "unit": unit, "fhir_id": res.get("id")})
            start = case.lab_start if source == "labevents" else case.lookback_start
            if moment < start:
                continue
            categories = res.get("category") or [{}]
            obs = {"t": iso(moment), "source": source, "item_id": item, "label": coding.get("display"),
                   "category": first_coding(categories[0]).get("code"),
                   "value": number, "value_text": text, "unit": unit, "fhir_id": res.get("id")}
            if text is None and number is not None and (item, float(number)) in VALUE_CODES:
                obs["value_text"] = VALUE_CODES[(item, float(number))]
                obs["note"] = "FHIR carries MIMIC's numeric code; text restored from docs/value_codes.csv"
            if item in NEGATE_IDS and number is not None:
                obs["value"] = -abs(number)
                obs["note"] = "MIMIC stores this goal without its minus sign; sign restored"
            if source == "labevents":
                flag, low, high = lab_flag_and_range(res)
                obs.update(flag=flag, ref_low=low, ref_high=high)
            case.observations.append(obs)


def read_infusions(path: Path, by_patient: dict, needles: list[str]) -> None:
    for res in iter_ndjson(path, contains=needles):
        if res.get("status") in SKIP_STATUSES:
            continue
        for case in by_patient.get(ref_id(res.get("subject")), []):
            start, end = period_of(res, "effectivePeriod")
            if start is None:
                start = end = parse_time(res.get("effectiveDateTime"))
            if start is None:
                continue
            end = end or start
            if end < case.lookback_start or start > case.lookahead_end:
                continue
            coding = first_coding(res.get("medicationCodeableConcept"))
            dosage = res.get("dosage") or {}
            dose, dose_unit = quantity(dosage.get("dose"))
            rate, rate_unit = quantity(dosage.get("rateQuantity"))
            case.infusions.append({
                "start": iso(start), "end": iso(end), "item_id": coding.get("code"),
                "label": coding.get("display"), "category": first_coding(res.get("category")).get("code"),
                "method": first_coding(dosage.get("method")).get("code"),
                "dose": dose, "dose_unit": dose_unit, "rate": rate, "rate_unit": rate_unit,
                "running_at_handoff": start <= case.handoff < end, "fhir_id": res.get("id")})


def read_devices(path: Path, by_patient: dict, needles: list[str]) -> None:
    for res in iter_ndjson(path, contains=needles):
        if res.get("status") in SKIP_STATUSES:
            continue
        for case in by_patient.get(ref_id(res.get("subject")), []):
            start, end = period_of(res, "performedPeriod")
            if start is None:
                start = end = parse_time(res.get("performedDateTime"))
            if start is None:
                continue
            end = end or start
            if start > case.lookahead_end or end < case.lookback_start:
                continue
            coding = first_coding(res.get("code"))
            in_place = start <= case.handoff <= end
            sites = res.get("bodySite") or []
            case.devices.append({
                "item_id": coding.get("code"),
                "label": DEVICE_IDS.get(coding.get("code"), coding.get("display")),
                "category": first_coding(res.get("category")).get("code"),
                "start": iso(start), "end": iso(end), "in_place_at_handoff": in_place,
                "day": (case.handoff.date() - start.date()).days + 1 if in_place else None,
                "site": first_coding(sites[0]).get("code") if sites else None,
                "is_line_or_device": coding.get("code") in DEVICE_IDS,
                "fhir_id": res.get("id")})


def read_orders(path: Path, cases: list[Case]) -> None:
    by_hospital = defaultdict(list)
    for case in cases:
        if case.hospital_id:
            by_hospital[case.hospital_id].append(case)
    for res in iter_ndjson(path, contains=list(by_hospital)):
        for case in by_hospital.get(ref_id(res.get("encounter")), []):
            instruction = (res.get("dosageInstruction") or [{}])[0]
            timing_code = first_coding((instruction.get("timing") or {}).get("code")).get("code")
            dose_rate = (instruction.get("doseAndRate") or [{}])[0]
            dose, dose_unit = quantity(dose_rate.get("doseQuantity"))
            start, end = period_of(res.get("dispenseRequest") or {}, "validityPeriod")
            coding = first_coding(res.get("medicationCodeableConcept"))
            case.med_orders.append({
                "name": coding.get("display") or coding.get("code"),
                "medication_ref": ref_id(res.get("medicationReference")),
                "route": first_coding(instruction.get("route")).get("code"),
                "frequency": timing_code, "instruction": instruction.get("text"),
                "dose": dose, "dose_unit": dose_unit,
                "start": iso(start or parse_time(res.get("authoredOn"))), "end": iso(end),
                "status": res.get("status"), "fhir_id": res.get("id")})


def read_med_admins(path: Path, by_patient: dict, needles: list[str]) -> None:
    for res in iter_ndjson(path, contains=needles):
        for case in by_patient.get(ref_id(res.get("subject")), []):
            moment = parse_time(res.get("effectiveDateTime")) or period_of(res, "effectivePeriod")[0]
            if moment is None or not (case.lookback_start <= moment <= case.lookahead_end):
                continue
            coding = first_coding(res.get("medicationCodeableConcept"))
            system = coding.get("system") or ""
            dosage = res.get("dosage") or {}
            dose, dose_unit = quantity(dosage.get("dose"))
            case.med_admins.append({
                "t": iso(moment),
                "relative": "before_handoff" if moment <= case.handoff else "after_handoff",
                "name": coding.get("display") or (coding.get("code") if system.endswith("medication-name") else None),
                "code": coding.get("code"), "request_id": ref_id(res.get("request")),
                "event": first_coding(dosage.get("method")).get("code"),
                "route": first_coding(dosage.get("route")).get("code"),
                "dose": dose, "dose_unit": dose_unit, "status": res.get("status"),
                "fhir_id": res.get("id")})


def read_conditions(path: Path, cases: list[Case]) -> None:
    by_hospital = defaultdict(list)
    for case in cases:
        if case.hospital_id:
            by_hospital[case.hospital_id].append(case)
    for res in iter_ndjson(path, contains=list(by_hospital)):
        for case in by_hospital.get(ref_id(res.get("encounter")), []):
            coding = first_coding(res.get("code"))
            system = coding.get("system") or ""
            seq = None
            ident = identifier_value(res, "identifier/condition") or ""
            parts = ident.split("-", 2)  # "<hadm_id>-<seq_num>-<icd_code>"
            if len(parts) == 3 and parts[1].isdigit():
                seq = int(parts[1])
            case.diagnoses.append({
                "seq": seq, "code": coding.get("code"), "display": coding.get("display"),
                "version": "ICD-10" if "icd10" in system else ("ICD-9" if "icd9" in system else None),
                "fhir_id": res.get("id")})


CHIEF_COMPLAINT_LOINC = "8661-1"


def read_ed(fhir_dir: Path, cases: list[Case]) -> list[str]:
    """Chief complaint and home medications from the ED visit that led to this admission.

    MIMIC-IV-ED is linked to the hospital admission through EncounterED.partOf. The
    chief complaint is an ObservationED coded LOINC 8661-1; home medications are the
    ED medication reconciliation (MedicationStatementED). Admissions that did not
    come through the ED have neither. Returns the file names read.
    """
    enc_path = resource_path(fhir_dir, "encounter_ed", required=False)
    if enc_path is None:
        return []
    by_hospital = defaultdict(list)
    for case in cases:
        case.admission = {"ed_encounter_fhir_id": None, "chief_complaint": None, "home_meds": []}
        if case.hospital_id:
            by_hospital[case.hospital_id].append(case)
    by_ed: dict[str, list[Case]] = defaultdict(list)
    for res in iter_ndjson(enc_path, contains=list(by_hospital)):
        for case in by_hospital.get(ref_id(res.get("partOf")), []):
            case.admission["ed_encounter_fhir_id"] = res.get("id")
            by_ed[res.get("id")].append(case)
    used = [enc_path.name]
    if not by_ed:
        return used
    obs_path = resource_path(fhir_dir, "observation_ed", required=False)
    if obs_path is not None:
        used.append(obs_path.name)
        for res in iter_ndjson(obs_path, contains=list(by_ed)):
            if first_coding(res.get("code")).get("code") != CHIEF_COMPLAINT_LOINC or not res.get("valueString"):
                continue
            for case in by_ed.get(ref_id(res.get("encounter")), []):
                case.admission["chief_complaint"] = {
                    "text": res["valueString"], "t": iso(parse_time(res.get("effectiveDateTime"))),
                    "loinc": CHIEF_COMPLAINT_LOINC, "fhir_id": res.get("id")}
    med_path = resource_path(fhir_dir, "med_statement_ed", required=False)
    if med_path is not None:
        used.append(med_path.name)
        for res in iter_ndjson(med_path, contains=list(by_ed)):
            name = (res.get("medicationCodeableConcept") or {}).get("text")
            for case in by_ed.get(ref_id(res.get("context")), []):
                if name:
                    case.admission["home_meds"].append({
                        "name": name, "t": iso(parse_time(res.get("dateAsserted"))), "fhir_id": res.get("id")})
    for case in cases:
        case.admission["home_meds"].sort(key=lambda m: (m["name"].lower(), m["t"] or ""))
    return used


def medication_name(res: dict) -> str | None:
    """Readable drug name. MIMIC keeps it in an identifier whose system ends in
    'medication-name'; the code itself is often an NDC or formulary code."""
    for ident in res.get("identifier") or []:
        if (ident.get("system") or "").rstrip("/").endswith("medication-name") and ident.get("value"):
            return ident["value"]
    coding = first_coding(res.get("code"))
    if coding.get("display"):
        return coding["display"]
    if (coding.get("system") or "").endswith("medication-name") and coding.get("code"):
        return coding["code"]
    return (res.get("code") or {}).get("text")


def resolve_medication_names(fhir_dir: Path, ids: set[str]) -> dict[str, str]:
    """Medication id -> name, including mixtures made of other Medications."""
    files = [p for p in (resource_path(fhir_dir, "medication", required=False),
                         resource_path(fhir_dir, "medication_mix", required=False)) if p]
    names, codes, mixtures, wanted = {}, {}, {}, set(ids)
    for _ in range(2):  # the second pass resolves mixture ingredients
        if not wanted:
            break
        for path in files:
            for res in iter_ndjson(path, contains=wanted):
                if res.get("id") not in wanted:
                    continue
                name = medication_name(res)
                if name:
                    names[res["id"]] = name
                elif res.get("ingredient"):
                    mixtures[res["id"]] = [ref_id(i.get("itemReference")) for i in res["ingredient"]]
                    # e.g. "Alteplase--ALTE50I--50242004413_Soln--FENTSOLN50" -> "Alteplase + Soln"
                    mix_id = identifier_value(res, "medication-mix") or ""
                    codes[res["id"]] = " + ".join(p.split("--")[0] for p in mix_id.split("_") if p) or None
                else:
                    codes[res["id"]] = first_coding(res.get("code")).get("code")
        wanted = {p for parts in mixtures.values() for p in parts if p and p not in names}
    for med_id, parts in mixtures.items():
        resolved = [names[p] for p in parts if p in names]
        if resolved and len(resolved) == len([p for p in parts if p]):
            names[med_id] = " + ".join(resolved)
    for med_id, code in codes.items():
        if code:
            names.setdefault(med_id, code)
    return names


# ---------------------------------------------------------------- derived values

def derived_obs(moment: str, item: str, label: str, value: float | None, unit: str, note: str) -> dict:
    return {"t": moment, "source": "derived", "item_id": item, "label": label, "category": "Derived",
            "value": value, "value_text": None, "unit": unit, "fhir_id": None, "note": note}


def overlap_fraction(start: datetime, end: datetime, a: datetime, b: datetime) -> float:
    """Share of [start, end] that falls in the window (a, b]."""
    if end <= start:  # a single moment, e.g. a bolus; same (a, b] rule as charted output
        return 1.0 if a < start <= b else 0.0
    shared = (min(end, b) - max(start, a)).total_seconds()
    return max(0.0, shared) / (end - start).total_seconds()


def add_derived(case: Case) -> dict:
    by_time = defaultdict(dict)
    for obs in case.observations:
        if obs["value"] is not None:
            by_time[obs["t"]][obs["item_id"]] = obs

    ventilated = any(d["in_place_at_handoff"] and d["item_id"] == str(config.INVASIVE_VENT) for d in case.devices)
    gcs_note = "Eye + verbal + motor charted at the same time"
    if ventilated:
        gcs_note += "; patient ventilated, so verbal 1 likely means 'No Response-ETT' (report as GCS with T)"

    new = []
    for moment, items in by_time.items():
        for site, ids in config.BP_SOURCES.items():
            s, d, m = str(ids["sys"]), str(ids["dia"]), str(ids["mean"])
            if s in items and d in items and m not in items:
                value = round((items[s]["value"] + 2 * items[d]["value"]) / 3, 1)
                new.append(derived_obs(moment, "MAP_CALC", f"MAP (calculated, {site})", value, "mmHg",
                                       "(SBP + 2 x DBP) / 3 where no mean was charted"))
        gcs = [str(i) for i in config.GCS_COMPONENTS.values()]
        if all(g in items for g in gcs):
            new.append(derived_obs(moment, "GCS_TOTAL", "GCS total", sum(items[g]["value"] for g in gcs),
                                   "points", gcs_note))
        if all(b in items for b in BRADEN_IDS):
            new.append(derived_obs(moment, "BRADEN_TOTAL", "Braden score",
                                   sum(items[b]["value"] for b in BRADEN_IDS), "points", "Sum of six subscales"))
        if all(m in items for m in MORSE_IDS):
            new.append(derived_obs(moment, "MORSE_TOTAL", "Morse Fall Scale",
                                   sum(items[m]["value"] for m in MORSE_IDS), "points", "Sum of six items"))
        for item, to_c in (("223762", lambda v: v), ("223761", lambda v: (v - 32) * 5 / 9)):
            if item in items:
                new.append(derived_obs(moment, "TEMP_C", "Temperature", round(to_c(items[item]["value"]), 1),
                                       "deg C", "Converted to Celsius" if item == "223761" else "Charted in Celsius"))

    handoff = case.handoff
    six_h = handoff - timedelta(hours=6)
    def times_in(start):
        # An output entry charted at time t holds what was collected since the previous entry, so a
        # window ending at handoff is (start, handoff]: an entry charted exactly at its start belongs
        # to the hour before. Counting both ends would put 7 hourly entries in 6 hours.
        return [o for o in case.observations if o["source"] == "outputevents" and o["value"] is not None
                and start < datetime.fromisoformat(o["t"]) <= handoff]
    out_6h, out_12h = times_in(six_h), times_in(case.trend_start)
    urine_rows = [o for o in out_6h if o["item_id"] in URINE_IDS]
    urine_6h = sum(o["value"] for o in urine_rows) \
        - sum(o["value"] for o in out_6h if o["item_id"] == IRRIGANT_IN)
    output_rows = [o for o in out_12h if o["item_id"] not in NON_VOLUME_OUTPUT and o["item_id"] != IRRIGANT_IN]
    output_12h = sum(o["value"] for o in output_rows)
    intake_12h = sum(o["value"] for o in out_12h if o["item_id"] == IRRIGANT_IN)
    intake_rows = 0
    for inf in case.infusions:
        if inf["dose"] is not None and (inf["dose_unit"] or "").lower() == "ml":
            frac = overlap_fraction(datetime.fromisoformat(inf["start"]), datetime.fromisoformat(inf["end"]),
                                    case.trend_start, handoff)
            if frac > 0:
                intake_12h += inf["dose"] * frac
                intake_rows += 1

    weight = max(case.weights, key=lambda w: w["t"]) if case.weights else None
    t_handoff = iso(handoff)
    # Totals are added only when something was charted, so "no data" never shows as 0 mL.
    if urine_rows:
        new.append(derived_obs(t_handoff, "UO_6H", "Urine output (last 6 h)", round(urine_6h, 1), "mL",
                               f"{len(urine_rows)} urine entries, minus GU irrigant in"))
        if weight:
            new.append(derived_obs(t_handoff, "UO_RATE_6H", "Urine output rate (last 6 h)",
                                   round(urine_6h / weight["value"] / 6, 2), "mL/kg/h",
                                   f"Uses weight {weight['value']} kg charted {weight['t']}"))
    if intake_rows:
        new.append(derived_obs(t_handoff, "INTAKE_12H", "Intake (last 12 h)", round(intake_12h), "mL",
                               "Approximate: ICU input events in mL, prorated by time"))
    if output_rows:
        new.append(derived_obs(t_handoff, "OUTPUT_12H", "Output (last 12 h)", round(output_12h), "mL",
                               "All output events in mL"))
    if intake_rows or output_rows:
        new.append(derived_obs(t_handoff, "NET_12H", "Net balance (last 12 h)", round(intake_12h - output_12h),
                               "mL", "Intake minus output"))
    case.observations.extend(new)
    case.observations.sort(key=lambda o: (o["t"], o["source"], o["item_id"] or ""))
    return {"weight": weight}


# ---------------------------------------------------------------- data elements

def check_abnormal(value, low, high, obs) -> tuple[bool | None, str | None]:
    if value is None:
        return None, None
    if low is not None or high is not None:
        if low is not None and value < low:
            return True, f"below {low:g}"
        if high is not None and value > high:
            return True, f"above {high:g}"
        return False, None
    ref_low, ref_high = obs.get("ref_low"), obs.get("ref_high")
    if ref_low is not None and value < ref_low:
        return True, f"below reference range ({ref_low:g})"
    if ref_high is not None and value > ref_high:
        return True, f"above reference range ({ref_high:g})"
    if obs.get("flag") == "abnormal":
        return True, "flagged abnormal by the lab"
    if ref_low is None and ref_high is None:
        return None, None
    return False, None


def infusion_matches(inf: dict, ids: list[str]) -> bool:
    for key in ids:
        if key.startswith("cat:"):
            if inf["item_id"] in CARRIER_IDS:
                continue
            if key[4:].lower() in (inf["category"] or "").lower():
                return True
        elif inf["item_id"] == key:
            return True
    return False


def summarize_infusions(case: Case, rows: list[dict]) -> dict:
    """What is running at handoff, which drips stopped in the last 12 h, and
    which other doses (boluses, antibiotics, fluids) were given in the last 12 h.

    MIMIC splits a drip into a new row at every rate change, so "since" is the
    time of the last rate change and rate_12h_ago shows the titration.
    """
    handoff, trend_start = iso(case.handoff), iso(case.trend_start)
    is_drip = lambda i: "drip" in (i["category"] or "").lower()  # noqa: E731 ("01-Drips")
    running = [i for i in rows if i["running_at_handoff"]]
    running_items = {i["item_id"] for i in running}
    stopped = {}
    for i in rows:
        if is_drip(i) and i["item_id"] not in running_items and trend_start <= i["end"] <= handoff:
            if i["item_id"] not in stopped or i["end"] > stopped[i["item_id"]]["end"]:
                stopped[i["item_id"]] = i
    given = [i for i in rows if not is_drip(i) and not i["running_at_handoff"]
             and trend_start <= i["start"] <= handoff]

    def rate_at(item_id, moment):
        for i in rows:
            if i["item_id"] == item_id and i["start"] <= moment < i["end"]:
                return i["rate"]
        return None

    return {
        "has_data": bool(running or stopped or given),
        "running": [{"label": i["label"], "rate": i["rate"], "rate_unit": i["rate_unit"],
                     "since": i["start"], "rate_12h_ago": rate_at(i["item_id"], trend_start),
                     "fhir_id": i["fhir_id"]} for i in running],
        "stopped_12h": [{"label": i["label"], "stopped_at": i["end"], "last_rate": i["rate"],
                         "rate_unit": i["rate_unit"], "fhir_id": i["fhir_id"]} for i in stopped.values()],
        "given_12h": [{"label": i["label"], "t": i["start"], "dose": i["dose"], "dose_unit": i["dose_unit"],
                       "fhir_id": i["fhir_id"]} for i in given],
    }


def summarize_elements(case: Case, elements: list[dict], available: set[str]) -> dict:
    summary = {}
    trend_start = iso(case.trend_start)
    for el in elements:
        src, ids = el["source"], el["ids"]
        entry = {"label": el["label"], "organ_system": el["organ_system"], "source": src,
                 "display_rule": el["display_rule"], "has_data": False}
        if src in OBSERVATION_SOURCES or src == "derived":
            needed = OBSERVATION_SOURCES.get(src, "chartevents")
            entry["mappable"] = needed in available
            # Use the item with the most recent value; ties go to the first listed
            # (for MAP: arterial line, then cuff, then calculated).
            by_item = {item: [o for o in case.observations if o["item_id"] == item] for item in ids}
            ranked = sorted((item for item in ids if by_item[item]),
                            key=lambda item: (by_item[item][-1]["t"], -ids.index(item)), reverse=True)
            for item in ranked[:1]:
                series = by_item[item]
                last = series[-1]
                recent = [o for o in series if o["t"] >= trend_start]
                numbers = [o["value"] for o in recent if o["value"] is not None]
                flag, reason = check_abnormal(last["value"], el["low"], el["high"], last)
                entry.update({
                    "has_data": True, "item_id": item,
                    "latest": {k: last.get(k) for k in ("t", "value", "value_text", "unit", "fhir_id")},
                    "n_12h": len(recent),
                    "min_12h": min(numbers) if numbers else None,
                    "max_12h": max(numbers) if numbers else None,
                    "change_12h": round(numbers[-1] - numbers[0], 2) if len(numbers) > 1 else None,
                    "abnormal": flag, "abnormal_reason": reason,
                    "any_abnormal_12h": any(check_abnormal(o["value"], el["low"], el["high"], o)[0]
                                            for o in recent) if recent else None,
                })
                break
        elif src == "infusion":
            entry["mappable"] = "med_admin_icu" in available
            entry.update(summarize_infusions(case, [i for i in case.infusions if infusion_matches(i, ids)]))
        elif src == "device":
            entry["mappable"] = "procedure_icu" in available
            in_place = [d for d in case.devices if d["item_id"] in ids and d["in_place_at_handoff"]]
            entry.update({"has_data": bool(in_place),
                          "in_place": [{k: d[k] for k in ("label", "start", "day", "site", "fhir_id")}
                                       for d in in_place]})
        elif src == "weight":
            entry["mappable"] = "chartevents" in available
            weights = [w for w in case.weights if w["item_id"] in ids]
            if weights:
                last = max(weights, key=lambda w: w["t"])
                entry.update({"has_data": True, "latest": last})
        else:
            entry["mappable"] = False
        if el.get("notes"):
            entry["note"] = el["notes"]
        summary[el["element_id"]] = entry
    return summary


# ---------------------------------------------------------------- output

def age_at(birth: str | None, moment: datetime):
    born = parse_time(birth)
    if not born:
        return None
    years = moment.year - born.year - ((moment.month, moment.day) < (born.month, born.day))
    return ">89" if years > 89 else years


def build_payload(case: Case, elements: list[dict], available: set[str], files_used: list[str]) -> dict:
    extra = add_derived(case)
    hospital = case.hospital_encounter or {}
    icu_start, icu_end = period_of(case.icu_encounter, "period")
    admit_start = period_of(hospital, "period")[0]
    in_window = iso(case.trend_start), iso(case.lookahead_end)
    active_orders = [o for o in case.med_orders
                     if (o["start"] or "") <= in_window[1] and (o["end"] or "9999") >= in_window[0]]
    case.med_admins.sort(key=lambda m: m["t"])
    case.infusions.sort(key=lambda i: i["start"])
    case.devices.sort(key=lambda d: d["start"])
    case.diagnoses.sort(key=lambda d: (d["seq"] is None, d["seq"] or 0))
    return {
        "schema_version": 1,
        "case_id": case.case_id,
        "complexity": case.spec.get("complexity"),
        "why": case.spec.get("why"),
        "disclaimer": "Research prototype. De-identified MIMIC-IV demo data. Not for clinical use.",
        "source": {"dataset": "MIMIC-IV Clinical Database Demo on FHIR (PhysioNet)",
                   "license": "Open Database License (ODbL) v1.0", "files": files_used},
        "time_note": "Times are MIMIC's date-shifted local (Boston) wall-clock times.",
        "patient": {"fhir_id": case.patient_id, "subject_id": str(case.spec["subject_id"]),
                    "gender": (case.patient or {}).get("gender"),
                    "age_at_handoff": age_at((case.patient or {}).get("birthDate"), case.handoff)},
        "stay": {"stay_id": str(case.spec["stay_id"]),
                 "hadm_id": identifier_value(hospital, "encounter-hosp", "identifier/encounter"),
                 "icu_encounter_fhir_id": (case.icu_encounter or {}).get("id"),
                 "hospital_encounter_fhir_id": case.hospital_id,
                 "careunit": case.careunit or case.spec.get("careunit"),
                 "hospital_admit_time": iso(admit_start),
                 "admission_class": (hospital.get("class") or {}).get("code"),
                 "icu_intime": iso(icu_start), "icu_outtime": iso(icu_end),
                 "icu_day": (case.handoff.date() - icu_start.date()).days + 1 if icu_start else None,
                 "handoff_time": iso(case.handoff)},
        "windows": {"lookback_start": iso(case.lookback_start), "trend_start": iso(case.trend_start),
                    "lab_start": iso(case.lab_start), "handoff": iso(case.handoff),
                    "lookahead_end": iso(case.lookahead_end)},
        "weight": extra["weight"],
        "elements": summarize_elements(case, elements, available),
        "observations": case.observations,
        "infusions": case.infusions,
        "med_administrations": case.med_admins,
        "med_administrations_note": ("Doses after the handoff time are the doses the eMAR shows were given "
                                     "in the next 12 h. Use them as a stand-in for what was due."),
        "med_orders_active": active_orders,
        "devices": case.devices,
        "diagnoses": case.diagnoses,
        "admission": case.admission or {"ed_encounter_fhir_id": None, "chief_complaint": None, "home_meds": []},
        "counts": {"observations": len(case.observations), "infusions": len(case.infusions),
                   "med_administrations": len(case.med_admins), "med_orders_active": len(active_orders),
                   "devices": len(case.devices), "diagnoses": len(case.diagnoses)},
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fhir-dir", type=Path, default=config.DEFAULT_FHIR_DIR,
                        help="folder holding the Mimic*.ndjson.gz files")
    parser.add_argument("--cases", type=Path, default=config.CASES_FILE)
    parser.add_argument("--elements", type=Path, default=config.DATA_ELEMENTS_FILE)
    parser.add_argument("--out-dir", type=Path, default=config.PROCESSED_DIR)
    args = parser.parse_args(argv)
    if not args.fhir_dir.exists():
        parser.error(f"{args.fhir_dir} not found. Run download_data.sh or pass --fhir-dir.")

    cases = load_cases(args.cases)
    elements = load_elements(args.elements)
    attach_encounters(args.fhir_dir, cases)
    ready = []
    for case in cases:
        problems = [name for name, ok in (("patient", case.patient), ("ICU stay", case.icu_encounter)) if not ok]
        if problems:
            print(f"! {case.case_id}: {' and '.join(problems)} not found in the FHIR files; skipped.")
            continue
        icu_start, icu_end = period_of(case.icu_encounter, "period")
        if icu_start and icu_end and not (icu_start <= case.handoff <= icu_end):
            print(f"! {case.case_id}: handoff {iso(case.handoff)} is outside the ICU stay "
                  f"({iso(icu_start)} to {iso(icu_end)}).")
        ready.append(case)
    if not ready:
        return 1

    by_patient = defaultdict(list)
    for case in ready:
        by_patient[case.patient_id].append(case)
    needles = [f"Patient/{pid}" for pid in by_patient]

    available, files_used = set(), []
    steps = [
        ("condition", lambda p: read_conditions(p, ready)),
        ("med_request", lambda p: read_orders(p, ready)),
        ("procedure_icu", lambda p: read_devices(p, by_patient, needles)),
        ("med_admin_icu", lambda p: read_infusions(p, by_patient, needles)),
        ("med_admin", lambda p: read_med_admins(p, by_patient, needles)),
        ("outputevents", lambda p: read_observations(p, "outputevents", by_patient, needles)),
        ("labevents", lambda p: read_observations(p, "labevents", by_patient, needles)),
        ("chartevents", lambda p: read_observations(p, "chartevents", by_patient, needles)),
    ]
    for key, reader in steps:
        path = resource_path(args.fhir_dir, key, required=False)
        if path is None:
            print(f"  (no {RESOURCE_FILES[key]} file found; skipping)")
            continue
        print(f"  reading {path.name} ...", flush=True)
        reader(path)
        available.add(key)
        files_used.append(path.name)

    for name in read_ed(args.fhir_dir, ready):
        print(f"  read {name}", flush=True)
        files_used.append(name)

    # Medication names for orders, then eMAR names through their orders.
    med_ids = {o["medication_ref"] for c in ready for o in c.med_orders if o["medication_ref"]}
    names = resolve_medication_names(args.fhir_dir, med_ids) if med_ids else {}
    for case in ready:
        order_names = {}
        for order in case.med_orders:
            order["name"] = order["name"] or names.get(order["medication_ref"])
            order_names[order["fhir_id"]] = order["name"]
        for admin in case.med_admins:
            admin["name"] = admin["name"] or order_names.get(admin["request_id"]) or admin["code"]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for case in ready:
        payload = build_payload(case, elements, available, files_used)
        out = args.out_dir / f"case_{case.case_id}.json"
        out.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        filled = sum(1 for e in payload["elements"].values() if e["has_data"])
        counts = payload["counts"]
        print(f"{case.case_id}: {counts['observations']} observations, {counts['infusions']} infusion rows, "
              f"{counts['med_administrations']} eMAR doses, {counts['devices']} procedures/devices; "
              f"{filled}/{len(payload['elements'])} data elements have data -> {out.relative_to(config.REPO_ROOT) if out.is_relative_to(config.REPO_ROOT) else out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
