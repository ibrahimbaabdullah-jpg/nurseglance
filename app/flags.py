"""Transparent rule-based flags (lightweight clinical decision support).

Each rule says what it checks, and each flag it raises carries the values that
triggered it with their times and FHIR resource IDs. Thresholds live in RULES so
they can be changed and cited in one place. They are off in study mode, so the
view comparison tests layout, not decision support.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app import data

# Thresholds. The MAP and SpO2 limits come from the project brief; the rest are
# common ICU nursing alert levels. Replace "cite" with your own references.
RULES = {
    "map_low": {"text": "MAP below 65 mmHg", "limit": 65, "cite": "Project brief; Surviving Sepsis Campaign 2021 MAP target 65"},
    "spo2": {"text": "SpO2 below 92%, or down 3 points or more over 2 h", "limit": 92, "drop": 3, "hours": 2,
             "cite": "Project brief"},
    "uop": {"text": "Urine output below 0.5 mL/kg/h over the last 6 h", "limit": 0.5,
            "cite": "KDIGO 2012 AKI urine output criterion"},
    "potassium": {"text": "Potassium outside 3.5-5.0 mEq/L", "low": 3.5, "high": 5.0, "cite": "Common adult reference range"},
    "lactate": {"text": "Lactate above 2 mmol/L", "limit": 2.0, "cite": "Sepsis-3 (Singer et al., JAMA 2016)"},
    "pressor": {"text": "Vasopressor infusion running", "cite": "Project brief"},
    "hr": {"text": "Heart rate above 120 or below 50 bpm", "low": 50, "high": 120, "cite": "Placeholder alert range"},
    "med_due": {"text": "Medication due within 1 hour of handoff", "hours": 1,
                "cite": "eMAR doses given in the next hour stand in for due doses"},
}


@dataclass
class Flag:
    rule_id: str
    title: str
    rule: str
    cite: str
    evidence: list[dict] = field(default_factory=list)   # {"what", "value", "t", "fhir_id"}


def _latest(case: dict, eid: str) -> dict | None:
    el = case["elements"].get(eid) or {}
    return el.get("latest") if el.get("has_data") else None


def _ev(what: str, latest: dict, value=None) -> dict:
    return {"what": what, "value": value if value is not None else latest.get("value"),
            "unit": latest.get("unit"), "t": latest.get("t"), "fhir_id": latest.get("fhir_id")}


def evaluate(case: dict) -> list[Flag]:
    ref = data.handoff(case)
    flags: list[Flag] = []

    def add(rule_id: str, title: str, evidence: list[dict]):
        rule = RULES[rule_id]
        flags.append(Flag(rule_id, title, rule["text"], rule["cite"], evidence))

    latest = _latest(case, "map")
    if latest and isinstance(latest.get("value"), (int, float)) and latest["value"] < RULES["map_low"]["limit"]:
        add("map_low", f"MAP {data.fmt_num(latest['value'])} mmHg", [_ev("MAP", latest)])

    spo2 = data.series(case, "spo2", hours=24)
    if spo2:
        t_last, v_last = spo2[-1]
        rule = RULES["spo2"]
        earlier = [(t, v) for t, v in spo2 if t <= t_last - timedelta(hours=rule["hours"])]
        drop = earlier and earlier[-1][1] - v_last >= rule["drop"]
        if v_last < rule["limit"] or drop:
            ev = [{"what": "SpO2", "value": v_last, "unit": "%", "t": t_last.isoformat(), "fhir_id": None}]
            if drop:
                ev.insert(0, {"what": "SpO2 2 h earlier", "value": earlier[-1][1], "unit": "%",
                              "t": earlier[-1][0].isoformat(), "fhir_id": None})
            add("spo2", f"SpO2 {data.fmt_num(v_last)}%" + (" and falling" if drop else ""), ev)

    uop = _latest(case, "urine_rate_6h")
    if uop and isinstance(uop.get("value"), (int, float)) and uop["value"] < RULES["uop"]["limit"]:
        add("uop", f"Urine output {data.fmt_num(uop['value'])} mL/kg/h", [_ev("Urine output rate, 6 h", uop)])

    k = _latest(case, "potassium")
    if k and isinstance(k.get("value"), (int, float)) and not RULES["potassium"]["low"] <= k["value"] <= RULES["potassium"]["high"]:
        add("potassium", f"Potassium {data.fmt_num(k['value'])}", [_ev("Potassium", k)])

    lac = _latest(case, "lactate")
    if lac and isinstance(lac.get("value"), (int, float)) and lac["value"] > RULES["lactate"]["limit"]:
        add("lactate", f"Lactate {data.fmt_num(lac['value'])}", [_ev("Lactate", lac)])

    pressors = (case["elements"].get("vasoactive_drips") or {}).get("running", [])
    if pressors:
        add("pressor", ", ".join(p["label"] for p in pressors),
            [{"what": p["label"], "value": data.fmt_num(p.get("rate")), "unit": p.get("rate_unit"),
              "t": p.get("since"), "fhir_id": p.get("fhir_id")} for p in pressors])

    hr = _latest(case, "heart_rate")
    if hr and isinstance(hr.get("value"), (int, float)) and not RULES["hr"]["low"] <= hr["value"] <= RULES["hr"]["high"]:
        add("hr", f"Heart rate {data.fmt_num(hr['value'])}", [_ev("Heart rate", hr)])

    soon = ref + timedelta(hours=RULES["med_due"]["hours"])
    due = [m for m in case["med_administrations"]
           if m.get("relative") == "after_handoff" and m.get("t") and ref <= data.ts(m["t"]) <= soon]
    if due:
        add("med_due", f"{len(due)} dose{'s' if len(due) > 1 else ''} due in the next hour",
            [{"what": m["name"], "value": data.fmt_num(m.get("dose")) if m.get("dose") else "",
              "unit": m.get("dose_unit"), "t": m["t"], "fhir_id": m.get("fhir_id")} for m in due])
    return flags


FLAG_CSS = """<style>
.ng-flags {display:flex; flex-wrap:wrap; gap:8px; margin:0 0 10px;}
.ng-flag {border:1px solid #e0a3a3; border-left:4px solid #c62828; border-radius:8px; padding:5px 10px;
  background:rgba(198,40,40,.05); font-size:.8rem; line-height:1.3; max-width:22rem;}
.ng-flag b {font-size:.86rem;}
.ng-flag .ng-rule {color:var(--ng-muted, #5f6b7a);}
.ng-flag ul {margin:2px 0 0 14px; padding:0;}
</style>"""


def render(case: dict) -> None:
    """One card per rule that fired, above the view: what fired, the rule, and the values behind it."""
    import html

    import streamlit as st

    flags = evaluate(case)
    ref = data.handoff(case)
    if not flags:
        st.caption("Rule-based flags: none of the 8 rules fired for this patient at handoff.")
        return
    cards = []
    for f in flags:
        rows = "".join(
            f"<li>{html.escape(str(e['what']))}: <b>{html.escape(str(e['value']))} "
            f"{html.escape(e.get('unit') or '')}</b> at {data.fmt_time(e.get('t'), ref)}</li>"
            for e in f.evidence[:4])
        more = f"<li>and {len(f.evidence) - 4} more</li>" if len(f.evidence) > 4 else ""
        tip = " · ".join(f"FHIR {e['fhir_id']}" for e in f.evidence if e.get("fhir_id"))
        cards.append(f'<div class="ng-flag" role="note" title="{html.escape(tip)}"><b>⚑ {html.escape(f.title)}</b>'
                     f'<div class="ng-rule">Rule: {html.escape(f.rule)} ({html.escape(f.cite)})</div>'
                     f'<ul>{rows}{more}</ul></div>')
    st.markdown(FLAG_CSS + f'<div class="ng-flags" aria-label="Rule-based flags">{"".join(cards)}</div>',
                unsafe_allow_html=True)
