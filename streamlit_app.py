"""NurseGlance: a nurse-centered ICU handoff dashboard on MIMIC-IV demo FHIR data.

Run with:  streamlit run streamlit_app.py
"""
import streamlit as st

from app import data, flags, glance, study, tabbed, vn

st.set_page_config(page_title="NurseGlance", page_icon="🩺", layout="wide")

VIEWS = {"NurseGlance (organ systems)": glance.render, "Tabbed EHR view (control)": tabbed.render}
MODES = ["Explore", "Study session", "Virtual-nurse mode"]

with st.sidebar:
    st.title("NurseGlance")
    cases = data.available_cases()
    if not cases:
        st.error("No case files in data/processed. Run etl/build_cases.py first.")
        st.stop()
    in_study = bool(st.session_state.get("study"))
    mode = st.radio("Mode", MODES, index=1 if in_study else 0, disabled=in_study,
                    help="Finish or abandon the study session to switch modes." if in_study else None)
    question_slot = st.container()   # study mode puts the current question here, beside the view
    if mode != "Study session":
        labels = {c: f"{c} · {data.patient_line(data.load_case(c))}" for c in cases}
        case_id = st.selectbox("Patient", cases, format_func=labels.get)
    if mode == "Explore":
        view = st.radio("View", list(VIEWS))
        show_flags = st.toggle("Rule-based flags", value=False,
                               help="Transparent rules with their triggering values. Always off in study mode.")
    st.divider()
    st.caption("Research prototype: not for clinical use and not clinically validated. "
               "Data: MIMIC-IV Clinical Database Demo on FHIR v2.1.0 (PhysioNet, ODbL v1.0). "
               "De-identified; dates are shifted into the future.")

# Less empty space above the page, so more of each view fits on a laptop screen (both views alike).
st.markdown("<style>[data-testid='stMainBlockContainer']{padding-top:3.6rem}"
            ".ng-banner{background:#fff4ce;color:#5c4400;border:1px solid #f0d78c;border-radius:6px;"
            "padding:4px 10px;font-size:.86rem;font-weight:600;margin-bottom:6px}</style>"
            '<div class="ng-banner" role="note">⚠️ Research prototype · not for clinical use · '
            "de-identified MIMIC-IV demo data</div>", unsafe_allow_html=True)
if mode == "Study session":
    study.render(question_slot)
elif mode == "Virtual-nurse mode":
    if st.session_state.get("log_context", {}).get("run_id") not in (None, "VN"):
        st.session_state.pop("log_context", None)
    vn.render(data.load_case(case_id))
else:
    st.session_state.pop("log_context", None)
    case = data.load_case(case_id)
    if show_flags:
        flags.render(case)
    VIEWS[view](case)
