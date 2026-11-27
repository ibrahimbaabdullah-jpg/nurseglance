"""NurseGlance: a nurse-centered ICU handoff dashboard on MIMIC-IV demo FHIR data.

Run with:  streamlit run streamlit_app.py

Four modes sit in a bar across the top (version 1.1): Handoff view, Study session,
Virtual nurse and Researcher. While a study session runs, the bar shows only the
study, so a participant cannot wander into another mode.
"""
import streamlit as st

from app import data, flags, glance, research, study, tabbed, vn

st.set_page_config(page_title="NurseGlance", page_icon="🩺", layout="wide")

VIEWS = {"NurseGlance": glance.render, "Tabbed EHR (control)": tabbed.render}
DISCLAIMER = ("Research prototype: not for clinical use and not clinically validated. Data: MIMIC-IV Clinical "
              "Database Demo on FHIR v2.1.0 (PhysioNet, ODbL v1.0). De-identified; dates are shifted into the future.")

# Less empty space above the page, so more of each view fits on a laptop screen (both views alike).
st.markdown("<style>[data-testid='stMainBlockContainer']{padding-top:3.2rem}"
            ".ng-banner{background:#fff4ce;color:#5c4400;border:1px solid #f0d78c;border-radius:6px;"
            "padding:3px 10px;font-size:.82rem;font-weight:600;margin-bottom:6px}</style>"
            '<div class="ng-banner" role="note">⚠️ Research prototype · not for clinical use · '
            "de-identified MIMIC-IV demo data</div>", unsafe_allow_html=True)

if not data.available_cases():
    st.error("No case files in data/processed. Run etl/build_cases.py first.")
    st.stop()


def handoff_page() -> None:
    st.session_state.pop("log_context", None)
    cases = data.available_cases()
    labels = {c: f"{c} · {data.patient_line(data.load_case(c))}" for c in cases}
    c1, c2, c3 = st.columns([2.4, 2.4, 1.2], vertical_alignment="center")
    case_id = c1.selectbox("Patient", cases, format_func=labels.get, key="handoff_case", label_visibility="collapsed")
    view = c2.radio("View", list(VIEWS), horizontal=True, key="handoff_view", label_visibility="collapsed")
    show_flags = c3.toggle("Rule-based flags", key="handoff_flags",
                           help="8 transparent rules, each shown with the values that set it off. "
                                "Always off in study mode.")
    case = data.load_case(case_id)
    if show_flags:
        flags.render(case)
    VIEWS[view](case)
    st.caption(DISCLAIMER)


def study_page() -> None:
    study.render()
    st.caption(DISCLAIMER)


def vn_page() -> None:
    vn.render()
    st.caption(DISCLAIMER)


def research_page() -> None:
    research.render()
    st.caption(DISCLAIMER)


PAGES = {
    "handoff": st.Page(handoff_page, title="Handoff view", icon="🩺", url_path="handoff", default=True),
    "study": st.Page(study_page, title="Study session", icon="⏱️", url_path="study"),
    "vn": st.Page(vn_page, title="Virtual nurse", icon="🖥️", url_path="virtual-nurse"),
    "research": st.Page(research_page, title="Researcher", icon="📊", url_path="researcher"),
}
if study.is_running():
    # Locked: only the study page, so the participant cannot leave mid-session.
    pages = [st.Page(study_page, title="Study session", icon="⏱️", url_path="study", default=True)]
else:
    pages = list(PAGES.values())
st.navigation(pages, position="top").run()
