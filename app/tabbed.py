"""Control view: a deliberately conventional, tabbed EHR-style layout of the same case data.

Tabs are Vitals (flowsheet), Labs, Meds and Notes/Problems, like a typical EHR.
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

TABS = ["Vitals", "Labs", "Meds", "Notes/Problems"]


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
    group = st.selectbox("Flowsheet group", groups, index=default, key=key,
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
    section = st.radio("Section", ["MAR", "Infusions", "Active orders"], horizontal=True, key=key,
                       on_change=on_change_logger(key, "toggle", "Meds: "))
    if section == "MAR":
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


def notes_tab(case: dict) -> None:
    ref = data.handoff(case)
    st.markdown("**Problem list** (hospital billing diagnoses)")
    dx = pd.DataFrame(case["diagnoses"])
    if not dx.empty:
        dx = dx[["code", "display", "version"]]
        dx.columns = ["Code", "Diagnosis", "Version"]
        st.dataframe(dx, width="stretch", hide_index=True, height=240)
    st.markdown("**Lines, devices and procedures**")
    dev = pd.DataFrame(case["devices"])
    if not dev.empty:
        dev = dev[pd.to_datetime(dev["start"]) <= ref]
        for col in ("start", "end"):
            dev[col] = pd.to_datetime(dev[col]).dt.strftime("%m-%d %H:%M")
        dev = dev[["label", "category", "site", "start", "end", "in_place_at_handoff"]]
        dev.columns = ["Device", "Category", "Site", "Start", "End", "In place at handoff"]
        st.dataframe(dev, width="stretch", hide_index=True)
    st.caption("The MIMIC-IV demo has no free-text nursing notes, so this tab shows problems and devices.")


def render(case: dict) -> None:
    ref = data.handoff(case)
    st.markdown(f"**{data.patient_line(case)}** · {data.weight_text(case)} · "
                f"handoff {ref:%Y-%m-%d %H:%M}")
    key = f"tab_{case['case_id']}"
    tab = st.radio("Chart tab", TABS, horizontal=True, key=key, label_visibility="collapsed",
                   on_change=on_change_logger(key, "tab_switch", ""))
    st.divider()
    df = _obs_frame(case)
    if tab == "Vitals":
        vitals_tab(case, df)
    elif tab == "Labs":
        labs_tab(case, df)
    elif tab == "Meds":
        meds_tab(case)
    else:
        notes_tab(case)
