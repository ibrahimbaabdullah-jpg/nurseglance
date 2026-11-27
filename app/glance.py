"""NurseGlance view: one screen, organ-system cards, sparklines, abnormal highlighting.

Every value carries a hover title with its time, the reason it is flagged, its
LOINC code and the FHIR resource it came from, so a reviewer can trace any number
back to the source.

Version 0.3 changes, from the heuristic evaluation (docs/heuristic_evaluation.md):
short labels on one line, the 12-hour range printed with each trended value,
LOW and HIGH beside abnormal values so color is not the only cue, empty elements
folded into one line per card, the infusions running now and the next dose of each
drug with times, and all diagnoses with disease codes first.

Version 1.1 changes, from the screen design review against Dr. Khairat's work and
the Lindroth 2022 nurse survey: a header with the reason for admission, code status,
allergies, isolation and VTE prophylaxis (each naming its source, and saying so when
the FHIR demo has no value); and a task list that runs from what was done in the
last 12 h to what is due next, since 61% of surveyed ICU nurses wanted tasks and the
schedule on screen. The demo has no task schedule, so "due" uses the eMAR stand-in
and a turning interval that is labeled a placeholder.

Version 1.2 takes the look of the design mockup (docs/design/): a patient card with
a Safety row of chips, flag cards, white system cards with a count of abnormal values,
and the Tasks & meds list as a fourth column. Rows stay on one line, so a whole
patient still fits a 1440 x 900 screen. Status words the data cannot support
("stable", "improving") and values the demo does not have (bed, name, allergies)
are left out.
"""
from __future__ import annotations

import html
from datetime import datetime

import streamlit as st

from app import data, flags
from app.timeline import timeline_rows
from app.ui import svg_img

TREND_HOURS = {"lab": 72}   # sparkline window by element source; everything else 12 h

SHORT_LABELS = {
    "Mean arterial pressure": "MAP", "Systolic blood pressure": "SBP", "Central venous pressure": "CVP",
    "Mechanical circulatory support (IABP or Impella)": "MCS (IABP/Impella)", "Heart rhythm": "Rhythm",
    "Vasoactive infusions": "Vasoactive drips", "Sedation and analgesia infusions": "Sedation drips",
    "Pupils (size and response)": "Pupils", "CAM-ICU components": "CAM-ICU", "Respiratory rate": "Resp rate",
    "O2 delivery device": "O2 device", "Ventilation in place": "Ventilation", "PEEP set": "PEEP",
    "Urine output (last 6 h)": "UOP 6 h", "Urine output rate (last 6 h)": "UOP rate", "Ventilator mode": "Vent mode",
    "Intake (last 12 h)": "Intake 12 h", "Output (last 12 h)": "Output 12 h", "Net balance (last 12 h)": "Net 12 h",
    "Dialysis or CRRT": "Dialysis/CRRT", "Glucose (point of care)": "Glucose POC", "Glucose (lab)": "Glucose lab",
    "Enteral nutrition": "Tube feeds", "Lines and catheters": "Lines", "Foley catheter": "Foley",
    "Morse Fall Scale": "Morse fall", "Stool output": "Stool", "Hemoglobin": "Hgb", "Temperature": "Temp",
    "White blood cells": "WBC", "Arterial pH": "pH (arterial)",
}

# Card titles, as in the mockup, for the organ systems in data.ORGAN_SYSTEMS.
TITLES = {"Neuro": "Neuro", "CV": "Cardiovascular", "Resp": "Respiratory", "Renal/I&O": "Renal · I&O",
          "GI/Nutrition": "GI · Nutrition", "Heme/ID": "Heme · Infection",
          "Skin/Lines/Devices": "Skin · Lines & drains", "Safety": "Safety"}
# Three columns of cards, balanced by row count for the complex patients; the Tasks & meds list is the
# fourth column.
# Safety has no card: its values are the chips in the patient card.
# The top row reads head to toe (Neuro, Cardiovascular, Respiratory).
COLUMNS = [["Neuro", "Renal/I&O"], ["CV", "Heme/ID"], ["Resp", "GI/Nutrition", "Skin/Lines/Devices"]]
HEADER_EIDS = {"code_status", "allergies", "precautions", "fall_risk", "restraints"}   # in the patient card

CSS = """
<style>
.ng-patient {background:var(--ng-surface); border:1px solid var(--ng-border); border-radius:12px;
  padding:11px 20px 9px; display:flex; flex-direction:column; gap:8px; color:var(--ng-text);
  font-family:Inter, system-ui, sans-serif;}
.ng-pt-top {display:flex; flex-wrap:wrap; align-items:flex-end; gap:8px 28px;}
.ng-pt-id {display:flex; flex-direction:column; gap:3px; margin-right:auto;}
.ng-eyebrow {font-size:12px; font-weight:600; letter-spacing:.06em; text-transform:uppercase; color:var(--ng-muted);}
.ng-patient h1.ng-pt-name {margin:0; padding:0; font-family:var(--ng-head); font-size:21px; font-weight:700;
  letter-spacing:-.01em; line-height:1.15; color:var(--ng-text);}
.ng-pt-line {font-size:14px; color:var(--ng-text2);}
.ng-field {display:flex; flex-direction:column; gap:2px; max-width:360px; min-width:0;}
.ng-field .ng-clamp {white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.ng-fl {font-size:12px; color:var(--ng-muted);}
.ng-fv {font-size:15px; font-weight:600; color:var(--ng-text); line-height:1.3;}
.ng-fv-warn {color:var(--ng-warn);}
.ng-fv-empty {color:var(--ng-muted); font-weight:500;}
.ng-fs {font-size:11.5px; color:var(--ng-muted);}
.ng-fs details {display:inline;} .ng-fs summary {display:inline; cursor:pointer; text-decoration:underline dotted;}
.ng-fs ul {margin:4px 0 0 16px; padding:0; color:var(--ng-text2); font-size:12.5px;}
.ng-safety {display:flex; flex-wrap:wrap; align-items:center; gap:8px; padding-top:8px;
  border-top:1px solid var(--ng-divider);}
.ng-safety-h {font-size:12px; font-weight:600; letter-spacing:.06em; text-transform:uppercase; color:var(--ng-muted);
  margin-right:4px;}
.ng-chip {font-size:13px; font-weight:500; color:var(--ng-text); background:var(--ng-track); padding:3px 9px;
  border-radius:6px; border:1px solid transparent;}
.ng-chip b {font-weight:600;}
.ng-chip-warn {color:var(--ng-warn-strong); background:var(--ng-warn-bg); font-weight:600;}
.ng-chip-empty {color:var(--ng-muted); background:transparent; border:1px dashed #C9D1D7; padding:2px 8px;}
.ng-chip-empty b {font-weight:500;}
.ng-infrow {flex-wrap:nowrap; align-items:baseline;}
.ng-infs {display:flex; flex-wrap:wrap; column-gap:0; row-gap:1px; font-size:13px; line-height:1.3; min-width:0;}
.ng-inf {white-space:nowrap;}
.ng-inf b {font-weight:600;}
.ng-inf + .ng-inf::before {content:"·"; color:var(--ng-muted); margin:0 .45em 0 .4em;}
.ng-inf small {color:var(--ng-muted); font-size:11.5px;}
.ng-none {color:var(--ng-muted);}
.ng-patient .ng-safety + .ng-safety {padding-top:5px;}

.ng-boardwrap {container-type:inline-size;}
.ng-board {display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)) minmax(0, .85fr); gap:12px; align-items:start;
  font-family:Inter, system-ui, sans-serif; color:var(--ng-text);}
.ng-col {display:flex; flex-direction:column; gap:12px; min-width:0;}
@container (max-width: 860px) {.ng-board {grid-template-columns:repeat(2, minmax(0, 1fr));}}
@container (max-width: 520px) {.ng-board {grid-template-columns:minmax(0, 1fr);}}
.ng-sys {background:var(--ng-surface); border:1px solid var(--ng-border); border-radius:12px; padding:9px 12px 5px;}
.ng-sys-h {display:flex; align-items:center; justify-content:space-between; gap:8px; padding-bottom:4px;}
.ng-sys-h {min-height:23px;}
.ng-sys-h h3 {margin:0; padding:0; font-family:var(--ng-head); font-size:15.5px; font-weight:600;
  letter-spacing:-.01em; color:var(--ng-text); line-height:1.25; white-space:nowrap;}
.ng-pill {font-size:11.5px; font-weight:600; padding:3px 8px; border-radius:999px; white-space:nowrap;}
.ng-pill-warn {color:var(--ng-warn-strong); background:var(--ng-warn-bg);}
.ng-pill-plain {color:var(--ng-text2); background:var(--ng-track);}
.ng-row, .ng-li {display:grid; grid-template-columns:minmax(0, 1fr) auto auto; align-items:center; column-gap:6px;
  padding:2px 0; border-top:1px solid var(--ng-divider); min-height:20px; line-height:1.1;}
ul.ng-row {display:block; list-style:none; margin:0; padding:0; border-top:0; min-height:0;}
.ng-label {font-size:12.5px; color:var(--ng-muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.ng-li .ng-label {color:var(--ng-text2);}
.ng-li .ng-val small {white-space:normal; display:inline-block; max-width:11em; text-align:right; line-height:1.15;}
.ng-li .ng-right:has(.ng-cap:empty) {display:none;}
.ng-dot {color:var(--ng-warn); font-weight:700; margin-left:2px;}   /* 5.8:1 on white (WCAG AA) */
.ng-val {font-size:14px; font-weight:600; color:var(--ng-text); text-align:right; white-space:nowrap;}
.ng-val small {font-size:11.5px; font-weight:400; color:var(--ng-muted); margin-left:3px;}
.ng-val .ng-arrow {font-size:12px; color:var(--ng-text2); margin-left:2px; font-weight:600;}
.ng-txt {font-size:12.5px; font-weight:600; text-align:right; white-space:normal; max-width:12em;
  overflow-wrap:anywhere; line-height:1.25;}
.ng-abn .ng-val, .ng-abn .ng-txt {color:var(--ng-warn);}
.ng-badge {font-size:9.5px; font-weight:700; letter-spacing:.06em; color:var(--ng-warn); background:var(--ng-warn-bg);
  padding:2px 4px; border-radius:4px; margin-left:4px; vertical-align:1px;}
.ng-right {display:flex; flex-direction:column; align-items:flex-end; gap:0; min-width:34px;}
.ng-cap {font-size:11px; color:var(--ng-muted); white-space:nowrap; line-height:1.1;}
.ng-spark {width:52px; height:13px; display:block;}
.ng-spark + .ng-cap {font-size:10px; line-height:1;}
.ng-empty {font-size:11px; color:var(--ng-muted); border-top:1px solid var(--ng-divider); padding:4px 0 2px;
  line-height:1.3;}
.ng-empty b {font-weight:600; color:var(--ng-text2);}

.ng-tasks {background:var(--ng-surface); border:1px solid var(--ng-border); border-radius:12px; padding:9px 13px 6px;}
.ng-tasks h2 {margin:0; padding:0 0 4px; font-family:var(--ng-head); font-size:15.5px; font-weight:600;
  letter-spacing:-.01em; color:var(--ng-text); line-height:1.25;}
.ng-tsec {font-size:11px; font-weight:600; letter-spacing:.06em; text-transform:uppercase; color:var(--ng-muted);
  margin:5px 0 1px;}
.ng-tasks ol {list-style:none; margin:0; padding:0;}
.ng-tasks li {display:grid; grid-template-columns:38px minmax(0, 1fr) auto; align-items:center; column-gap:6px;
  padding:2px 0; border-top:1px solid var(--ng-divider); font-size:13px; line-height:1.15; min-height:21px;}
.ng-tasks li.ng-day {display:block; min-height:0; padding:3px 0 1px; font-size:10.5px; font-weight:600;
  letter-spacing:.06em; text-transform:uppercase; color:var(--ng-muted);}
.ng-tasks li.ng-run {grid-template-columns:minmax(0, 1fr) auto;}
.ng-tt {font-size:12px; color:var(--ng-muted);}
.ng-tx {white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.ng-tx small {color:var(--ng-muted); font-size:11.5px;}
.ng-run .ng-tx b, .ng-due .ng-tx b {font-weight:600;}
.ng-run .ng-rate {font-weight:600; text-align:right; white-space:nowrap;}
.ng-run .ng-rate small {font-weight:400; font-size:11px; color:var(--ng-muted);}
.ng-done .ng-tx {color:var(--ng-text2);}
.ng-st {font-size:11.5px; color:var(--ng-muted); display:flex; align-items:center; gap:3px; white-space:nowrap;}
.ng-soon {font-size:11.5px; font-weight:600; color:#FFFFFF; background:var(--ng-accent); padding:2px 8px;
  border-radius:999px; white-space:nowrap;}
.ng-over {font-size:11.5px; font-weight:600; color:var(--ng-warn-strong); background:var(--ng-warn-bg);
  padding:2px 8px; border-radius:999px; white-space:nowrap;}
.ng-due.ng-next .ng-tt, .ng-due.ng-next .ng-tx {font-weight:600; color:var(--ng-text);}
.ng-tasks li.ng-now {display:flex; align-items:center; gap:8px; padding:6px 0 2px; border-top:0; min-height:0;}
.ng-now span:first-child {font-size:12px; font-weight:700; color:var(--ng-accent); white-space:nowrap;}
.ng-now .ng-line {flex:1 1 0; height:2px; border-radius:2px; background:var(--ng-accent);}
.ng-legend {font-size:11.5px; color:var(--ng-muted); margin:0; line-height:1.4;}
.ng-legend .ng-badge {margin-left:0;}
</style>
"""

CHECK = svg_img('<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#5A6671" stroke-width="2.4" '
                'stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"></path></svg>')


def short(label: str) -> str:
    return SHORT_LABELS.get(label, label)


def sparkline(points: list[tuple[datetime, float]], low=None, high=None, warn: bool | None = None) -> str:
    """A 52 x 13 line over the window; drawn in the warning color when the latest value is out of range.

    warn, when given, is the element's own flag for its latest value, so a lab outside its reference range
    (labs have no threshold in docs/data_elements.csv) is drawn in the warning color too.
    """
    if len(points) < 2:
        return ""
    w, h, pad = 52, 13, 1.5
    t0, t1 = points[0][0], points[-1][0]
    span = (t1 - t0).total_seconds() or 1
    vals = [v for _, v in points]
    lo, hi = min(vals), max(vals)
    if hi == lo:
        hi, lo = hi + 1, lo - 1
    xy = [(pad + (t - t0).total_seconds() / span * (w - 2 * pad),
           h - pad - (v - lo) / (hi - lo) * (h - 2 * pad)) for t, v in points]
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in xy)
    lx, ly = xy[-1]
    last_bad = warn if warn is not None else (
        (low not in (None, "") and vals[-1] < float(low)) or (high not in (None, "") and vals[-1] > float(high)))
    line, dot = ("#A84A0A", "#A84A0A") if last_bad else ("#8C98A3", "#1C5D86")
    return svg_img(f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
                   f'<polyline points="{path}" fill="none" stroke="{line}" stroke-width="1.6" stroke-linejoin="round" '
                   f'stroke-linecap="round"></polyline><circle cx="{lx:.1f}" cy="{ly:.1f}" r="2.3" fill="{dot}">'
                   f'</circle></svg>', "ng-spark")


def _arrow(change) -> str:
    if not isinstance(change, (int, float)) or change == 0:
        return ""
    return f'<span class="ng-arrow">{"↑" if change > 0 else "↓"}</span>'


def _badge(el: dict) -> str:
    """LOW or HIGH beside an abnormal value, so color is not the only cue."""
    reason = (el.get("abnormal_reason") or "").lower()
    if el.get("abnormal") is not True:
        return ""
    if reason.startswith(("below", "low")):
        return '<span class="ng-badge" title="below the threshold">LOW</span>'
    if reason.startswith(("above", "high")):
        return '<span class="ng-badge" title="above the threshold">HIGH</span>'
    return ""


def value_row(case: dict, eid: str, el: dict, ref: datetime) -> tuple[str, bool, str | None]:
    """(html, is_abnormal, empty_kind). empty_kind is set when the element has no value to show."""
    spec = data.element_specs().get(eid, {})
    full = el["label"]
    if not el.get("has_data"):
        return "", False, ("not charted" if el.get("mappable") else "not in FHIR demo")
    latest = el.get("latest") or {}
    text_value = latest.get("value_text")
    value = text_value or data.fmt_num(latest.get("value"))
    unit = latest.get("unit") or spec.get("unit") or ""
    if unit in ("score", "points", "units"):
        unit = ""
    abnormal = el.get("abnormal") is True
    recent = not abnormal and el.get("any_abnormal_12h")
    title = [full, f"Charted {data.fmt_time(latest.get('t'), ref)}"]
    if el.get("n_12h"):
        title.append(f"12 h: {el['n_12h']} values, range {data.fmt_num(el.get('min_12h'))}–"
                     f"{data.fmt_num(el.get('max_12h'))}")
    if abnormal:
        title.append(f"Flag: {el.get('abnormal_reason')}")
    elif recent:
        title.append("Abnormal at least once in the last 12 h")
    loinc = data.loinc_for(case, eid, latest)
    if loinc:
        title.append(f"LOINC {loinc[0]} {loinc[1]}")
    if latest.get("fhir_id"):
        title.append(f"FHIR id {latest['fhir_id']}")
    if el.get("note"):
        title.append(el["note"])
    trend = el.get("display_rule") == "trend"
    spark = ""
    if trend:
        hours = TREND_HOURS.get(el.get("source"), 12)
        spark = sparkline(data.series(case, eid, hours), spec.get("low"), spec.get("high"), warn=abnormal)
    arrow = _arrow(el.get("change_12h")) if trend else ""
    age = data.hours_before(latest.get("t"), ref)
    if trend and (el.get("n_12h") or 0) >= 2 and el.get("min_12h") != el.get("max_12h"):
        cap = f'{data.fmt_num(el.get("min_12h"))}–{data.fmt_num(el.get("max_12h"))}'
        title.append(f"12 h range {cap}")
    elif age is not None and age >= 6:
        cap = f"{age:.0f} h ago"
    else:
        cap = data.fmt_time(latest.get("t"), ref)
    cls = "ng-row" + (" ng-abn" if abnormal else "")
    dot = '<span class="ng-dot" title="abnormal earlier in the last 12 h">•</span>' if recent else ""
    long_text = bool(text_value) and len(str(text_value)) > 9
    shown = (f'<span class="ng-txt">{html.escape(str(value))}{_badge(el)}</span>' if long_text else
             f'<span class="ng-val">{html.escape(str(value))}<small>{html.escape(unit)}</small>{_badge(el)}'
             f'{arrow}</span>')
    return (f'<div class="{cls}" data-eid="{eid}" title="{html.escape(" · ".join(title))}">'
            f'<span class="ng-label">{html.escape(short(full))}{dot}</span>{shown}'
            f'<span class="ng-right">{spark}<span class="ng-cap">{html.escape(cap)}</span></span></div>',
            abnormal, None)


def _li(label: str, value: str, cap: str, title: str = "") -> str:
    tip = f' title="{html.escape(title)}"' if title else ""
    return (f'<li class="ng-li"{tip}><span class="ng-label">{html.escape(label)}</span>'
            f'<span class="ng-val">{value}</span><span class="ng-right"><span class="ng-cap">{html.escape(cap)}'
            f'</span></span></li>')


def _side(site: str) -> str:
    """'Left Radial' -> 'L Radial': the charting shorthand, so a long site leaves room for the device name."""
    first, _, rest = site.partition(" ")
    return f"{first[0]} {rest}" if first in ("Left", "Right") and rest else site


def list_rows(eid: str, el: dict, ref: datetime) -> tuple[str, str | None]:
    """One line per drip, dose or device (the card title says what kind), or ('', 'none')."""
    items = []
    rule = el.get("display_rule")
    if rule == "running":
        for drip in el.get("running", []):
            rate = (f'{html.escape(data.fmt_num(drip.get("rate")))}'
                    f'<small>{html.escape(drip.get("rate_unit") or "")}</small>')
            before, cap = drip.get("rate_12h_ago"), ""
            if isinstance(before, (int, float)) and isinstance(drip.get("rate"), (int, float)) \
                    and abs(drip["rate"] - before) > 1e-6:
                cap = f"{'↑' if drip['rate'] > before else '↓'} from {data.fmt_num(before)}"
            items.append(_li(drip["label"].replace(" (Concentrate)", ""), rate, cap,
                             f"{drip['label']} · {el['label']} · running at handoff, this rate since "
                                                       f"{data.fmt_time(drip.get('since'), ref)}"))
        for drip in el.get("stopped_12h", []):
            items.append(_li(drip["label"], '<small>stopped</small>', data.fmt_time(drip.get("stopped_at"), ref),
                             f"{el['label']} · stopped in the last 12 h"))
        names: dict[str, list[str]] = {}
        for dose in el.get("given_12h", []):
            names.setdefault(dose["label"], []).append(data.fmt_time(dose.get("t"), ref))
        for name, times in names.items():
            items.append(_li(name, f'<small>given ×{len(times)}</small>' if len(times) > 1 else '<small>given</small>',
                             times[-1], f"{el['label']} · given {', '.join(times)}"))
    elif rule == "in_place":
        for dev in el.get("in_place", []):
            site = dev.get("site") or ""
            items.append(_li(dev["label"], f'<small>{html.escape(_side(site))}</small>',
                             f"day {dev['day']}" if dev.get("day") else "",
                             f"{el['label']} · in place at handoff" + (f" · site: {site}" if site else "")))
    if not items:
        return "", "none"
    return f'<ul class="ng-row ng-list" data-eid="{eid}" title="{html.escape(el["label"])}">{"".join(items)}</ul>', None


def card_html(case: dict, system: str, ref: datetime) -> str:
    """One organ-system card: title, count of abnormal latest values, rows, and a line for what is empty."""
    rows, n_abn = [], 0
    empty: dict[str, list[str]] = {}
    for eid, el in case["elements"].items():
        if el.get("organ_system") != system or eid in HEADER_EIDS:
            continue
        if el.get("display_rule") in ("running", "in_place"):
            row, kind = list_rows(eid, el, ref)
        else:
            row, abn, kind = value_row(case, eid, el, ref)
            n_abn += abn
        if kind:
            empty.setdefault(kind, []).append(short(el["label"]))
        else:
            rows.append(row)
    parts = [f'<b>{kind[0].upper() + kind[1:]}:</b> {html.escape(", ".join(empty[kind]))}'
             for kind in ("none", "not charted", "not in FHIR demo") if empty.get(kind)]
    if parts:
        rows.append(f'<div class="ng-empty">{" · ".join(parts)}</div>')
    pill = f'<span class="ng-pill ng-pill-warn">{n_abn} abnormal</span>' if n_abn else ""
    sid = "sys-" + "".join(ch for ch in system.lower() if ch.isalnum())
    return (f'<section class="ng-sys" data-system="{html.escape(system)}" aria-labelledby="{sid}">'
            f'<div class="ng-sys-h"><h3 id="{sid}">{html.escape(TITLES.get(system, system))}</h3>{pill}</div>'
            f'{"".join(rows)}</section>')


def _chip(name: str, text: str, kind: str = "", source: str = "", eid: str = "") -> str:
    cls = "ng-chip" + (f" ng-chip-{kind}" if kind else "")
    attr = f' data-eid="{eid}"' if eid else ""
    return (f'<span class="{cls}"{attr} title="{html.escape(source)}"><b>{html.escape(name)}:</b> '
            f'{html.escape(text)}</span>')


def _element_chip(case: dict, eid: str, name: str, ref: datetime) -> str:
    el = case["elements"].get(eid) or {}
    if not el.get("has_data"):
        return _chip(name, "not charted" if el.get("mappable", True) else "not in FHIR demo", "empty",
                     "Nothing charted in the 24 h before handoff", eid)
    latest = el.get("latest") or {}
    value = latest.get("value_text") or data.fmt_num(latest.get("value"))
    text = f"Morse {value}" if eid == "fall_risk" else str(value)
    src = f"{el['label']} · charted {data.fmt_time(latest.get('t'), ref)}"
    if el.get("abnormal") is True:
        src += f" · flag: {el.get('abnormal_reason')}"
    return _chip(name, text, "warn" if el.get("abnormal") is True else "", src, eid)


def patient_line_long(case: dict) -> str:
    p, s = case["patient"], case["stay"]
    sex = {"female": "Female", "male": "Male"}.get(p.get("gender"), "Sex not recorded")
    unit = s["careunit"]
    unit = unit[unit.find("(") + 1:unit.find(")")] if "(" in unit else unit
    return f"{p.get('age_at_handoff', '?')} y · {sex} · {unit} · ICU day {s['icu_day']} · {data.weight_text(case)}"


def patient_card(case: dict, ref: datetime, eyebrow: str | None = None, title: str | None = None,
                 infusions: bool = False) -> str:
    """Who the patient is, why they are here, code status and allergies, then the Safety chips.

    With infusions=True (NurseGlance) a third row lists the infusions running at handoff that no card
    shows (fluids, heparin, CRRT solutions, blood). The tabbed control shows the card without that row,
    since it lists every infusion on its Summary and MAR tabs.
    """
    reason = data.reason_for_admission(case)
    dx = data.diagnoses_sorted(case)
    items = "".join(f"<li>{html.escape(data.dx_text(d))}</li>" for d in dx)
    more = f' · <details><summary>all {len(dx)} diagnoses</summary><ul>{items}</ul></details>' if dx else ""
    label = "Reason for admission" if reason["kind"] == "chief_complaint" else "Diagnoses"
    src = "ED chief complaint" if reason["kind"] == "chief_complaint" else "first 3 billing codes, no priority in FHIR"
    code, allergy = data.code_status(case), data.allergies(case)
    code_text = code["text"]
    code_src = ('<span class="ng-fs">from a diagnosis code</span>' if code["text"] == "DNR" and
                code["source"].startswith("Not charted") else "")
    code_cls = " ng-fv-warn" if code.get("alert") else (" ng-fv-empty" if code["text"] == "Not charted" else "")
    allergy_cls = " ng-fv-empty" if allergy["empty"] else " ng-fv-warn"
    iso, vte = data.isolation(case), data.vte_prophylaxis(case)
    chips = "".join([
        _element_chip(case, "fall_risk", "Fall risk", ref),
        _chip("Isolation", iso["text"], "empty" if iso["empty"] else "", iso["source"], "precautions"),
        _element_chip(case, "restraints", "Restraints", ref),
        _chip("VTE prophylaxis", vte["text"], "empty" if vte["empty"] else "", vte["source"]),
    ])
    eyebrow = eyebrow or f"ICU handoff · {ref:%Y-%m-%d %H:%M}"
    # Without a title (study mode, where patients carry no case labels) the patient line is the title.
    name = title or f"{data.patient_line(case)} · {data.weight_text(case)}"
    line = f'<span class="ng-pt-line">{html.escape(patient_line_long(case))}</span>' if title else ""
    return (f'<section class="ng-patient" aria-label="Patient summary"><div class="ng-pt-top">'
            f'<div class="ng-pt-id"><span class="ng-eyebrow">{html.escape(eyebrow)}</span>'
            f'<h1 class="ng-pt-name">{html.escape(name)}</h1>{line}</div>'
            f'<div class="ng-field"><span class="ng-fl">{label}</span>'
            f'<span class="ng-fv ng-clamp" title="{html.escape(reason["text"] + " · " + reason["source"])}">'
            f'{html.escape(reason["text"])}</span>'
            f'<span class="ng-fs">{src}{more}</span></div>'
            f'<div class="ng-field" data-eid="allergies"><span class="ng-fl">Allergies</span>'
            f'<span class="ng-fv{allergy_cls}" title="{html.escape(allergy["source"])}">{html.escape(allergy["text"])}'
            f'</span></div>'
            f'<div class="ng-field" data-eid="code_status"><span class="ng-fl">Code status</span>'
            f'<span class="ng-fv{code_cls}" title="{html.escape(code["source"])}">{html.escape(code_text)}</span>'
            f'{code_src}</div>'
            f'</div><div class="ng-safety"><span class="ng-safety-h">Safety</span>{chips}</div>'
            f'{infusions_row(case, ref) if infusions else ""}</section>')


def _in_cards(case: dict) -> set[str]:
    """Labels of the drips the system cards already list (vasoactive drips under Cardiovascular, sedation under Neuro)."""
    return {d["label"] for el in case["elements"].values() if el.get("display_rule") == "running"
            for d in el.get("running", [])}


def infusions_row(case: dict, ref: datetime) -> str:
    """The other infusions running at handoff (fluids, heparin, CRRT solutions, blood), with any 12 h titration.

    Vasoactive and sedation drips are not repeated here: their cards list them, as in the mockup.
    """
    _, running = timeline_rows(case)
    shown = _in_cards(case)
    drips = sorted((r for r in running if r["label"] not in shown), key=lambda r: r["label"])
    before = _titration(case)
    chips = []
    for d in drips:
        rate = f'{html.escape(data.fmt_num(d.get("rate")))} {html.escape(d.get("rate_unit") or "")}'.strip()
        was, sub = before.get(d["label"]), ""
        if was is not None and isinstance(d.get("rate"), (int, float)) and abs(d["rate"] - was) > 1e-6:
            sub = f' <small>{"↑" if d["rate"] > was else "↓"} from {data.fmt_num(was)}</small>'
        tip = f"{d['label']} · running at handoff, this rate since {data.fmt_time(d.get('start'), ref)}"
        chips.append(f'<span class="ng-inf ng-item" title="{html.escape(tip)}"><b>{html.escape(d["label"])}'
                     f'</b> {rate}{sub}</span>')
    body = "".join(chips) or '<span class="ng-inf ng-none">none running besides the drips in the cards</span>'
    return (f'<div class="ng-safety ng-infrow"><span class="ng-safety-h">Other infusions</span>'
            f'<div class="ng-meds ng-infs">{body}</div></div>')


def _titration(case: dict) -> dict[str, float]:
    """Drip label -> its rate 12 h before handoff, from the running-infusion elements."""
    out = {}
    for el in case["elements"].values():
        for drip in el.get("running", []) if el.get("display_rule") == "running" else []:
            if isinstance(drip.get("rate_12h_ago"), (int, float)):
                out[drip["label"]] = drip["rate_12h_ago"]
    return out


def tasks_html(case: dict, ref: datetime) -> str:
    """The Tasks & meds list: what was done in the last 12 h, the handoff line, then what is due.

    Due doses are the eMAR doses given in the next 12 h (the demo has no schedule);
    the turn is due a placeholder interval after the last charted turn.
    """
    doses, _ = timeline_rows(case)
    def day_line(when: datetime, last: list) -> str:
        """A 'previous day' or 'next day' line where the date changes, so times stay plain HH:MM."""
        days = (when.date() - ref.date()).days
        if last and last[0] == days:
            return ""
        first = not last
        last[:] = [days]
        if first and days == 0:
            return ""
        name = {-1: "Previous day", 0: "Handoff day", 1: "Next day"}.get(days, f"{days:+d} days")
        return f'<li class="ng-day">{name}</li>'

    seen: list = []
    done_items = []
    for t in sorted(data.tasks_done(case), key=lambda r: r["t"]):
        if t["count"] == 0:
            text, status = f'{html.escape(t["name"])} <small>{html.escape(t["note"])}</small>', "Not done"
        elif t["name"] == "Labs drawn":
            text, status = f'Labs drawn <small>{html.escape(t["detail"])}</small>', f"{CHECK}Done"
        elif t["name"] == "Doses given":
            text, status = f'{t["count"]} doses given <small>eMAR</small>', f"{CHECK}Given"
        else:
            times = f' <small>×{t["count"]}</small>' if t["count"] > 1 else ""
            note = f' <small>{html.escape(t["note"])}</small>' if t["note"] else ""
            text, status = f'{html.escape(t["name"])}{times}{note}', f"{CHECK}Done"
        plain = html.unescape(text.replace("<small>", "").replace("</small>", ""))
        when = data.ts(t["t"])
        done_items.append(f'{day_line(when, seen)}<li class="ng-done" title="{html.escape(plain)}">'
                          f'<span class="ng-tt">{when:%H:%M}</span><span class="ng-tx">{text}</span>'
                          f'<span class="ng-st">{status}</span></li>')
    first: dict[str, list[datetime]] = {}
    for m in doses:
        first.setdefault(m["name"].split(" + ")[0], []).append(data.ts(m["t"]))
    due = [(min(times), html.escape(name) + (f" <small>×{len(times)}</small>" if len(times) > 1 else ""), False)
           for name, times in first.items()]
    turn = data.turn_due(case)
    if turn:
        due.append((data.ts(turn["t"]), f'Turn <small>placeholder rule: every {data.TURN_EVERY_H} h</small>',
                    turn["overdue"]))
    due.sort(key=lambda d: d[0])
    seen = [0]
    due_items = []
    for when, text, overdue in due:
        minutes = (when - ref).total_seconds() / 60
        if overdue:
            status, nxt = '<span class="ng-over">Overdue</span>', True
        elif minutes <= 60:
            status, nxt = f'<span class="ng-soon">In {max(0, round(minutes))} min</span>', True
        else:
            status, nxt = "", False
        plain = html.unescape(text.replace("<small>", "").replace("</small>", ""))
        due_items.append(f'{day_line(when, seen)}<li class="ng-due ng-item{" ng-next" if nxt else ""}" '
                         f'title="{html.escape(plain)}"><span class="ng-tt">{"now" if overdue else f"{when:%H:%M}"}</span>'
                         f'<span class="ng-tx">{text}</span>{status}</li>')
    none = '<li class="ng-done"><span class="ng-tt"></span><span class="ng-tx"><small>{}</small></span></li>'
    return (f'<aside class="ng-tasks ng-meds" aria-labelledby="tasks-h"><h2 id="tasks-h">Tasks &amp; meds</h2>'
            f'<div class="ng-tsec">Done · last 12 h</div>'
            f'<ol>{"".join(done_items) or none.format("No care charted in the last 12 h")}</ol>'
            f'<ol><li class="ng-now" aria-label="Handoff {ref:%H:%M}"><span>Handoff {ref:%H:%M}</span>'
            f'<span class="ng-line"></span></li></ol>'
            f'<div class="ng-tsec">Due · next 12 h</div>'
            f'<ol>{"".join(due_items) or none.format("No doses in the eMAR for the next 12 h")}</ol></aside>')


LEGEND = ('<p class="ng-legend"><span class="ng-badge">LOW</span> / <span class="ng-badge">HIGH</span> = latest '
          'value outside its threshold (placeholder thresholds, not clinically validated) · '
          '<span class="ng-dot">•</span> = abnormal earlier in the last 12 h · ↑↓ = change over 12 h · '
          'sparklines 12 h (labs 72 h), with the 12 h low–high under them · hover a row for its time, LOINC code and FHIR id · due times are the eMAR '
          'doses given after handoff, as the demo has no order schedule</p>')


def board_html(case: dict, ref: datetime) -> str:
    cols = "".join(f'<div class="ng-col">{"".join(card_html(case, s, ref) for s in col)}</div>' for col in COLUMNS)
    return (f'<div class="ng-boardwrap"><div class="ng-board">{cols}'
            f'<div class="ng-col">{tasks_html(case, ref)}</div></div></div>')


def render(case: dict, show_flags: bool = False, eyebrow: str | None = None, title: str | None = None) -> None:
    ref = data.handoff(case)
    st.html(CSS + patient_card(case, ref, eyebrow, title, infusions=True))
    if show_flags:
        st.html(flags.cards_html(case))
    st.html(board_html(case, ref))
    st.html(LEGEND)
