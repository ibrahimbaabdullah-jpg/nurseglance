"""Load the per-case JSON files written by etl/build_cases.py and shape them for the views.

Both views read the same case file through these helpers, so any difference the
study measures comes from the layout, not from the data.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
ELEMENTS_CSV = ROOT / "docs" / "data_elements.csv"

ORGAN_SYSTEMS = ["Neuro", "CV", "Resp", "Renal/I&O", "GI/Nutrition", "Heme/ID",
                 "Skin/Lines/Devices", "Safety"]
CASE_ORDER = ["S1", "S2", "C1", "C2"]


def ts(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def available_cases() -> list[str]:
    found = {p.stem.removeprefix("case_") for p in PROCESSED.glob("case_*.json")}
    return [c for c in CASE_ORDER if c in found] + sorted(found - set(CASE_ORDER))


@lru_cache(maxsize=8)
def load_case(case_id: str) -> dict:
    with open(PROCESSED / f"case_{case_id}.json", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def element_specs() -> dict[str, dict]:
    """Rows of docs/data_elements.csv by element_id, with item_ids split into a list."""
    with open(ELEMENTS_CSV, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["item_id_list"] = [i for i in (row.get("item_ids") or "").split("|") if i]
    return {row["element_id"]: row for row in rows}


def handoff(case: dict) -> datetime:
    return ts(case["stay"]["handoff_time"])


def series(case: dict, element_id: str, hours: float | None = None) -> list[tuple[datetime, float]]:
    """Numeric (time, value) points for one element, oldest first.

    Uses every item ID the element lists (for MAP: arterial, cuff, calculated) and
    keeps one value per time stamp, preferring the first ID in the list.
    """
    spec = element_specs().get(element_id)
    if not spec:
        return []
    ids = spec["item_id_list"]
    rank = {item: i for i, item in enumerate(ids)}
    end = handoff(case)
    start = end - timedelta(hours=hours) if hours else None
    best: dict[datetime, tuple[int, float]] = {}
    for obs in case["observations"]:
        if obs["item_id"] not in rank or not isinstance(obs.get("value"), (int, float)):
            continue
        moment = ts(obs["t"])
        if moment > end or (start and moment < start):
            continue
        value = float(obs["value"])   # the ETL already restored the RASS goal's sign
        prev = best.get(moment)
        if prev is None or rank[obs["item_id"]] < prev[0]:
            best[moment] = (rank[obs["item_id"]], value)
    return sorted((t, v) for t, (_, v) in best.items())


def fmt_num(value) -> str:
    if value is None:
        return "–"
    if isinstance(value, float):
        if abs(value) >= 100:
            return f"{value:.0f}"
        if abs(value) >= 10:
            return f"{value:.1f}".rstrip("0").rstrip(".")
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def fmt_time(value: str | datetime | None, ref: datetime | None = None) -> str:
    """'16:00', or '16:00 (-1d)' when the time is on an earlier day than ref."""
    if value is None:
        return "–"
    moment = ts(value) if isinstance(value, str) else value
    text = moment.strftime("%H:%M")
    if ref is not None:
        days = (moment.date() - ref.date()).days
        if days:
            text += f" ({days:+d}d)"
    return text


def hours_before(moment: str | None, ref: datetime) -> float | None:
    if not moment:
        return None
    return (ref - ts(moment)).total_seconds() / 3600


def lab_flag(obs: dict) -> str:
    """'H' or 'L' against the result's own reference range, else ''."""
    value = obs.get("value")
    if not isinstance(value, (int, float)):
        return ""
    low, high = obs.get("ref_low"), obs.get("ref_high")
    if high is not None and value > high:
        return "H"
    if low is not None and value < low:
        return "L"
    return ""


def patient_line(case: dict) -> str:
    p, s = case["patient"], case["stay"]
    sex = {"female": "F", "male": "M"}.get(p.get("gender"), "?")
    unit = s["careunit"]
    short = unit[unit.find("(") + 1:unit.find(")")] if "(" in unit else unit
    return f"{p.get('age_at_handoff', '?')} {sex} · {short} · ICU day {s['icu_day']}"


def weight_text(case: dict) -> str:
    w = case.get("weight") or {}
    return f"{fmt_num(w.get('value'))} kg" if w.get("value") else "weight not charted"


LOINC_CSV = ROOT / "docs" / "loinc_mapping.csv"


@lru_cache(maxsize=1)
def loinc_table() -> dict[str, tuple[str, str]]:
    """MIMIC item ID (or derived code) -> (LOINC code, LOINC long name)."""
    if not LOINC_CSV.exists():
        return {}
    with open(LOINC_CSV, newline="", encoding="utf-8") as handle:
        return {r["mimic_item_id"]: (r["loinc_code"], r["loinc_long_name"])
                for r in csv.DictReader(handle) if r["loinc_code"]}


@lru_cache(maxsize=4096)
def _item_by_fhir_id(case_id: str, fhir_id: str) -> str | None:
    for obs in load_case(case_id)["observations"]:
        if obs.get("fhir_id") == fhir_id:
            return obs["item_id"]
    return None


def loinc_for(case: dict, element_id: str, latest: dict | None) -> tuple[str, str] | None:
    """LOINC (code, name) for the item behind an element's latest value, else the element's first item."""
    table = loinc_table()
    item = None
    if latest and latest.get("fhir_id"):
        item = _item_by_fhir_id(case["case_id"], latest["fhir_id"])
    if latest and latest.get("item_id"):
        item = latest["item_id"]
    if item is None:
        el = case["elements"].get(element_id) or {}
        item = str(el.get("item_id") or "")
    return table.get(str(item))


def dx_text(diagnosis: dict) -> str:
    code = diagnosis.get("code") or ""
    if code and len(code) > 3 and "." not in code and diagnosis.get("version") == "ICD-10":
        code = f"{code[:3]}.{code[3:]}"
    return f"{diagnosis['display']} ({code})" if code else diagnosis["display"]


def dx_rank(diagnosis: dict) -> int:
    """Sort key that lists disease codes first, then status codes, then external causes.

    FHIR Condition in the demo carries no billing priority (MIMIC's seq_num is not
    converted), so this is the only ordering available, and it is labeled as such.
    """
    code = (diagnosis.get("code") or "").upper()
    if diagnosis.get("version") == "ICD-10":
        if code[:1] in ("V", "W", "X", "Y"):
            return 2
        return 1 if code.startswith("Z") else 0
    if code.startswith("E"):
        return 2
    return 1 if code.startswith("V") else 0


def diagnoses_sorted(case: dict) -> list[dict]:
    return sorted(case["diagnoses"], key=dx_rank)
