"""NurseGlance view: one screen, organ-system panels, sparklines, abnormal highlighting.

Every value carries a hover title with its time, the reason it is flagged and the
FHIR resource it came from, so a reviewer can trace any number back to the source.
"""
from __future__ import annotations

import html
from datetime import datetime

import streamlit as st

from app import data
from app.timeline import timeline_figure

TREND_HOURS = {"lab": 72}   # sparkline window by element source; everything else 12 h

CSS = """
<style>
.ng-panel {border:1px solid var(--ng-border); border-radius:10px; padding:8px 10px 6px;
  margin-bottom:12px; background:var(--ng-bg);}
.ng-panel h4 {margin:0 0 4px; font-size:0.95rem; letter-spacing:.02em;}
.ng-panel h4 .ng-count {float:right; font-weight:500; font-size:.75rem; color:#c62828;}
.ng-row {display:grid; grid-template-columns: 1fr auto 64px; gap:6px; align-items:center;
  padding:3px 0; border-top:1px dashed var(--ng-border); font-size:.86rem; line-height:1.2;}
.ng-row:first-of-type {border-top:none;}
.ng-label {color:var(--ng-muted);}
.ng-val {font-weight:600; text-align:right; white-space:nowrap;}
.ng-val small {font-weight:400; color:var(--ng-muted);}
.ng-abn .ng-val {color:#c62828;}
.ng-abn {background:rgba(198,40,40,.07); border-radius:4px;}
.ng-recent .ng-label::after {content:" •"; color:#ef6c00;}
.ng-none .ng-val {color:var(--ng-muted); font-weight:400; font-style:italic;}
.ng-list {font-size:.84rem; margin:0; padding:2px 0 2px 0; list-style:none;}
.ng-list li {padding:2px 0;}
.ng-list .ng-sub {color:var(--ng-muted); font-size:.78rem;}
.ng-spark {width:64px; height:20px;}
.ng-legend {font-size:.78rem; color:var(--ng-muted);}
:root {--ng-border:#d9dde3; --ng-bg:#ffffff; --ng-muted:#5f6b7a;}
@media (prefers-color-scheme: dark) {:root {--ng-border:#3a3f47; --ng-bg:#16191e; --ng-muted:#a3adba;}}
</style>
"""


def sparkline(points: list[tuple[datetime, float]], low=None, high=None) -> str:
    if len(points) < 2:
        return ""
    w, h, pad = 64, 20, 2
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


DNR_CODES = {"Z66", "V4986"}   # ICD-10 / ICD-9 "Do not resuscitate status"


def value_row(case: dict, eid: str, el: dict, ref: datetime) -> tuple[str, bool]:
    spec = data.element_specs().get(eid, {})
    label = html.escape(el["label"])
    if eid == "code_status" and not el.get("has_data"):
        dnr = next((d for d in case["diagnoses"] if (d.get("code") or "").replace(".", "") in DNR_CODES), None)
        if dnr:
            tip = html.escape(f"Not charted at the bedside. From the hospital diagnosis code {dnr['code']} "
                              f"({dnr['display']}), FHIR Condition {dnr.get('fhir_id')}")
            return (f'<div class="ng-row ng-abn" title="{tip}"><span class="ng-label">{label}</span>'
                    f'<span class="ng-val">DNR <small>dx code</small></span><span></span></div>', False)
    if not el.get("has_data"):
        note = "not in FHIR demo" if not el.get("mappable") else "not charted"
        return (f'<div class="ng-row ng-none"><span class="ng-label">{label}</span>'
                f'<span class="ng-val">{note}</span><span></span></div>', False)
    latest = el.get("latest") or {}
    value = latest.get("value_text") or data.fmt_num(latest.get("value"))
    unit = latest.get("unit") or spec.get("unit") or ""
    if unit in ("score", "points"):
        unit = ""
    abnormal = el.get("abnormal") is True
    recent = not abnormal and el.get("any_abnormal_12h")
    title = [f"Charted {data.fmt_time(latest.get('t'), ref)}"]
    if el.get("n_12h"):
        title.append(f"12 h: {el['n_12h']} values, range {data.fmt_num(el.get('min_12h'))}–"
                     f"{data.fmt_num(el.get('max_12h'))}")
    if abnormal:
        title.append(f"Flag: {el.get('abnormal_reason')}")
    elif recent:
        title.append("Abnormal at least once in the last 12 h")
    if latest.get("fhir_id"):
        title.append(f"FHIR id {latest['fhir_id']}")
    if el.get("note"):
        title.append(el["note"])
    spark = ""
    if el.get("display_rule") == "trend":
        hours = TREND_HOURS.get(el.get("source"), 12)
        spark = sparkline(data.series(case, eid, hours), spec.get("low"), spec.get("high"))
    arrow = _arrow(el.get("change_12h")) if el.get("display_rule") == "trend" else ""
    cls = "ng-row" + (" ng-abn" if abnormal else "") + (" ng-recent" if recent else "")
    age = data.hours_before(latest.get("t"), ref)
    stale = f' <small>{age:.0f}h ago</small>' if age is not None and age >= 6 else ""
    return (f'<div class="{cls}" title="{html.escape(" · ".join(title))}">'
            f'<span class="ng-label">{label}</span>'
            f'<span class="ng-val">{html.escape(str(value))} <small>{html.escape(unit)}</small>'
            f'{arrow}{stale}</span>{spark}</div>', abnormal)


def list_row(el: dict, ref: datetime) -> str:
    label = html.escape(el["label"])
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
            items.append(f"<li><b>{html.escape(drip['label'])}</b> {html.escape(rate)}{trend}"
                         f'<br><span class="ng-sub">rate since {data.fmt_time(drip.get("since"), ref)}</span></li>')
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
        return (f'<div class="ng-row ng-none"><span class="ng-label">{label}</span>'
                f'<span class="ng-val">none</span><span></span></div>')
    return (f'<div class="ng-row" style="grid-template-columns:1fr"><span class="ng-label">{label}</span>'
            f'<ul class="ng-list">{"".join(items)}</ul></div>')


def panel_html(case: dict, system: str, ref: datetime) -> str:
    rows, n_abn = [], 0
    for eid, el in case["elements"].items():
        if el.get("organ_system") != system:
            continue
        if el.get("display_rule") in ("running", "in_place"):
            rows.append(list_row(el, ref))
        else:
            row, abn = value_row(case, eid, el, ref)
            rows.append(row)
            n_abn += abn
    count = f'<span class="ng-count">{n_abn} abnormal</span>' if n_abn else ""
    return f'<div class="ng-panel"><h4>{html.escape(system)}{count}</h4>{"".join(rows)}</div>'


def render(case: dict) -> None:
    ref = data.handoff(case)
    st.markdown(CSS, unsafe_allow_html=True)
    dx = ", ".join(d["display"] for d in case["diagnoses"][:3])
    st.markdown(f"#### {data.patient_line(case)} · {data.weight_text(case)}")
    st.caption(f"Handoff {ref:%Y-%m-%d %H:%M} · Diagnoses (billing codes, unordered): {dx}"
               f"{' …' if len(case['diagnoses']) > 3 else ''}")
    st.markdown('<div class="ng-legend">Red = latest value outside the threshold · '
                '<span style="color:#ef6c00">•</span> = abnormal earlier in the last 12 h · '
                'sparklines show 12 h (labs 72 h) · hover any row for time, reason and FHIR id</div>',
                unsafe_allow_html=True)
    systems = data.ORGAN_SYSTEMS
    for start in range(0, len(systems), 4):
        cols = st.columns(4)
        for col, system in zip(cols, systems[start:start + 4]):
            with col:
                st.markdown(panel_html(case, system, ref), unsafe_allow_html=True)
    st.markdown("##### Next 12 hours: medications and running infusions")
    st.plotly_chart(timeline_figure(case), width="stretch",
                    config={"displayModeBar": False})
    st.caption(case.get("med_administrations_note", ""))
