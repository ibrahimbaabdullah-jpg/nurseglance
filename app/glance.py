"""NurseGlance view: one screen, organ-system panels, sparklines, abnormal highlighting.

Every value carries a hover title with its time, the reason it is flagged, its
LOINC code and the FHIR resource it came from, so a reviewer can trace any number
back to the source.

Version 0.3 changes, from the heuristic evaluation (docs/heuristic_evaluation.md):
short labels on one line, the 12-hour range printed under each trended value,
H and L beside abnormal values so color is not the only cue, empty elements folded
into one line per panel, a medication strip at the top (infusions running now and
the next dose of each drug, with times), and all diagnoses with disease codes first.
"""
from __future__ import annotations

import html
from datetime import datetime

import streamlit as st

from app import data
from app.timeline import timeline_figure, timeline_rows

TREND_HOURS = {"lab": 72}   # sparkline window by element source; everything else 12 h
DX_INLINE = 5                # diagnoses shown in the header before "show all"

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
    "Morse Fall Scale": "Morse fall", "Stool output": "Stool",
}

CSS = """
<style>
.ng-panel {border:1px solid var(--ng-border); border-radius:10px; padding:6px 9px 5px;
  margin-bottom:10px; background:var(--ng-bg);}
.ng-h {font-weight:700; font-size:.92rem; margin:0 0 2px; letter-spacing:.02em;}
.ng-h .ng-count {float:right; font-weight:500; font-size:.74rem; color:#c62828;}
.ng-row {display:grid; grid-template-columns: minmax(0,1fr) auto 54px; gap:6px; align-items:center;
  padding:2px 0; border-top:1px dashed var(--ng-border); font-size:.84rem; line-height:1.15;}
.ng-row:first-of-type {border-top:none;}
.ng-label {color:var(--ng-muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.ng-val {font-weight:600; text-align:right; white-space:nowrap;}
.ng-val small {font-weight:400; color:var(--ng-muted);}
.ng-txt {font-weight:600; text-align:right; white-space:normal; font-size:.8rem; max-width:9em;
  overflow-wrap:anywhere;}
.ng-row.ng-nospark {grid-template-columns: minmax(0,1fr) auto;}
.ng-rng {display:block; font-weight:400; font-size:.7rem; color:var(--ng-muted);}
.ng-hl {font-size:.68rem; font-weight:700; border:1px solid currentColor; border-radius:3px; padding:0 2px;
  margin-left:2px;}
.ng-abn .ng-val, .ng-abn .ng-txt {color:#c62828;}
.ng-abn {background:rgba(198,40,40,.07); border-radius:4px;}
.ng-recent .ng-label::after {content:" •"; color:#ef6c00;}
.ng-list {font-size:.82rem; margin:0; padding:1px 0; list-style:none;}
.ng-list li {padding:1px 0;}
.ng-sub {color:var(--ng-muted); font-size:.74rem;}
.ng-empty {font-size:.74rem; color:var(--ng-muted); border-top:1px dashed var(--ng-border); padding:2px 0 0;}
.ng-empty b {font-weight:600;}
.ng-spark {width:54px; height:18px;}
.ng-legend {font-size:.75rem; color:var(--ng-muted); margin:-4px 0 6px;}
.ng-meds {border:1px solid var(--ng-border); border-left:4px solid #1565c0; border-radius:8px;
  padding:5px 10px; margin:2px 0 10px; font-size:.84rem; line-height:1.45; background:var(--ng-bg);}
.ng-mh {font-weight:700; margin-right:6px; white-space:nowrap;}
.ng-head {font-size:1.25rem; font-weight:700; margin:0 0 2px;}
.ng-dx {font-size:.8rem; color:var(--ng-muted); margin:0 0 6px;}
.ng-dx details {display:inline;} .ng-dx summary {display:inline; cursor:pointer; text-decoration:underline dotted;}
.ng-dx ul {margin:4px 0 0 18px; padding:0;}
.ng-item {white-space:nowrap;}
.ng-item + .ng-item::before {content:"·"; color:var(--ng-muted); margin:0 .35em 0 .25em;}
:root {--ng-border:#d9dde3; --ng-bg:#ffffff; --ng-muted:#5f6b7a;}
@media (prefers-color-scheme: dark) {:root {--ng-border:#3a3f47; --ng-bg:#16191e; --ng-muted:#a3adba;}}
</style>
"""


def short(label: str) -> str:
    return SHORT_LABELS.get(label, label)


def sparkline(points: list[tuple[datetime, float]], low=None, high=None) -> str:
    if len(points) < 2:
        return ""
    w, h, pad = 54, 18, 2
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
    last_bad = (low not in (None, "") and vals[-1] < float(low)) or \
               (high not in (None, "") and vals[-1] > float(high))
    dot = "#c62828" if last_bad else "#1565c0"
    return (f'<svg class="ng-spark" viewBox="0 0 {w} {h}" aria-hidden="true">'
            f'<polyline points="{path}" fill="none" stroke="#7a8796" stroke-width="1.3"/>'
            f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="2.2" fill="{dot}"/></svg>')


def _arrow(change) -> str:
    if not isinstance(change, (int, float)) or change == 0:
        return ""
    return " ↑" if change > 0 else " ↓"


def _hl(el: dict) -> str:
    """'H' or 'L' for an abnormal value, so color is not the only cue."""
    reason = (el.get("abnormal_reason") or "").lower()
    if el.get("abnormal") is not True:
        return ""
    if reason.startswith(("below", "low")):
        return '<span class="ng-hl" title="below the threshold">L</span>'
    if reason.startswith(("above", "high")):
        return '<span class="ng-hl" title="above the threshold">H</span>'
    return ""


DNR_CODES = {"Z66", "V4986"}   # ICD-10 / ICD-9 "Do not resuscitate status"


def value_row(case: dict, eid: str, el: dict, ref: datetime) -> tuple[str, bool, str | None]:
    """(html, is_abnormal, empty_kind). empty_kind is set when the element has no value to show."""
    spec = data.element_specs().get(eid, {})
    full = el["label"]
    label = html.escape(short(full))
    if eid == "code_status" and not el.get("has_data"):
        dnr = next((d for d in case["diagnoses"] if (d.get("code") or "").replace(".", "") in DNR_CODES), None)
        if dnr:
            tip = html.escape(f"{full}. Not charted at the bedside. From the hospital diagnosis code "
                              f"{dnr['code']} ({dnr['display']}), FHIR Condition {dnr.get('fhir_id')}")
            return (f'<div class="ng-row ng-abn" data-eid="{eid}" title="{tip}"><span class="ng-label">{label}'
                    f'</span><span class="ng-val">DNR <small>dx code</small></span><span></span></div>', False, None)
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
        spark = sparkline(data.series(case, eid, hours), spec.get("low"), spec.get("high"))
    arrow = _arrow(el.get("change_12h")) if trend else ""
    age = data.hours_before(latest.get("t"), ref)
    stale = f' <small>{age:.0f}h ago</small>' if age is not None and age >= 6 else ""
    rng = ""
    if trend and (el.get("n_12h") or 0) >= 2 and el.get("min_12h") != el.get("max_12h"):
        rng = (f'<span class="ng-rng">12 h {data.fmt_num(el.get("min_12h"))}–'
               f'{data.fmt_num(el.get("max_12h"))}</span>')
    cls = "ng-row" + (" ng-abn" if abnormal else "") + (" ng-recent" if recent else "") + \
        ("" if spark else " ng-nospark")
    vcls = "ng-txt" if text_value and len(str(text_value)) > 8 else "ng-val"
    return (f'<div class="{cls}" data-eid="{eid}" title="{html.escape(" · ".join(title))}">'
            f'<span class="ng-label">{label}</span>'
            f'<span class="{vcls}">{html.escape(str(value))} <small>{html.escape(unit)}</small>'
            f'{_hl(el)}{arrow}{stale}{rng}</span>{spark or ""}</div>', abnormal, None)


def list_row(eid: str, el: dict, ref: datetime) -> tuple[str, str | None]:
    label = html.escape(short(el["label"]))
    items = []
    rule = el.get("display_rule")
    if rule == "running":
        for drip in el.get("running", []):
            rate = f"{data.fmt_num(drip.get('rate'))} {drip.get('rate_unit') or ''}"
            before = drip.get("rate_12h_ago")
            trend = ""
            if isinstance(before, (int, float)) and isinstance(drip.get("rate"), (int, float)):
                if abs(drip["rate"] - before) > 1e-6:
                    trend = f" ({'↑' if drip['rate'] > before else '↓'} from {data.fmt_num(before)})"
            items.append(f"<li><b>{html.escape(drip['label'])}</b> {html.escape(rate)}{trend} "
                         f'<span class="ng-sub">since {data.fmt_time(drip.get("since"), ref)}</span></li>')
        for drip in el.get("stopped_12h", []):
            items.append(f'<li>{html.escape(drip["label"])} <span class="ng-sub">stopped '
                         f'{data.fmt_time(drip.get("stopped_at"), ref)}</span></li>')
        given = el.get("given_12h", [])
        if given:
            names: dict[str, list[str]] = {}
            for dose in given:
                names.setdefault(dose["label"], []).append(data.fmt_time(dose.get("t"), ref))
            for name, times in names.items():
                items.append(f'<li>{html.escape(name)} <span class="ng-sub">given '
                             f'{", ".join(times[-3:])}{" …" if len(times) > 3 else ""}</span></li>')
    elif rule == "in_place":
        for dev in el.get("in_place", []):
            site = f" · {html.escape(dev['site'])}" if dev.get("site") else ""
            day = f"day {dev['day']}" if dev.get("day") else ""
            items.append(f'<li><b>{html.escape(dev["label"])}</b>{site} '
                         f'<span class="ng-sub">{day}</span></li>')
    if not items:
        return "", "none"
    return (f'<div class="ng-row" data-eid="{eid}" style="grid-template-columns:1fr" title="{html.escape(el["label"])}">'
            f'<span class="ng-label">{label}</span><ul class="ng-list">{"".join(items)}</ul></div>', None)


def panel_html(case: dict, system: str, ref: datetime) -> str:
    rows, n_abn = [], 0
    empty: dict[str, list[str]] = {}
    for eid, el in case["elements"].items():
        if el.get("organ_system") != system:
            continue
        if el.get("display_rule") in ("running", "in_place"):
            row, kind = list_row(eid, el, ref)
        else:
            row, abn, kind = value_row(case, eid, el, ref)
            n_abn += abn
        if kind:
            empty.setdefault(kind, []).append(short(el["label"]))
        else:
            rows.append(row)
    for kind in ("none", "not charted", "not in FHIR demo"):
        if empty.get(kind):
            rows.append(f'<div class="ng-empty"><b>{kind[0].upper() + kind[1:]}:</b> '
                        f'{html.escape(", ".join(empty[kind]))}</div>')
    count = f'<span class="ng-count">{n_abn} abnormal</span>' if n_abn else ""
    return f'<div class="ng-panel"><div class="ng-h">{html.escape(system)}{count}</div>{"".join(rows)}</div>'


def meds_strip(case: dict, ref: datetime) -> str:
    """Running infusions (with rates) and the next dose of each drug in the next 12 h."""
    doses, running = timeline_rows(case)
    drips = sorted(running, key=lambda r: (not str(r.get("category", "")).startswith("01"), r["label"]))
    run_items = []
    for d in drips:
        rate = f"{data.fmt_num(d.get('rate'))} {d.get('rate_unit') or ''}".strip()
        run_items.append(f'<span class="ng-item"><b>{html.escape(d["label"])}</b> {html.escape(rate)}</span>')
    first: dict[str, list[datetime]] = {}
    for m in doses:
        first.setdefault(m["name"].split(" + ")[0], []).append(data.ts(m["t"]))
    nxt = sorted(first.items(), key=lambda kv: min(kv[1]))
    next_items = [f'<span class="ng-item"><b>{data.fmt_time(min(ts), ref)}</b> {html.escape(name)}'
                  f'{f" <small>×{len(ts)}</small>" if len(ts) > 1 else ""}</span>' for name, ts in nxt]
    run_html = "".join(run_items) or '<span class="ng-sub">none</span>'
    next_html = "".join(next_items) or '<span class="ng-sub">no doses in the eMAR for the next 12 h</span>'
    return (f'<div class="ng-meds"><div><span class="ng-mh">Running now</span>{run_html}</div>'
            f'<div><span class="ng-mh">Next 12 h</span>{next_html}</div></div>')


def render(case: dict) -> None:
    ref = data.handoff(case)
    st.markdown(CSS, unsafe_allow_html=True)
    dx = data.diagnoses_sorted(case)
    shown = "; ".join(html.escape(data.dx_text(d)) for d in dx[:DX_INLINE])
    more = ""
    if len(dx) > DX_INLINE:
        items = "".join(f"<li>{html.escape(data.dx_text(d))}</li>" for d in dx)
        more = f' <details><summary>all {len(dx)}</summary><ul>{items}</ul></details>'
    st.markdown(f'<div class="ng-head">{html.escape(data.patient_line(case))} · {html.escape(data.weight_text(case))}'
                f'</div><div class="ng-dx">Handoff {ref:%Y-%m-%d %H:%M} · <b>Diagnoses</b> ({len(dx)}; billing codes '
                f'carry no priority in FHIR, so disease codes come first): {shown}{more}</div>',
                unsafe_allow_html=True)
    st.markdown(meds_strip(case, ref), unsafe_allow_html=True)
    st.markdown('<div class="ng-legend">Red with <b>H</b>/<b>L</b> = latest value outside its threshold '
                '(placeholder thresholds, not clinically validated) · <span style="color:#ef6c00">•</span> = '
                'abnormal earlier in the last 12 h · grey = 12 h range · sparklines 12 h (labs 72 h) · hover a '
                'row for time, LOINC code and FHIR id</div>', unsafe_allow_html=True)
    systems = data.ORGAN_SYSTEMS
    for start in range(0, len(systems), 4):
        cols = st.columns(4, gap="small")
        for col, system in zip(cols, systems[start:start + 4]):
            with col:
                st.markdown(panel_html(case, system, ref), unsafe_allow_html=True)
    st.markdown("##### Next 12 hours: medications and running infusions")
    st.plotly_chart(timeline_figure(case), width="stretch",
                    config={"displayModeBar": False})
    st.caption(case.get("med_administrations_note", ""))
