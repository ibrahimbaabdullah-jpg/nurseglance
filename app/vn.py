"""Virtual-nurse mode: admission or discharge review checklist, session timer and break prompt.

The checklist is built from the same case file as the other views. A completeness
counter shows items reviewed out of total. After 10 minutes the app offers an
optional break, because virtual nurses showed first signs of cognitive fatigue
at 9.8 minutes into discharges and 11.9 minutes into admissions (Khairat et al.,
JMIR Hum Factors 2025). Virtual nurses reached 80.2% documentation completeness
in Khairat et al., SAGE Open Nursing 2025, which the counter echoes.
"""
from __future__ import annotations

import time

import streamlit as st

from app import data, events

BREAK_AFTER_S = 10 * 60


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


def checklist_items(case: dict, kind: str) -> list[tuple[str, str]]:
    """(item, what the data shows) pairs for an admission or discharge review."""
    ref = data.handoff(case)
    els = case["elements"]
    dnr = any((d.get("code") or "").replace(".", "") in ("Z66", "V4986") for d in case["diagnoses"])
    code = _latest_text(case, "code_status", ref)
    if dnr and code.startswith("not"):
        code = "DNR (from diagnosis code; not charted at the bedside)"
    lines = (els.get("lines") or {}).get("in_place", []) + (els.get("foley") or {}).get("in_place", []) \
        + (els.get("ventilation") or {}).get("in_place", []) + (els.get("dialysis") or {}).get("in_place", [])
    devices = "; ".join(f"{d['label']}{' day ' + str(d['day']) if d.get('day') else ''}" for d in lines) or "none"
    from app.timeline import timeline_rows
    _, drips = timeline_rows(case)   # every infusion running at handoff, one row per drug
    drip_text = "; ".join(f"{d['label']} {data.fmt_num(d.get('rate'))} {d.get('rate_unit') or ''}".strip()
                          for d in drips) or "none running"
    due = [m for m in case["med_administrations"] if m.get("relative") == "after_handoff"]
    next_doses = ", ".join(sorted({m["name"].split(" + ")[0] for m in due})[:6]) or "none in the next 12 h"
    labs = [o for o in case["observations"] if o["source"] == "labevents"]
    last_lab = max((o["t"] for o in labs), default=None)
    io = (f"in {_latest_text(case, 'intake_12h', ref).split(' (')[0]}, out "
          f"{_latest_text(case, 'output_12h', ref).split(' (')[0]}, net {_latest_text(case, 'net_12h', ref).split(' (')[0]} (12 h)")
    items = [
        ("Identity, allergies and code status", f"Code status: {code}. Allergies: not in FHIR demo"),
        ("Lines, tubes and devices", devices),
        ("Skin and pressure injury risk",
         f"Braden {_latest_text(case, 'braden_total', ref)}; skin {_latest_text(case, 'skin_condition', ref)}"),
        ("Fall risk and safety", f"Fall risk: {_latest_text(case, 'fall_risk', ref)}; "
                                 f"restraints: {_latest_text(case, 'restraints', ref)}"),
        ("Medications: infusions", drip_text),
        ("Medications: scheduled doses", next_doses),
        ("Labs: most recent results and pending", f"Last results at {data.fmt_time(last_lab, ref)}; "
                                                  "pending orders are not in the demo data"),
        ("Intake and output", io),
    ]
    if kind == "Admission":
        items.insert(1, ("Neuro baseline", f"GCS {_latest_text(case, 'gcs_total', ref)}; "
                                           f"RASS {_latest_text(case, 'rass', ref)}"))
        items.append(("Diet and nutrition", _latest_text(case, "diet", ref)))
    else:
        items.append(("Discharge teaching and follow-up", "Not in the demo data; confirm with the bedside nurse"))
        items.append(("Lines to remove before transfer", devices))
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


def render(case: dict) -> None:
    import streamlit.components.v1 as components

    ref = data.handoff(case)
    st.header("Virtual-nurse review")
    kind = st.radio("Review type", ["Admission", "Discharge"], horizontal=True, key="vn_kind")
    session_key = f"vn_{case['case_id']}_{kind}"
    vn = st.session_state.setdefault(session_key, {"start": time.time(), "break_dismissed": False})
    if "log_context" not in st.session_state:
        st.session_state["log_context"] = {"run_id": "VN", "seed": ""}
    st.session_state["log_context"].update(view="vn", case_id=case["case_id"], question_id="")

    items = checklist_items(case, kind)
    done = sum(bool(st.session_state.get(f"{session_key}_{i}")) for i in range(len(items)))
    elapsed = time.time() - vn["start"]

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        st.caption("Session time")
        components.html(_timer_html(vn["start"]), height=48)
    c2.metric("Completeness", f"{done}/{len(items)}", f"{done / len(items):.0%}", delta_color="off")
    with c3:
        if st.button("Restart timer and checklist"):
            del st.session_state[session_key]
            for i in range(len(items)):
                st.session_state.pop(f"{session_key}_{i}", None)
            st.rerun()
    st.progress(done / len(items))
    if elapsed >= BREAK_AFTER_S and not vn["break_dismissed"]:
        st.info("You've been reviewing for 10 minutes. Consider a short break. Virtual nurses showed first "
                "signs of cognitive fatigue at 9.8 minutes into discharges and 11.9 minutes into admissions "
                "(Khairat et al., JMIR Human Factors 2025).", icon="☕")
        if st.button("Dismiss"):
            vn["break_dismissed"] = True
            events.log("toggle", target="break_prompt_dismissed")
            st.rerun()

    st.markdown(f"**{data.patient_line(case)}** · {data.weight_text(case)} · {kind.lower()} review "
                f"at {ref:%H:%M}")
    for i, (item, shows) in enumerate(items):
        key = f"{session_key}_{i}"
        st.checkbox(f"**{item}** — {shows}", key=key,
                    on_change=lambda k=key, name=item: events.log("toggle", target=f"checked: {name}",
                                                                  value=int(bool(st.session_state.get(k)))))
    vn_rows = [r for r in st.session_state.get("events", []) if r["view"] == "vn"]
    if vn_rows:
        import csv
        import io
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=events.COLUMNS)
        writer.writeheader()
        writer.writerows(vn_rows)
        st.download_button(f"Download virtual-nurse log ({len(vn_rows)} events, CSV)", buf.getvalue(),
                           "virtual_nurse_events.csv", "text/csv")
    st.caption("The counter mirrors task completeness: virtual nurses reached 80.2% documentation "
               "completeness in Khairat et al., SAGE Open Nursing 2025. The break prompt appears on the "
               "next interaction after 10 minutes.")
