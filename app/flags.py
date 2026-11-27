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


def _fhir_id_at(case: dict, eid: str, moment: datetime) -> str | None:
    """FHIR id of the element's observation charted at this moment (series() keeps only time and value)."""
    ids = set((data.element_specs().get(eid) or {}).get("item_id_list", []))
    stamp = moment.isoformat(timespec="seconds")
    return next((o.get("fhir_id") for o in case["observations"] if o["item_id"] in ids and o["t"] == stamp), None)


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
            ev = [{"what": "SpO2", "value": v_last, "unit": "%", "t": t_last.isoformat(),
                   "fhir_id": _fhir_id_at(case, "spo2", t_last)}]
            if drop:
                ev.insert(0, {"what": "SpO2 2 h earlier", "value": earlier[-1][1], "unit": "%",
                              "t": earlier[-1][0].isoformat(), "fhir_id": _fhir_id_at(case, "spo2", earlier[-1][0])})
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


ICONS = {
    "warn": ('<svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="#A84A0A" '
             'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 2.5 20h19z"></path>'
             '<path d="M12 10v4"></path><path d="M12 17.5v.01"></path></svg>'),
    "trend": ('<svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="#A84A0A" '
              'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7l6 6 4-4 8 8"></path>'
              '<path d="M21 11v6h-6"></path></svg>'),
    "clock": ('<svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="#1C5D86" '
              'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"></circle>'
              '<path d="M12 7v5l3 2"></path></svg>'),
    "info": ('<svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="#1C5D86" '
             'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"></circle>'
             '<path d="M12 11v6"></path><path d="M12 7.5v.01"></path></svg>'),
}
# Info cards (blue outline) for rules that report something to plan for rather than a value out of range.
INFO_RULES = {"pressor": "info", "med_due": "clock"}

FLAG_CSS = """<style>
.ng-flags {display:flex; flex-direction:column; gap:10px; font-family:Inter, system-ui, sans-serif;
  color:var(--ng-text, #16212B);}
.ng-flags h2 {margin:0; padding:0; font-family:var(--ng-head); font-size:16px; font-weight:600; line-height:1.25;
  color:var(--ng-text, #16212B);}
.ng-flags h2 small {font-family:Inter, system-ui, sans-serif; font-size:12px; font-weight:400;
  color:var(--ng-muted, #5A6671); margin-left:8px;}
.ng-fgrid {display:grid; grid-template-columns:repeat(auto-fit, minmax(min(300px, 100%), 1fr)); gap:12px;}
.ng-flag {display:flex; gap:12px; align-items:flex-start; background:#FFF8F1; border:1px solid #F0C9A5;
  border-radius:10px; padding:12px 16px;}
.ng-flag.ng-flag-info {background:#FFFFFF; border-color:#C7DBE8;}
.ng-flag img {flex:none; margin-top:1px;}
.ng-flag div {display:flex; flex-direction:column; gap:3px; min-width:0;}
.ng-flag strong {font-size:15px; font-weight:600;}
.ng-flag span {font-size:12px; color:var(--ng-muted2, #4A5560); line-height:1.35;}
.ng-noflags {font-size:13px; color:var(--ng-muted, #5A6671); margin:0;}
</style>"""


def cards_html(case: dict) -> str:
    """One card per rule that fired: what fired, the rule, and the values behind it with their times."""
    import html

    from app.ui import svg_img

    found = evaluate(case)
    ref = data.handoff(case)
    if not found:
        return FLAG_CSS + ('<p class="ng-noflags" role="note">Rule-based flags: none of the 8 rules fired for this '
                           'patient at handoff.</p>')
    cards = []
    for f in found:
        shown = "; ".join(
            f"{e['what']} {e['value']}{(' ' + e['unit']) if e.get('unit') else ''} at {data.fmt_time(e.get('t'), ref)}"
            for e in f.evidence[:3]) + (f"; and {len(f.evidence) - 3} more" if len(f.evidence) > 3 else "")
        tip = " · ".join(f"FHIR {e['fhir_id']}" for e in f.evidence if e.get("fhir_id"))
        icon = INFO_RULES.get(f.rule_id) or ("trend" if "falling" in f.title else "warn")
        cls = "ng-flag" + (" ng-flag-info" if f.rule_id in INFO_RULES else "")
        cards.append(f'<div class="{cls}" role="note" data-rule="{f.rule_id}" title="{html.escape(tip)}">'
                     f'{svg_img(ICONS[icon])}<div><strong>{html.escape(f.title)}</strong>'
                     f'<span>Rule: {html.escape(f.rule)} · {html.escape(shown)}</span>'
                     f'<span>Source: {html.escape(f.cite)}</span></div></div>')
    n = len(found)
    head = f"{n} flag{'s' if n != 1 else ''} need{'s' if n == 1 else ''} attention"
    return (FLAG_CSS + f'<section class="ng-flags" aria-label="Rule-based flags"><h2>{head}'
            f'<small>8 transparent rules · placeholder thresholds, not clinically validated</small></h2>'
            f'<div class="ng-fgrid">{"".join(cards)}</div></section>')


def render(case: dict) -> None:
    import streamlit as st

    st.html(cards_html(case))
