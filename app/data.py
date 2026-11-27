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
PRACTICE = PROCESSED / "practice"   # the unscored practice stay for study mode (etl/practice_case.json)
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
    path = PROCESSED / f"case_{case_id}.json"
    if not path.exists():
        path = PRACTICE / f"case_{case_id}.json"
    with open(path, encoding="utf-8") as handle:
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


# ---------------------------------------------------------------- header facts
# Each returns the text to show and where it came from, so an empty or derived
# value says so in words instead of looking like a charted one.

DNR_CODES = {"Z66", "V4986"}   # ICD-10 / ICD-9 "Do not resuscitate status"


def _latest_text(case: dict, eid: str) -> tuple[str | None, dict]:
    el = case["elements"].get(eid) or {}
    if not el.get("has_data"):
        return None, {}
    latest = el.get("latest") or {}
    return latest.get("value_text") or fmt_num(latest.get("value")), latest


def reason_for_admission(case: dict) -> dict:
    """The ED chief complaint when the admission came through the ED, else the top diagnoses."""
    cc = (case.get("admission") or {}).get("chief_complaint")
    if cc:
        return {"text": cc["text"], "source": "ED chief complaint (LOINC 8661-1)", "fhir_id": cc.get("fhir_id"),
                "kind": "chief_complaint"}
    top = [d for d in diagnoses_sorted(case) if dx_rank(d) == 0][:3] or diagnoses_sorted(case)[:3]
    return {"text": "; ".join(d["display"] for d in top) or "Not in FHIR demo",
            "source": "No ED chief complaint for this admission, so the first 3 hospital diagnoses are shown "
                      "(FHIR carries no billing priority; disease codes come first)",
            "fhir_id": None, "kind": "diagnoses"}


def code_status(case: dict) -> dict:
    text, latest = _latest_text(case, "code_status")
    if text:
        return {"text": text, "source": f"Charted {fmt_time(latest.get('t'), handoff(case))}",
                "fhir_id": latest.get("fhir_id"), "alert": "dnr" in text.lower() or "dni" in text.lower()}
    dnr = next((d for d in case["diagnoses"] if (d.get("code") or "").replace(".", "") in DNR_CODES), None)
    if dnr:
        return {"text": "DNR", "source": f"Not charted at the bedside; from diagnosis code {dnr['code']} "
                                         f"({dnr['display']})", "fhir_id": dnr.get("fhir_id"), "alert": True}
    return {"text": "Not charted", "source": "No code status charted or coded for this stay", "fhir_id": None,
            "alert": False}


def allergies(case: dict) -> dict:
    text, latest = _latest_text(case, "allergies")
    if text:
        return {"text": text, "source": "Charted", "fhir_id": latest.get("fhir_id"), "empty": False}
    return {"text": "Not in FHIR demo", "source": "MIMIC-IV has no allergy table, so the FHIR demo has no "
                                                  "AllergyIntolerance resource", "fhir_id": None, "empty": True}


def isolation(case: dict) -> dict:
    text, latest = _latest_text(case, "precautions")
    if text:
        return {"text": text, "source": f"Charted {fmt_time(latest.get('t'), handoff(case))}",
                "fhir_id": latest.get("fhir_id"), "empty": False}
    return {"text": "Not charted", "source": "No precautions charted in the 24 h before handoff", "fhir_id": None,
            "empty": True}


def _obs_before(case: dict, labels: set[str], hours: float) -> list[dict]:
    end = handoff(case)
    start = end - timedelta(hours=hours)
    return sorted((o for o in case["observations"] if o["label"] in labels and start <= ts(o["t"]) <= end),
                  key=lambda o: o["t"])


def vte_prophylaxis(case: dict) -> dict:
    """Mechanical (compression devices, from charting) and drug prophylaxis (from the eMAR).

    A heparin infusion running at handoff is therapeutic anticoagulation, which is
    shown as such rather than as prophylaxis.
    """
    ref = handoff(case)
    parts, sources = [], []
    therapeutic = any(i.get("running_at_handoff") and "heparin" in i["label"].lower() for i in case["infusions"])
    if therapeutic:
        parts.append("on a heparin infusion")
        sources.append("infusion running at handoff")
    else:
        sq = [m for m in case["med_administrations"]
              if m.get("relative") == "before_handoff"
              and (m["name"].strip().lower() == "heparin" or "enoxaparin" in m["name"].lower())]
        if sq:
            last = sq[-1]
            drug = "enoxaparin" if "enoxaparin" in last["name"].lower() else "heparin SQ"
            parts.append(f"{drug}, last {fmt_time(last['t'], ref)}")
            sources.append("eMAR")
    device = _obs_before(case, {"Anti Embolic Device"}, 24)
    status = _obs_before(case, {"Anti Embolic Device Status"}, 24)
    if device:
        text = (device[-1].get("value_text") or "device").lower()
        if status:
            text += f", {(status[-1].get('value_text') or '').lower()}"
        parts.append(text)
        sources.append(f"charted {fmt_time(device[-1]['t'], ref)}")
    if not parts:
        return {"text": "Not charted", "source": "No compression device charted and no heparin or enoxaparin "
                                                 "in the eMAR", "empty": True}
    return {"text": "; ".join(parts), "source": "; ".join(sources), "empty": False}


# ---------------------------------------------------------------- care tasks
# The demo has no nursing task schedule, so "done" comes from charted care and
# "due" from the eMAR (doses given after handoff stand in for doses due) plus a
# placeholder turning interval.

TURN_EVERY_H = 2          # placeholder rule, not a unit policy
NOT_DONE = ("deferred", "refused", "not done")
CARE_ITEMS = {"Turn": "Turned", "Oral Care": "Oral care", "Bath": "Bath", "Eye Care": "Eye care"}


def _done(obs: dict) -> bool:
    text = (obs.get("value_text") or "").lower()
    if obs["label"] == "Eye Care":
        return obs.get("value") == 1
    return not any(word in text for word in NOT_DONE)


def tasks_done(case: dict, hours: float = 12) -> list[dict]:
    """Charted care, lab draws and doses given in the last `hours`, one row per kind."""
    ref = handoff(case)
    out = []
    for label, name in CARE_ITEMS.items():
        rows = _obs_before(case, {label}, hours)
        done = [o for o in rows if _done(o)]
        skipped = [o for o in rows if not _done(o)]
        if done:
            last = done[-1]
            detail = (last.get("value_text") or "").split(" (")[0]
            out.append({"t": last["t"], "name": name, "count": len(done),
                        "detail": detail if label in ("Turn", "Bath") else "",
                        "note": f"{skipped[-1].get('value_text', '').lower()} at {fmt_time(skipped[-1]['t'], ref)}"
                        if skipped and skipped[-1]["t"] > last["t"] else ""})
        elif skipped:
            out.append({"t": skipped[-1]["t"], "name": name, "count": 0, "detail": "",
                        "note": f"{(skipped[-1].get('value_text') or '').lower()} at "
                                f"{fmt_time(skipped[-1]['t'], ref)}"})
    start = ref - timedelta(hours=hours)
    draws: list[datetime] = []
    for t in sorted({ts(o["t"]) for o in case["observations"]
                     if o["source"] == "labevents" and start <= ts(o["t"]) <= ref}):
        if not draws or (t - draws[-1]).total_seconds() > 30 * 60:
            draws.append(t)
    if draws:
        out.append({"t": draws[-1].isoformat(), "name": "Labs drawn", "count": len(draws),
                    "detail": ", ".join(fmt_time(d, ref) for d in draws[-3:]), "note": ""})
    given = [m for m in case["med_administrations"]
             if m.get("relative") == "before_handoff" and start <= ts(m["t"]) <= ref]
    if given:
        out.append({"t": given[-1]["t"], "name": "Doses given", "count": len(given), "detail": "", "note": ""})
    return sorted(out, key=lambda r: r["t"], reverse=True)


def turn_due(case: dict) -> dict | None:
    """When the next turn falls due under the placeholder interval, from the last charted turn."""
    turns = [o for o in _obs_before(case, {"Turn", "Position Change"}, 24) if _done(o)]
    if not turns:
        return None
    due = ts(turns[-1]["t"]) + timedelta(hours=TURN_EVERY_H)
    return {"t": due.isoformat(), "overdue": due < handoff(case), "last": turns[-1]["t"]}


def home_meds(case: dict) -> list[dict]:
    return list((case.get("admission") or {}).get("home_meds") or [])
