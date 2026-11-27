"""Small helpers for reading MIMIC-IV on FHIR NDJSON files.

They avoid depending on exact code-system URLs, which changed between FHIR
demo releases (http://fhir.mimic.mit.edu/... in 2.0, http://mimic.mit.edu/fhir/mimic/...
later). Resources are matched by identifier suffix and by which file they came from.
"""
from __future__ import annotations

import gzip
import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator
from zoneinfo import ZoneInfo

# MIMIC comes from Beth Israel Deaconess in Boston. FHIR timestamps carry a UTC
# offset; converting back to Boston time gives the same wall-clock times as the
# MIMIC CSV tables, which makes FHIR and CSV directly comparable.
MIMIC_TZ = ZoneInfo("America/New_York")

# Short name -> file stem used on PhysioNet (without the "Mimic" prefix).
RESOURCE_FILES = {
    "patient": "Patient",
    "encounter": "Encounter",
    "encounter_icu": "EncounterICU",
    "location": "Location",
    "chartevents": "ObservationChartevents",
    "labevents": "ObservationLabevents",
    "outputevents": "ObservationOutputevents",
    "med_admin_icu": "MedicationAdministrationICU",
    "med_admin": "MedicationAdministration",
    "med_request": "MedicationRequest",
    "medication": "Medication",
    "medication_mix": "MedicationMix",
    "procedure_icu": "ProcedureICU",
    "condition": "Condition",
    "encounter_ed": "EncounterED",
    "observation_ed": "ObservationED",
    "med_statement_ed": "MedicationStatementED",
}


def find_resource_file(fhir_dir: str | Path, stem: str) -> Path | None:
    """Find a resource file whether it is named like PhysioNet's
    (MimicPatient.ndjson.gz), unzipped, or without the Mimic prefix."""
    folder = Path(fhir_dir)
    for name in (f"Mimic{stem}.ndjson.gz", f"Mimic{stem}.ndjson",
                 f"{stem}.ndjson.gz", f"{stem}.ndjson"):
        path = folder / name
        if path.exists():
            return path
    return None


def iter_ndjson(path: str | Path, contains: Iterable[str] | None = None) -> Iterator[dict]:
    """Yield one FHIR resource per line.

    `contains` is a fast pre-filter: a line is parsed only if it contains at
    least one of these strings (for example "Patient/<id>"). This makes a pass
    over the 600 MB chartevents file take seconds instead of minutes.
    """
    needles = tuple(contains) if contains else None
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if needles and not any(n in line for n in needles):
                continue
            line = line.strip()
            if line:
                yield json.loads(line)


def parse_time(value: str | None) -> datetime | None:
    """FHIR date/dateTime -> naive Boston wall-clock datetime (or None)."""
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None  # partial dates such as "2150-05" are not used here
    if moment.tzinfo is not None:
        moment = moment.astimezone(MIMIC_TZ).replace(tzinfo=None)
    return moment


def iso(moment: datetime | None) -> str | None:
    return moment.isoformat(timespec="seconds") if moment else None


def ref_id(reference: dict | str | None) -> str | None:
    """{"reference": "Encounter/abc"} -> "abc"."""
    if not reference:
        return None
    text = reference.get("reference") if isinstance(reference, dict) else reference
    return text.rsplit("/", 1)[-1] if text else None


def first_coding(concept: dict | None) -> dict:
    """First coding of a CodeableConcept, falling back to its text."""
    if isinstance(concept, list):  # some elements are lists of CodeableConcepts
        concept = concept[0] if concept else None
    if not concept:
        return {}
    codings = concept.get("coding") or []
    if codings:
        return codings[0]
    return {"display": concept["text"]} if concept.get("text") else {}


def identifier_value(resource: dict, *suffixes: str) -> str | None:
    """Value of the first identifier whose system ends with one of `suffixes`."""
    for ident in resource.get("identifier") or []:
        system = (ident.get("system") or "").rstrip("/")
        if any(system.endswith(s) for s in suffixes):
            return ident.get("value")
    return None


def period_of(resource: dict, key: str) -> tuple[datetime | None, datetime | None]:
    """Start/end of a Period field, e.g. key="effectivePeriod"."""
    period = resource.get(key) or {}
    return parse_time(period.get("start")), parse_time(period.get("end"))


def quantity(q: dict | None) -> tuple[float | None, str | None]:
    if not q:
        return None, None
    return q.get("value"), q.get("unit") or q.get("code")


def observation_value(resource: dict) -> tuple[float | None, str | None, str | None]:
    """(number, text, unit) from an Observation's value[x]."""
    if "valueQuantity" in resource:
        number, unit = quantity(resource["valueQuantity"])
        return number, None, unit
    if "valueString" in resource:
        text = str(resource["valueString"]).strip()
        try:
            return float(text), text, None
        except ValueError:
            return None, text, None
    if "valueCodeableConcept" in resource:
        coding = first_coding(resource["valueCodeableConcept"])
        return None, coding.get("display") or coding.get("code"), None
    for key in ("valueInteger", "valueDecimal"):
        if key in resource:
            return float(resource[key]), None, None
    for key in ("valueDateTime", "valueBoolean"):
        if key in resource:
            return None, str(resource[key]), None
    return None, None, None


def lab_flag_and_range(resource: dict) -> tuple[str | None, float | None, float | None]:
    """(flag, reference low, reference high) for a lab Observation."""
    flag = None
    for interp in resource.get("interpretation") or []:
        code = first_coding(interp).get("code")
        if code:
            flag = code
            break
    low = high = None
    ranges = resource.get("referenceRange") or []
    if ranges:
        low = (ranges[0].get("low") or {}).get("value")
        high = (ranges[0].get("high") or {}).get("value")
    return flag, low, high
