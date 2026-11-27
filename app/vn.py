"""Virtual-nurse mode: an admission or discharge review with a timer, a break prompt and a handoff note.

Version 1.1 layout, from the screen design review: what is already in the chart
sits in its own card, each checklist item says whether the chart covers it or the
bedside nurse must confirm it, and the review ends in a short note the virtual
nurse can copy to the bedside nurse. There are no camera or call buttons: those
belong to the telehealth system, not to the chart.

After 10 minutes the screen offers a break, because virtual nurses showed first
signs of cognitive fatigue 9.8 minutes into discharges and 11.9 minutes into
admissions (Khairat et al., JMIR Hum Factors 2025). The nurse can take the break
(the timer restarts) or snooze it for 2 minutes. The prompt appears on its own,
without waiting for a click. Virtual nurses reached 80.2% documentation
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
SNOOZE_S = 2 * 60


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
    items = [
        ("Identity and safety", "Two patient identifiers confirmed", "with the patient, over video", False),
        ("Identity and safety", "Code status", code["text"] + (" (from a diagnosis code)" if code["text"] == "DNR"
                                                               and code["source"].startswith("Not") else ""),
         code["text"] != "Not charted"),
        ("Identity and safety", "Allergies", allergy["text"] + "; ask the patient", not allergy["empty"]),
        ("Identity and safety", "Isolation and precautions", iso["text"], not iso["empty"]),
        ("Identity and safety", "Fall risk",
         f"Morse {_latest_text(case, 'fall_risk', ref)}; restraints {_latest_text(case, 'restraints', ref)}", True),
        ("Lines and devices", "Lines, tubes and devices", devices, devices != "none"),
        ("Medications", "Home medications reconciled",
         ", ".join(m["name"] for m in meds) if meds else "no home medication list in the chart", bool(meds)),
        ("Medications", "Infusions running", drip_text, True),
        ("Medications", "Doses due in the next 12 h", next_doses, bool(due)),
        ("Assessment", "Neuro baseline",
         f"GCS {_latest_text(case, 'gcs_total', ref)}; RASS {_latest_text(case, 'rass', ref)}", True),
        ("Assessment", "Skin and pressure injury risk",
         f"Braden {_latest_text(case, 'braden_total', ref)}; skin {_latest_text(case, 'skin_condition', ref)}", True),
        ("Assessment", "Intake and output", io_text, True),
        ("Assessment", "Most recent labs", f"last results at {data.fmt_time(last_lab, ref)}; pending orders are "
                                           "not in the demo data", bool(last_lab)),
    ]
    if kind == "Admission":
        items.append(("Assessment", "Diet and nutrition", _latest_text(case, "diet", ref),
                      not _latest_text(case, "diet", ref).startswith("not")))
    else:
        items.append(("Discharge", "Teaching and follow-up", "not in the demo data", False))
        items.append(("Discharge", "Lines to remove before transfer", devices, devices != "none"))
    return items


def _timer_html(start: float) -> str:
    return f"""<div style="font:600 1.6rem 'Source Sans Pro',system-ui,sans-serif;color:#888" id="vn-timer"></div>
<script>
const t0 = {start * 1000};
function tick() {{
  const s = Math.max(0, Math.floor((Date.now() - t0) / 1000));
  document.getElementById('vn-timer').textContent =
    String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0');
}}
tick(); setInterval(tick, 1000);
</script>"""


@st.fragment(run_every=15)
def _break_prompt(session_key: str) -> None:
    """Shows the break prompt once the review passes 10 minutes (or the snooze runs out), with no click needed."""
    vn = st.session_state.get(session_key)
    if not vn:
        return
    elapsed = time.time() - vn["start"]
    if elapsed < vn["prompt_at"]:
        return
    with st.container(border=True):
        st.markdown(f"☕ **{int(elapsed // 60)} minutes into this review.** A short break away from the screen is "
                    "suggested now. Virtual nurses showed first signs of cognitive fatigue 9.8 minutes into "
                    "discharges and 11.9 minutes into admissions (Khairat et al., JMIR Human Factors 2025).")
        c1, c2, _ = st.columns([1, 1, 3])
        if c1.button("Take a break now", key=f"{session_key}_break", type="primary"):
            events.log("toggle", target="break_taken", value=round(elapsed))
            vn["start"], vn["prompt_at"] = time.time(), BREAK_AFTER_S
            st.rerun(scope="app")
        if c2.button(f"Snooze {SNOOZE_S // 60} min", key=f"{session_key}_snooze"):
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


def render() -> None:
    import streamlit.components.v1 as components

    cases = data.available_cases()
    labels = {c: f"{c} · {data.patient_line(data.load_case(c))}" for c in cases}
    c1, c2, _ = st.columns([2.4, 2, 1.6], vertical_alignment="bottom")
    case_id = c1.selectbox("Patient", cases, format_func=labels.get, key="vn_case")
    kind = c2.radio("Review type", ["Admission", "Discharge"], horizontal=True, key="vn_kind")
    case = data.load_case(case_id)
    session_key = f"vn_{case_id}_{kind}"
    vn = st.session_state.setdefault(session_key, {"start": time.time(), "prompt_at": BREAK_AFTER_S})
    if st.session_state.get("log_context", {}).get("run_id") != "VN":
        st.session_state["log_context"] = {"run_id": "VN", "seed": ""}
    st.session_state["log_context"].update(view="vn", case_id=case_id, question_id="")

    items = checklist_items(case, kind)
    keys = [f"{session_key}_{i}" for i in range(len(items))]
    checked = [bool(st.session_state.get(k)) for k in keys]
    done = sum(checked)

    s1, s2, s3 = st.columns([1, 1, 2], vertical_alignment="center")
    with s1:
        st.caption(f"Virtual {kind.lower()} · time in review")
        components.html(_timer_html(vn["start"]), height=44)
    s2.metric("Checklist", f"{done} of {len(items)}", help="Items reviewed. Virtual nurses reached 80.2% "
              "documentation completeness in Khairat et al., SAGE Open Nursing 2025.")
    if s3.button("Restart timer and checklist"):
        del st.session_state[session_key]
        for k in keys:
            st.session_state.pop(k, None)
        st.rerun()
    _break_prompt(session_key)

    left, right = st.columns([2, 3], gap="large")
    with left, st.container(border=True):
        st.markdown("**Already in the chart**")
        rows = "".join(f"<div style='margin:0 0 6px'><span style='font-size:.78rem;opacity:.7'>{html.escape(n)}</span>"
                       f"<br>{html.escape(v)} <span style='font-size:.72rem;opacity:.6'>· {html.escape(src)}</span>"
                       "</div>" for n, v, src in chart_facts(case))
        st.markdown(rows, unsafe_allow_html=True)
        st.caption("From FHIR Observation (ED), MedicationStatement (ED) and Condition resources, so nothing is "
                   "typed twice. The demo has no allergy data.")
    with right:
        st.markdown(f"**{kind} checklist**")
        group = None
        for key, (grp, item, shows, covered) in zip(keys, items):
            if grp != group:
                group = grp
                st.markdown(f"<div style='font-size:.78rem;font-weight:700;letter-spacing:.04em;opacity:.7;"
                            f"margin-top:6px'>{html.escape(grp.upper())}</div>", unsafe_allow_html=True)
            tag = "from chart" if covered else "confirm with bedside nurse"
            st.checkbox(f"**{item}** — {shows} · *{tag}*", key=key,
                        on_change=lambda k=key, name=item: events.log("toggle", target=f"checked: {name}",
                                                                      value=int(bool(st.session_state.get(k)))))

    elapsed = time.time() - vn["start"]
    st.markdown("**Handoff note for the bedside nurse**")
    st.code(handoff_note(case, kind, items, checked, elapsed), language=None, wrap_lines=True)

    with st.expander("Show the NurseGlance view of this patient"):
        from app import glance
        glance.render(case)

    vn_rows = [r for r in st.session_state.get("events", []) if r["view"] == "vn"]
    if vn_rows:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=events.COLUMNS)
        writer.writeheader()
        writer.writerows(vn_rows)
        st.download_button(f"Download virtual-nurse log ({len(vn_rows)} events, CSV)", buf.getvalue(),
                           "virtual_nurse_events.csv", "text/csv")
    st.caption("The counter mirrors task completeness: virtual nurses reached 80.2% documentation completeness in "
               "Khairat et al., SAGE Open Nursing 2025.")
