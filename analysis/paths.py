"""The shortest path to each study answer, in each view (the task analysis).

Each question has one path per view: the fewest clicks, then the fewest scrolls,
needed to see the data the answer key names. Paths run in study order, so a path
starts wherever the previous question of the same case left the view (the tabbed
view remembers its tab, flowsheet group and Meds section for each patient).
Leaving a tab resets its controls: Meds reopens on MAR and Vitals on Routine
Vital Signs (Streamlit drops the state of widgets that are not on screen).
Every question starts with the page and its tables scrolled to the top-left.

Step types
  tabbed:  tab, group (flowsheet group selectbox), section (Meds radio),
           grid (make rows visible and cover columns in the table on screen)
  glance:  see (a row or list item is in view and shows the value),
           hover (read a row's tooltip or a timeline dose's hover label)
  both:    think (extra mental steps beyond reading a value, with the reason)

Grid columns: "last" = the row's most recent value; "window" = the first and last
values in the 12 h before handoff (scanning passes every value between them);
"find:<text>" = the cell that starts with <text>.
"""
from __future__ import annotations


def tab(name):
    return {"do": "tab", "name": name}


def group(name):
    return {"do": "group", "name": name}


def section(name):
    return {"do": "section", "name": name}


def grid(rows, cols=("last",), table=None):
    """rows: labels (pivot tables) or lists of strings a row must contain (MAR, infusions)."""
    return {"do": "grid", "rows": list(rows), "cols": list(cols), "table": table}


def think(n, why):
    return {"do": "think", "n": n, "why": why}


def see_row(label, expect):
    return {"do": "see", "kind": "row", "label": label, "expect": expect}


def see_li(text, expect):
    return {"do": "see", "kind": "li", "text": text, "expect": expect}


def see_tick(text):
    return {"do": "see", "kind": "ytick", "text": text, "expect": text}


def hover_row(label, expect):
    return {"do": "hover", "kind": "row", "label": label, "expect": expect}


def hover_dose(name, expect):
    return {"do": "hover", "kind": "dose", "name": name, "expect": expect}


RUNNING = "True"   # the infusions table's running_at_handoff column

PATHS: dict[str, dict[str, list[dict]]] = {
    # ---------------------------------------------------------------- S1
    "S1-Q1": {
        "tabbed": [tab("Labs"), grid(["Potassium"], ["last"], "labs")],
        "glance": [see_row("Potassium", "3.2")],
    },
    "S1-Q2": {
        "tabbed": [tab("Vitals"), grid(["Heart Rate"], ["window"], "vitals"),
                   think(1, "compare the first and last heart rates of the 12 h window")],
        "glance": [see_row("Heart rate", "↓")],
    },
    "S1-Q3": {
        "tabbed": [tab("Meds"), grid([["oxycodone", "21:37"]], table="mar")],
        "glance": [hover_dose("OxyCODONE", "21:37")],
    },
    "S1-Q4": {   # bleeding risk on heparin, with one value (rubric score 2)
        "tabbed": [section("Infusions"), grid([["Heparin", RUNNING]], table="infusions"),
                   tab("Labs"), grid(["Hemoglobin"], ["last"], "labs")],
        "glance": [see_row("Hemoglobin", "9.3"), see_tick("Heparin Sodium")],
    },
    # ---------------------------------------------------------------- S2
    "S2-Q1": {
        "tabbed": [group("Neurological"),
                   grid(["GCS - Eye Opening", "GCS - Motor Response", "GCS - Verbal Response"],
                        ["last"], "vitals"),
                   think(1, "add eye, verbal and motor scores")],
        "glance": [see_row("GCS total", "15")],
    },
    "S2-Q2": {
        "tabbed": [group("Routine Vital Signs"),
                   grid(["ART BP Mean", "Arterial Blood Pressure mean"], ["window"], "vitals"),
                   think(2, "find the lowest of about 13 values in each of two MAP rows, then compare")],
        "glance": [hover_row("Mean arterial pressure", "range 63")],
    },
    "S2-Q3": {
        "tabbed": [tab("Meds"), grid([["nimodipine", "10:50"]], table="mar")],
        "glance": [hover_dose("NiMODipine", "10:50")],
    },
    "S2-Q4": {   # neuro decline after SAH: GCS now and the MAP dip
        "tabbed": [tab("Vitals"),
                   grid(["ART BP Mean", "Arterial Blood Pressure mean"], ["window"], "vitals"),
                   think(2, "find the lowest MAP in two rows, then compare"),
                   group("Neurological"),
                   grid(["GCS - Eye Opening", "GCS - Motor Response", "GCS - Verbal Response"],
                        ["last"], "vitals"),
                   think(1, "add eye, verbal and motor scores")],
        "glance": [see_row("GCS total", "15"), hover_row("Mean arterial pressure", "range 63")],
    },
    # ---------------------------------------------------------------- C1
    "C1-Q1": {
        "tabbed": [tab("Meds"), section("Infusions"),
                   grid([["Norepinephrine", RUNNING]], table="infusions")],
        "glance": [see_li("Norepinephrine", "0.2")],
    },
    "C1-Q2": {
        "tabbed": [tab("Labs"), grid(["Lactate"], ["window"], "labs"),
                   think(1, "compare the first and last lactates of the 12 h window")],
        "glance": [see_row("Lactate", "↓")],
    },
    "C1-Q3": {
        "tabbed": [tab("Meds"), grid([["vancomycin", "01:01"]], table="mar")],   # Meds reopens on MAR
        "glance": [hover_dose("Vancomycin", "01:01")],
    },
    "C1-Q4": {   # hemodynamic instability: MAP, both pressors, lactate
        "tabbed": [section("Infusions"),
                   grid([["Norepinephrine", RUNNING], ["Vasopressin", RUNNING]], table="infusions"),
                   tab("Labs"), grid(["Lactate"], ["last"], "labs"),
                   tab("Vitals"), grid(["Arterial Blood Pressure mean"], ["last"], "vitals")],
        "glance": [see_row("Mean arterial pressure", "64"), see_li("Norepinephrine", "0.2"),
                   see_li("Vasopressin", "units"), see_row("Lactate", "4.3")],
    },
    # ---------------------------------------------------------------- C2
    "C2-Q1": {
        "tabbed": [grid(["Heart Rate"], ["last"], "vitals")],
        "glance": [see_row("Heart rate", "130")],
    },
    "C2-Q2": {
        "tabbed": [tab("Meds"), section("Infusions"),
                   grid([["Norepinephrine", "03-26 06:30"], ["Norepinephrine", RUNNING]], table="infusions"),
                   think(1, "compare the rate in effect 12 h before handoff with the current rate")],
        "glance": [see_li("Norepinephrine", "from 0.2")],
    },
    "C2-Q3": {
        "tabbed": [section("MAR"), grid([["cefepime", "01:41"]], table="mar")],
        "glance": [hover_dose("CefePIME", "01:41")],
    },
    "C2-Q4": {   # GI bleeding: hemoglobin falling 9.6 -> 7.9, platelets 68
        "tabbed": [tab("Labs"), grid(["Hemoglobin"], ["find:9.6", "last"], "labs"),
                   think(1, "compare the earlier and latest hemoglobin"),
                   grid(["Platelet Count"], ["last"], "labs")],
        "glance": [see_row("Hemoglobin", "7.9"), see_row("Platelets", "68")],
    },
}

# What the replay types as the answer, so the app scores each run (answer entry is not timed).
SYNTHESIS_ANSWERS = {
    "S1-Q4": "Bleeding risk on the heparin infusion; hemoglobin 9.3.",
    "S2-Q4": "Neurological decline after SAH: GCS 15 now; MAP dipped to 63, keep close neuro checks and BP control.",
    "C1-Q4": "Hemodynamic instability: MAP 64 on norepinephrine and vasopressin; lactate 4.3.",
    "C2-Q4": "Ongoing GI bleeding: hemoglobin down to 7.9 from 9.6; platelets 68.",
}
