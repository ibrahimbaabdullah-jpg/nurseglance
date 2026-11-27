"""Virtual-nurse mode: an admission or discharge review with a timer, a break prompt and a handoff note.

Version 1.1 layout, from the screen design review: what is already in the chart
sits in its own card, each checklist item says whether the chart covers it or the
bedside nurse must confirm it, and the review ends in a short note the virtual
nurse can copy to the bedside nurse. There are no camera or call buttons: those
belong to the telehealth system, not to the chart.

A band under the top bar (version 1.2, as in the design mockup) shows the time in
the review. After 10 minutes it turns orange and offers a break, because in 75%
(22 of 29) of observed virtual-nurse encounters the first instance of cognitive fatigue
came 9.8 minutes into discharges and 11.9 minutes into admissions (Khairat et al.,
JMIR Hum Factors 2025). The nurse can take
the break (the timer restarts) or ask to be reminded in 5 minutes. The band changes
on its own, without waiting for a click. The patient's chart sits above the review,
in whichever view the top bar has chosen. Virtual nurses reached 80.2% documentation
completeness in Khairat et al., SAGE Open Nursing 2025, which the counter echoes.
"""
from __future__ import annotations

import csv
import html
import io
import time

import streamlit as st

from app import data, events
from app.timeline import timeline_rows

BREAK_AFTER_S = 10 * 60
SNOOZE_S = 5 * 60


def _latest_text(case: dict, eid: str, ref) -> str:
    el = case["elements"].get(eid) or {}
    if not el.get("has_data"):
        return "not charted" if el.get("mappable", True) else "not in FHIR demo"
    latest = el.get("latest") or {}
    value = latest.get("value_text") or data.fmt_num(latest.get("value"))
    unit = latest.get("unit") or ""
    if unit in ("points", "score"):
        unit = ""
    return f"{value} {unit}".strip() + f" ({data.fmt_time(latest.get('t'), ref)})"


def _devices(case: dict) -> str:
    els = case["elements"]
    lines = (els.get("lines") or {}).get("in_place", []) + (els.get("foley") or {}).get("in_place", []) \
        + (els.get("ventilation") or {}).get("in_place", []) + (els.get("dialysis") or {}).get("in_place", [])
    return "; ".join(f"{d['label']}{' day ' + str(d['day']) if d.get('day') else ''}" for d in lines) or "none"


def chart_facts(case: dict) -> list[tuple[str, str, str]]:
    """(name, value, source) for the 'already in the chart' card."""
    reason, code = data.reason_for_admission(case), data.code_status(case)
    allergy, iso = data.allergies(case), data.isolation(case)
    meds = data.home_meds(case)
    dx = [d for d in data.diagnoses_sorted(case) if data.dx_rank(d) == 0][:3]
    return [
        ("Reason for admission" if reason["kind"] == "chief_complaint" else "Diagnoses", reason["text"],
         "ED chief complaint" if reason["kind"] == "chief_complaint" else "first 3 billing codes"),
        ("Code status", code["text"], code["source"]),
        ("Allergies", allergy["text"], allergy["source"]),
        ("Isolation", iso["text"], iso["source"]),
        ("Home medications", (f"{len(meds)} on file: " + ", ".join(m["name"] for m in meds)) if meds
         else "None on file", "ED medication reconciliation" if meds else "no ED medication list for this admission"),
        ("Problem list", "; ".join(d["display"] for d in dx) or "none", f"{len(case['diagnoses'])} billing diagnoses"),
    ]


def checklist_items(case: dict, kind: str) -> list[tuple[str, str, str, bool]]:
    """(group, item, what the chart shows, covered by the chart) for an admission or discharge review."""
    ref = data.handoff(case)
    code, allergy, iso = data.code_status(case), data.allergies(case), data.isolation(case)
    _, drips = timeline_rows(case)   # every infusion running at handoff, one row per drug
    drip_text = "; ".join(f"{d['label']} {data.fmt_num(d.get('rate'))} {d.get('rate_unit') or ''}".strip()
                          for d in drips) or "none running"
    due = [m for m in case["med_administrations"] if m.get("relative") == "after_handoff"]
    next_doses = ", ".join(sorted({m["name"].split(" + ")[0] for m in due})[:6]) or "none in the next 12 h"
    meds = data.home_meds(case)
    labs = [o for o in case["observations"] if o["source"] == "labevents"]
    last_lab = max((o["t"] for o in labs), default=None)
    io_text = (f"in {_latest_text(case, 'intake_12h', ref).split(' (')[0]}, out "
               f"{_latest_text(case, 'output_12h', ref).split(' (')[0]}, net "
               f"{_latest_text(case, 'net_12h', ref).split(' (')[0]} (12 h)")
    devices = _devices(case)

    def charted(*eids: str) -> bool:
        """True when the chart has a value for at least one of these elements, so the item is 'from chart'."""
        return any((case["elements"].get(e) or {}).get("has_data") for e in eids)

    items = [
        ("Identity and safety", "Two patient identifiers confirmed", "with the patient, over video", False),
        ("Identity and safety", "Code status", code["text"] + (" (from a diagnosis code)" if code["text"] == "DNR"
                                                               and code["source"].startswith("Not") else ""),
         code["text"] != "Not charted"),
        ("Identity and safety", "Allergies", allergy["text"] + "; ask the patient", not allergy["empty"]),
        ("Identity and safety", "Isolation and precautions", iso["text"], not iso["empty"]),
        ("Identity and safety", "Fall risk",
         f"Morse {_latest_text(case, 'fall_risk', ref)}; restraints {_latest_text(case, 'restraints', ref)}",
         charted("fall_risk", "restraints")),
        ("Lines and devices", "Lines, tubes and devices", devices, devices != "none"),
        ("Medications", "Home medications reconciled",
         ", ".join(m["name"] for m in meds) if meds else "no home medication list in the chart", bool(meds)),
        ("Medications", "Infusions running", drip_text, True),
        ("Medications", "Doses due in the next 12 h", next_doses, bool(due)),
        ("Assessment", "Neuro baseline",
         f"GCS {_latest_text(case, 'gcs_total', ref)}; RASS {_latest_text(case, 'rass', ref)}",
         charted("gcs_total", "rass")),
        ("Assessment", "Skin and pressure injury risk",
         f"Braden {_latest_text(case, 'braden_total', ref)}; skin {_latest_text(case, 'skin_condition', ref)}",
         charted("braden_total", "skin_condition")),
        ("Assessment", "Intake and output", io_text, charted("intake_12h", "output_12h")),
        ("Assessment", "Most recent labs", f"last results at {data.fmt_time(last_lab, ref)}; pending orders are "
                                           "not in the demo data", bool(last_lab)),
    ]
    if kind == "Admission":
        items.append(("Assessment", "Diet and nutrition", _latest_text(case, "diet", ref), charted("diet")))
    else:
        items.append(("Discharge", "Teaching and follow-up", "not in the demo data", False))
        items.append(("Discharge", "Lines to remove before transfer", devices, devices != "none"))
    return items


CLOCK = ('<svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="#16212B" '
         'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="13" r="8"></circle>'
         '<path d="M12 9v4l2.5 2.5"></path><path d="M9 2h6"></path></svg>')

BANNER_CSS = """<style>
.st-key-ng-vnbar {padding:12px 28px; background:#E8F1F7; border-bottom:1px solid #C7DBE8;
  gap:12px 20px !important; flex-wrap:nowrap !important; min-height:60px;}
.st-key-ng-vnbar > div:has(.ng-vn-note) {min-width:0; flex:1 1 auto !important;}
@media (max-width: 900px) {.st-key-ng-vnbar {flex-wrap:wrap !important;}}
.st-key-ng-vnbar.ng-due, .st-key-ng-vnbar:has(.ng-vn-due) {background:#FFF1E3; border-bottom-color:#F3D3B5;}
.ng-vn-head {display:flex; align-items:center; gap:10px; white-space:nowrap; font-family:Inter, system-ui, sans-serif;
  color:#16212B;}
.ng-vn-head strong {font-size:14px; font-weight:600;}
.ng-vn-time {font-size:14px; font-weight:700; color:#16212B; background:#FFFFFF; border:1px solid #C7DBE8;
  padding:3px 8px; border-radius:6px; font-variant-numeric:tabular-nums;}
.ng-vn-note {font-size:14px; color:#2A3640; font-family:Inter, system-ui, sans-serif; line-height:1.35;}
.ng-vn-note small {color:#5A6671; font-size:12px; white-space:nowrap;}
.st-key-ng-vnbar button {min-height:40px; padding:0 14px; border-radius:8px; font-size:14px; font-weight:600;}
.st-key-ng-vnbar button[kind="secondary"] {border:1px solid #9FBDD2; background:#FFFFFF; color:#16212B;}
.st-key-ng-vnbar button p {font-size:14px; font-weight:600;}
.ng-vn-facts {display:flex; flex-direction:column; gap:9px; font-family:Inter, system-ui, sans-serif;}
.ng-vn-facts div {display:flex; flex-direction:column; gap:2px; padding-top:8px; border-top:1px solid #EEF1F3;}
.ng-vn-facts div:first-child {border-top:0; padding-top:0;}
.ng-vn-facts span {font-size:12px; color:#5A6671;}
.ng-vn-facts b {font-size:14px; font-weight:600; color:#16212B; line-height:1.35;}
.ng-vn-facts small {font-size:11.5px; color:#5A6671;}
.ng-vn-group {font-size:11px; font-weight:600; letter-spacing:.06em; text-transform:uppercase; color:#5A6671;
  margin:6px 0 0;}
.ng-vn-h {font-family:'Space Grotesk', Inter, sans-serif; font-size:16px; font-weight:600; margin:0; color:#16212B;}
</style>"""


def _elapsed_html(start: float, due: bool) -> str:
    """The elapsed time, ticking in the browser between reruns."""
    uid = f"vn-t-{int(start * 1000)}"
    from app.ui import svg_img
    return (f'<div class="ng-vn-head{" ng-vn-due" if due else ""}">{svg_img(CLOCK)}<strong>{{title}}</strong>'
            f'<span class="ng-vn-time"><span id="{uid}">00:00</span> elapsed</span></div>'
            f'<script>(function(){{const t0={start * 1000:.0f};const tick=()=>{{const el=document.getElementById("{uid}");'
            f'if(!el){{clearInterval(h);return;}}const s=Math.max(0,Math.floor((Date.now()-t0)/1000));'
            f'el.textContent=String(Math.floor(s/60)).padStart(2,"0")+":"+String(s%60).padStart(2,"0");}};'
            f'const h=setInterval(tick,1000);tick();}})();</script>')


@st.fragment(run_every=15)
def _banner(session_key: str, kind: str) -> None:
    """The session band under the top bar: elapsed time, the fatigue note, and the break controls.

    It turns from blue to orange on its own once the review passes 10 minutes (or the reminder runs out).
    """
    vn = st.session_state.get(session_key)
    if not vn:
        return
    elapsed = time.time() - vn["start"]
    due = elapsed >= vn["prompt_at"]
    with st.container(key="ng-vnbar", horizontal=True, vertical_alignment="center"):
        st.html(BANNER_CSS + _elapsed_html(vn["start"], due).replace("{title}", f"Virtual {kind.lower()} session"),
                width="content", unsafe_allow_javascript=True)
        if due:
            note = (f"<b>{int(elapsed // 60)} minutes into this review.</b> Plan a short break away from the "
                    "workstation now.")
        else:
            note = ("In 22 of 29 observed virtual-nurse encounters, the first sign of fatigue came 9.8 min into "
                    "discharges and 11.9 min into admissions. Plan a short break away from the workstation.")
        st.html(f'<span class="ng-vn-note" title="Eye tracking of virtual nurses: 75% (22 of 29) of encounters showed '
                f'a first instance of cognitive fatigue (pupil size) at 9.8 minutes during discharges and 11.9 minutes '
                f'during admissions">{note} <small>Khairat et al., JMIR Hum Factors 2025</small></span>',
                width="stretch")
        if due and st.button("Take a break now", key=f"{session_key}_break", type="primary"):
            events.log("toggle", target="break_taken", value=round(elapsed))
            vn["start"], vn["prompt_at"] = time.time(), BREAK_AFTER_S
            st.rerun(scope="app")
        if st.button(f"Remind me in {SNOOZE_S // 60} min", key=f"{session_key}_snooze"):
            events.log("toggle", target="break_snoozed", value=round(elapsed))
            vn["prompt_at"] = elapsed + SNOOZE_S
            st.rerun(scope="fragment")


def handoff_note(case: dict, kind: str, items, checked: list[bool], elapsed: float) -> str:
    ref = data.handoff(case)
    reason = data.reason_for_admission(case)
    done = sum(checked)
    lines = [f"Virtual {kind.lower()} review · {case['case_id']} · {data.patient_line(case)} · "
             f"chart as of {ref:%H:%M}",
             f"{'Reason for admission' if reason['kind'] == 'chief_complaint' else 'Diagnoses'}: {reason['text']}",
             f"Reviewed {done} of {len(items)} items in {int(elapsed // 60):02d}:{int(elapsed % 60):02d}.", ""]
    reviewed = [f"- {item}: {shows}" for (_, item, shows, _), c in zip(items, checked) if c]
    open_ = [f"- {item}" + ("" if covered else " (not in the chart)")
             for (_, item, _, covered), c in zip(items, checked) if not c]
    if reviewed:
        lines += ["Reviewed:"] + reviewed + [""]
    if open_:
        lines += ["Still to confirm with the bedside nurse:"] + open_
    return "\n".join(lines)


def render(patient_view, footer=None) -> None:
    """Banner, patient and review type, the patient's chart in the chosen view, then the review itself.

    patient_view(case_id, show_flags) draws the chart exactly as the Handoff page does; footer() ends the page.
    """
    cases = data.available_cases()
    case_id = st.session_state.get("vn_case") or cases[0]
    kind = st.session_state.get("vn_kind") or "Admission"
    session_key = f"vn_{case_id}_{kind}"
    vn = st.session_state.setdefault(session_key, {"start": time.time(), "prompt_at": BREAK_AFTER_S})
    if st.session_state.get("log_context", {}).get("run_id") != "VN":
        st.session_state["log_context"] = {"run_id": "VN", "seed": ""}
    st.session_state["log_context"].update(view="vn", case_id=case_id, question_id="")
    _banner(session_key, kind)

    items = checklist_items(data.load_case(case_id), kind)
    keys = [f"{session_key}_{i}" for i in range(len(items))]
    checked = [bool(st.session_state.get(k)) for k in keys]
    with st.container(key="ng-main"):
        with st.container(key="ng-ctx", horizontal=True, vertical_alignment="center"):
            st.html('<span class="ng-ctx-label">Patient</span>', width="content")
            st.segmented_control("Patient", cases, default=cases[0], required=True, key="vn_case",
                                 format_func=lambda c: f"{c} · {'Standard' if c.startswith('S') else 'Complex'}",
                                 label_visibility="collapsed")
            st.html('<span class="ng-ctx-label">Review</span>', width="content")
            st.segmented_control("Review type", ["Admission", "Discharge"], default="Admission", required=True,
                                 key="vn_kind", label_visibility="collapsed")
            st.space("stretch")
            show = st.toggle("Rule-based flags", key="vn_flags")
        patient_view(case_id, show)
        review(data.load_case(case_id), kind, session_key, vn, items, keys, checked)
        if footer:
            footer()


def review(case: dict, kind: str, session_key: str, vn: dict, items, keys, checked) -> None:
    """What the chart already holds, the checklist, and the note for the bedside nurse."""
    done = sum(checked)
    with st.container(key="ng-card-vnhead", horizontal=True, vertical_alignment="center"):
        st.html(f'<p class="ng-vn-h">Virtual {kind.lower()} review · {done} of {len(items)} items checked</p>',
                width="stretch")
        if st.button("Restart timer and checklist", key="vn_restart", type="tertiary"):
            del st.session_state[session_key]
            for k in keys:
                st.session_state.pop(k, None)
            st.rerun()
    left, right = st.columns([2, 3], gap="medium")
    with left, st.container(key="ng-card-vnfacts"):
        st.html('<p class="ng-vn-h">Already in the chart</p>')
        rows = "".join(f"<div><span>{html.escape(n)}</span><b>{html.escape(v)}</b><small>{html.escape(src)}</small>"
                       "</div>" for n, v, src in chart_facts(case))
        st.html(f'<div class="ng-vn-facts">{rows}</div>')
        st.caption("From FHIR Observation (ED), MedicationStatement (ED) and Condition resources, so nothing is "
                   "typed twice. The demo has no allergy data.")
    with right, st.container(key="ng-card-vncheck"):
        st.html(f'<p class="ng-vn-h">{kind} checklist</p>')
        group = None
        for key, (grp, item, shows, covered) in zip(keys, items):
            if grp != group:
                group = grp
                st.html(f'<p class="ng-vn-group">{html.escape(grp)}</p>')
            tag = "from chart" if covered else "confirm with bedside nurse"
            st.checkbox(f"**{item}** — {shows} · *{tag}*", key=key,
                        on_change=lambda k=key, name=item: events.log("toggle", target=f"checked: {name}",
                                                                      value=int(bool(st.session_state.get(k)))))
    elapsed = time.time() - vn["start"]
    with st.container(key="ng-card-vnnote"):
        st.html('<p class="ng-vn-h">Handoff note for the bedside nurse</p>')
        st.code(handoff_note(case, kind, items, checked, elapsed), language=None, wrap_lines=True)
        vn_rows = [r for r in st.session_state.get("events", []) if r["view"] == "vn"]
        if vn_rows:
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=events.COLUMNS)
            writer.writeheader()
            writer.writerows(vn_rows)
            st.download_button(f"Download virtual-nurse log ({len(vn_rows)} events, CSV)", buf.getvalue(),
                               "virtual_nurse_events.csv", "text/csv")
        st.caption("The checklist count mirrors task completeness: virtual nurses reached 80.2% documentation "
                   "completeness in Khairat et al., SAGE Open Nursing 2025.")
