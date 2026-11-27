"""Control view: a deliberately conventional, tabbed EHR-style layout of the same case data.

Tabs are Summary, Flowsheet, Labs, MAR, Problems and Lines & drains, like a typical
ICU EHR (version 1.1; before that: Vitals, Labs, Meds, Notes/Problems). The demo
has no nursing notes, so there is no Notes tab. A patient banner carries code
status, allergies and isolation, as an EHR's header does, so both views show the
same safety facts and the comparison stays about layout.
The tab bar is a radio control rather than st.tabs so that each tab change is a
real interaction the study mode can count as a click and a screen visit.

Version 0.3 makes the control closer to a current EHR, so the comparison is not
against a straw man (docs/heuristic_evaluation.md): flowsheet and lab columns run
newest first, so the latest values sit next to the labels; calculated scores (GCS
total, Braden, Morse) and shift totals sit in the flowsheet group where nurses
chart their parts; running infusions are listed first; upcoming doses lead the
MAR; and columns have readable names.
"""
from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

from app import data
from app.events import on_change_logger

TABS = ["Summary", "Flowsheet", "Labs", "MAR", "Problems", "Lines & drains"]
MAR_SECTIONS = ["Doses", "Infusions", "Active orders", "Home meds"]


# Calculated values (built by the ETL) go where an EHR flowsheet would show them.
DERIVED_HOME = {
    "GCS_TOTAL": ("Neurological", "GCS Total"),
    "BRADEN_TOTAL": ("Skin - Assessment", "Braden Score"),
    "MORSE_TOTAL": ("Restraint/Support Systems", "Morse Fall Score"),
    "TEMP_C": ("Routine Vital Signs", "Temperature (°C, calculated)"),
    "UO_6H": ("Output", "Urine Output, last 6 h"),
    "UO_RATE_6H": ("Output", "Urine Output Rate, last 6 h"),
    "INTAKE_12H": ("Output", "Intake, last 12 h"),
    "OUTPUT_12H": ("Output", "Output, last 12 h"),
    "NET_12H": ("Output", "Net Balance, last 12 h"),
}


def _obs_frame(case: dict) -> pd.DataFrame:
    df = pd.DataFrame(case["observations"])
    if df.empty:
        return df
    for item, (category, label) in DERIVED_HOME.items():
        mask = df["item_id"] == item
        df.loc[mask, "category"] = category
        df.loc[mask, "label"] = label
    df["t"] = pd.to_datetime(df["t"])
    df = df[df["t"] <= data.handoff(case)]
    df["shown"] = df["value_text"].where(df["value_text"].notna(),
                                         df["value"].map(data.fmt_num))
    return df


def _pivot(df: pd.DataFrame, value_col: str = "shown") -> pd.DataFrame:
    df = df.copy()
    df["time"] = df["t"].dt.strftime("%m-%d %H:%M")
    table = df.pivot_table(index="label", columns="time", values=value_col,
                           aggfunc="last")
    table.index.name = "Item"
    return table.reindex(sorted(table.columns, reverse=True), axis=1).fillna("")   # newest first


def vitals_tab(case: dict, df: pd.DataFrame) -> None:
    ref = data.handoff(case)
    chart = df[(df["source"] != "labevents") & (df["t"] >= ref - timedelta(hours=24))]
    groups = sorted(chart["category"].dropna().unique())
    default = groups.index("Routine Vital Signs") if "Routine Vital Signs" in groups else 0
    key = f"fs_{case['case_id']}"
    group = st.selectbox("Flowsheet section", groups, index=default, key=key,
                         on_change=on_change_logger(key, "toggle", "Flowsheet: "))
    st.caption("Flowsheet, last 24 h before handoff. Newest column first.")
    st.dataframe(_pivot(chart[chart["category"] == group]), width="stretch", height=420)


def labs_tab(case: dict, df: pd.DataFrame) -> None:
    labs = df[df["source"] == "labevents"].copy()
    if labs.empty:
        st.info("No lab results in the last 72 h.")
        return
    flags = labs.apply(lambda r: data.lab_flag(r.to_dict()), axis=1)
    labs["shown"] = labs["shown"] + flags.map(lambda f: f" ({f})" if f else "")
    st.caption("Results, last 72 h before handoff, newest column first. "
               "(H)/(L) = outside the result's reference range.")
    st.dataframe(_pivot(labs), width="stretch", height=460)


def meds_tab(case: dict) -> None:
    ref = data.handoff(case)
    key = f"meds_{case['case_id']}"
    section = st.radio("Section", MAR_SECTIONS, horizontal=True, key=key,
                       on_change=on_change_logger(key, "toggle", "MAR: "))
    if section == "Home meds":
        meds = data.home_meds(case)
        if not meds:
            st.info("No home medication list for this admission. The demo has one only when the patient came "
                    "through the emergency department and the ED reconciled medications.")
            return
        table = pd.DataFrame([{"Medication": m["name"], "Recorded": data.fmt_time(m["t"], ref),
                               "Source": "ED medication reconciliation"} for m in meds])
        st.dataframe(table, width="stretch", hide_index=True)
        return
    if section == "Doses":
        mar = pd.DataFrame(case["med_administrations"])
        if mar.empty:
            st.info("No eMAR entries in this window.")
            return
        mar["time"] = pd.to_datetime(mar["t"]).dt.strftime("%m-%d %H:%M")
        mar["when"] = mar["relative"].map({"before_handoff": "Given (24 h before)",
                                           "after_handoff": "Next 12 h"})
        mar["dose"] = mar.apply(lambda r: f"{data.fmt_num(r['dose'])} {r['dose_unit'] or ''}"
                                if pd.notna(r["dose"]) else "", axis=1)
        st.caption(case.get("med_administrations_note", "") + " Upcoming doses first, then doses given, newest first.")
        st.dataframe(mar_table(mar), width="stretch", hide_index=True, height=420)
    elif section == "Infusions":
        inf = pd.DataFrame(case["infusions"])
        if inf.empty:
            st.info("No infusions in this window.")
            return
        inf = inf[pd.to_datetime(inf["start"]) <= ref]
        for col in ("start", "end"):
            inf[col] = pd.to_datetime(inf[col]).dt.strftime("%m-%d %H:%M")
        inf["rate"] = inf.apply(lambda r: f"{data.fmt_num(r['rate'])} {r['rate_unit'] or ''}"
                                if pd.notna(r["rate"]) else "", axis=1)
        inf["amount"] = inf.apply(lambda r: f"{data.fmt_num(r['dose'])} {r['dose_unit'] or ''}", axis=1)
        st.caption("Infusions running at handoff first, then earlier rates, newest first.")
        st.dataframe(infusions_table(inf), width="stretch", hide_index=True, height=420)
    else:
        orders = pd.DataFrame(case["med_orders_active"])
        if orders.empty:
            st.info("No medication orders in this window.")
            return
        for col in ("start", "end"):
            orders[col] = pd.to_datetime(orders[col]).dt.strftime("%m-%d %H:%M")
        orders = orders[["name", "route", "frequency", "dose", "dose_unit", "start", "end", "status"]]
        orders.columns = ["Medication", "Route", "Frequency", "Dose", "Unit", "Start", "End", "Status"]
        st.dataframe(orders, width="stretch", hide_index=True, height=420)


def mar_table(mar: pd.DataFrame) -> pd.DataFrame:
    """Upcoming doses in time order, then doses already given, newest first."""
    upcoming = mar[mar["relative"] == "after_handoff"].sort_values("time", kind="stable")
    given = mar[mar["relative"] != "after_handoff"].sort_values("time", ascending=False, kind="stable")
    out = pd.concat([upcoming, given])[["time", "when", "name", "dose", "event", "status"]]
    out.columns = ["Time", "When", "Medication", "Dose", "Event", "Status"]
    return out


def infusions_table(inf: pd.DataFrame) -> pd.DataFrame:
    """Running infusions first (by name), then the rest, newest start first."""
    running = inf[inf["running_at_handoff"] == True].sort_values("label", kind="stable")  # noqa: E712
    rest = inf[inf["running_at_handoff"] != True].sort_values("start", ascending=False, kind="stable")  # noqa: E712
    out = pd.concat([running, rest])[["start", "end", "label", "category", "rate", "amount", "running_at_handoff"]]
    out.columns = ["Start", "End", "Infusion", "Category", "Rate", "Amount", "Running at handoff"]
    return out


def _fit(n_rows: int) -> int:
    """Table height that shows every row with no inner scroll bar (35 px rows plus the header)."""
    return 35 * (n_rows + 1) + 3


def summary_tab(case: dict) -> None:
    """Latest vital signs, running infusions and 12-hour intake and output, as an EHR summary shows them.

    Every table shows all its rows: a summary that hides a running drip behind a scroll bar
    would be a weaker control than a real EHR's summary screen.
    """
    ref = data.handoff(case)
    rows = []
    for eid in ("heart_rate", "heart_rhythm", "sbp", "map", "resp_rate", "spo2", "o2_device", "temperature"):
        el = case["elements"].get(eid) or {}
        latest = el.get("latest") or {}
        if not el.get("has_data"):
            continue
        value = latest.get("value_text") or data.fmt_num(latest.get("value"))
        rows.append({"Vital sign": el["label"], "Latest": f"{value} {latest.get('unit') or ''}".strip(),
                     "Time": data.fmt_time(latest.get("t"), ref)})
    left, right = st.columns([1, 1], gap="large")
    with left:
        st.markdown("**Latest vital signs**")
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True, height=_fit(len(rows)))
    with right:
        from app.timeline import timeline_rows
        _, running = timeline_rows(case)
        st.markdown("**Infusions running at handoff**")
        if running:
            st.dataframe(pd.DataFrame([{"Infusion": r["label"],
                                        "Rate": f"{data.fmt_num(r.get('rate'))} {r.get('rate_unit') or ''}".strip(),
                                        "Since": data.fmt_time(r.get("start"), ref)} for r in running]),
                         width="stretch", hide_index=True, height=_fit(len(running)))
        else:
            st.caption("None running.")
        st.markdown("**Intake and output, last 12 h**")
        io = []
        for eid, name in (("intake_12h", "Intake"), ("output_12h", "Output"), ("net_12h", "Net")):
            latest = (case["elements"].get(eid) or {}).get("latest") or {}
            io.append({"": name, "mL": data.fmt_num(latest.get("value")) if latest else "–"})
        st.dataframe(pd.DataFrame(io), width="content", hide_index=True)


def problems_tab(case: dict) -> None:
    reason = data.reason_for_admission(case)
    if reason["kind"] == "chief_complaint":
        st.markdown(f"**Reason for admission:** {reason['text']}  \n"
                    f"<span style='opacity:.75;font-size:.85rem'>{reason['source']}</span>", unsafe_allow_html=True)
    else:
        st.markdown("**Reason for admission:** no ED chief complaint for this admission.")
    st.markdown("**Problem list** (hospital billing diagnoses; FHIR carries no billing priority)")
    dx = pd.DataFrame(case["diagnoses"])
    if not dx.empty:
        dx = dx[["code", "display", "version"]]
        dx.columns = ["Code", "Diagnosis", "Version"]
        st.dataframe(dx, width="stretch", hide_index=True, height=380)


def lines_tab(case: dict) -> None:
    ref = data.handoff(case)
    dev = pd.DataFrame(case["devices"])
    if dev.empty:
        st.info("No lines, drains or devices charted for this stay.")
        return
    dev = dev[pd.to_datetime(dev["start"]) <= ref].copy()
    dev["Removed"] = [data.fmt_time(e, ref) if e and data.ts(e) <= ref else ""
                      for e in dev["end"]]   # nothing after handoff: the nurse could not know it yet
    dev["Inserted"] = pd.to_datetime(dev["start"]).dt.strftime("%m-%d %H:%M")
    for col in ("site", "day"):
        dev[col] = dev[col].map(lambda v: "" if v is None or (isinstance(v, float) and pd.isna(v)) else v)
    lines = dev[dev["is_line_or_device"] == True].copy()   # noqa: E712
    lines["order"] = lines["in_place_at_handoff"].map(lambda v: 0 if v else 1)
    lines = lines.sort_values(["order", "start"], ascending=[True, False], kind="stable")
    table = lines[["label", "category", "site", "day", "Inserted", "Removed", "in_place_at_handoff"]]
    table.columns = ["Line, drain or device", "Category", "Site", "Day", "Inserted", "Removed", "In place at handoff"]
    st.caption("In place at handoff first.")
    st.dataframe(table, width="stretch", hide_index=True)
    procs = dev[dev["is_line_or_device"] != True].sort_values("start", ascending=False)   # noqa: E712
    if not procs.empty:
        st.markdown("**Procedures and imaging in this stay, before handoff**")
        procs = procs[["label", "category", "Inserted"]]
        procs.columns = ["Procedure", "Category", "Time"]
        st.dataframe(procs, width="stretch", hide_index=True)


def banner(case: dict) -> None:
    """The patient banner an EHR keeps above every tab."""
    ref = data.handoff(case)
    code, allergy, iso = data.code_status(case), data.allergies(case), data.isolation(case)
    code_text = code["text"] + (" (diagnosis code)" if code["text"] == "DNR" and
                                code["source"].startswith("Not charted") else "")
    st.markdown(f"**{data.patient_line(case)}** · {data.weight_text(case)} · handoff {ref:%Y-%m-%d %H:%M}  \n"
                f"<span style='font-size:.86rem'>Code status: <b>{code_text}</b> · Allergies: <b>{allergy['text']}"
                f"</b> · Isolation: <b>{iso['text']}</b></span>", unsafe_allow_html=True)


def render(case: dict) -> None:
    banner(case)
    key = f"tab_{case['case_id']}"
    tab = st.radio("Chart tab", TABS, horizontal=True, key=key, label_visibility="collapsed",
                   on_change=on_change_logger(key, "tab_switch", ""))
    st.divider()
    df = _obs_frame(case)
    if tab == "Summary":
        summary_tab(case)
    elif tab == "Flowsheet":
        vitals_tab(case, df)
    elif tab == "Labs":
        labs_tab(case, df)
    elif tab == "MAR":
        meds_tab(case)
    elif tab == "Problems":
        problems_tab(case)
    else:
        lines_tab(case)
