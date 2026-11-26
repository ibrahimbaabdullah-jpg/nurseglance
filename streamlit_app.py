"""NurseGlance: a nurse-centered ICU handoff dashboard on MIMIC-IV demo FHIR data.

Run with:  streamlit run streamlit_app.py
"""
import streamlit as st

from app import data, glance, tabbed

st.set_page_config(page_title="NurseGlance", page_icon="🩺", layout="wide")

VIEWS = {"NurseGlance (organ systems)": glance.render, "Tabbed EHR view (control)": tabbed.render}

with st.sidebar:
    st.title("NurseGlance")
    cases = data.available_cases()
    if not cases:
        st.error("No case files in data/processed. Run etl/build_cases.py first.")
        st.stop()
    labels = {c: f"{c} · {data.patient_line(data.load_case(c))}" for c in cases}
    case_id = st.selectbox("Patient", cases, format_func=labels.get)
    view = st.radio("View", list(VIEWS))
    st.divider()
    st.caption("Research prototype: not for clinical use and not clinically validated. "
               "Data: MIMIC-IV Clinical Database Demo on FHIR v2.1.0 (PhysioNet, ODbL v1.0). "
               "De-identified; dates are shifted into the future.")

case = data.load_case(case_id)
st.warning("Research prototype · not for clinical use · de-identified MIMIC-IV demo data", icon="⚠️")
VIEWS[view](case)
