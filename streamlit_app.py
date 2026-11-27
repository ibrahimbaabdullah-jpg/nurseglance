"""NurseGlance: a nurse-centered ICU handoff dashboard on MIMIC-IV demo FHIR data.

Run with:  streamlit run streamlit_app.py

Version 1.2 (the look of the design mockup, docs/design/): a white top bar holds the
view switch (Glance view or Tabbed EHR view), the mode switch (Handoff or Virtual
nurse) and a "Start study mode" button. The Researcher page is linked at the foot
of each page. While a study session runs, the bar shows only the session, so a
participant cannot wander into another mode.
"""
import streamlit as st

from app import data, glance, research, study, tabbed, ui, vn

st.set_page_config(page_title="NurseGlance", page_icon="🩺", layout="wide", initial_sidebar_state="expanded")
ui.inject()

VIEWS = {"glance": "Glance view", "tabbed": "Tabbed EHR view"}
MODES = {"handoff": "Handoff", "virtual-nurse": "Virtual nurse"}
KINDS = {"S": "Simple", "C": "Complex"}

if not data.available_cases():
    st.error("No case files in data/processed. Run etl/build_cases.py first.")
    st.stop()


def case_label(case_id: str) -> str:
    return f"{case_id} · {KINDS.get(case_id[:1], '')}".strip(" ·")


def eyebrow(case_id: str, case: dict) -> str:
    cases = data.available_cases()
    return (f"Case {case_id} · {cases.index(case_id) + 1} of {len(cases)} · {KINDS.get(case_id[:1], '')} · "
            f"handoff {data.handoff(case):%Y-%m-%d %H:%M}")


def patient_view(case_id: str, show_flags: bool) -> None:
    """The chosen view of one patient, as on the Handoff page (and under the virtual-nurse review)."""
    case = data.load_case(case_id)
    if st.session_state.get("ng_view", "glance") == "tabbed":
        tabbed.render(case, show_flags=show_flags, eyebrow=eyebrow(case_id, case), title=f"Patient {case_id}")
    else:
        glance.render(case, show_flags=show_flags, eyebrow=eyebrow(case_id, case), title=f"Patient {case_id}")


def context_row(key: str) -> tuple[str, bool]:
    """Patient picker and the flags switch, under the top bar."""
    cases = data.available_cases()
    with st.container(key="ng-ctx", horizontal=True, vertical_alignment="center"):
        st.html('<span class="ng-ctx-label">Patient</span>', width="content")
        case_id = st.segmented_control("Patient", cases, format_func=case_label, default=cases[0], required=True,
                                       key=key, label_visibility="collapsed")
        st.space("stretch")
        show = st.toggle("Rule-based flags", key=f"{key}_flags",
                         help="8 transparent rules, each shown with the values that set it off. "
                              "Always off in study mode.")
    return case_id or cases[0], show


def handoff_page() -> None:
    st.session_state.pop("log_context", None)
    with st.container(key="ng-main"):
        case_id, show = context_row("handoff_case")
        patient_view(case_id, show)
        foot()


def vn_page() -> None:
    vn.render(patient_view, footer=foot)


def study_page() -> None:
    with st.container(key="ng-main"):
        study.render()
        foot(research_link=False)


def research_page() -> None:
    with st.container(key="ng-main"):
        research.render()
        foot(research_link=False)


PAGES = {
    "handoff": st.Page(handoff_page, title="Handoff", icon="🩺", url_path="handoff", default=True),
    "virtual-nurse": st.Page(vn_page, title="Virtual nurse", icon="🖥️", url_path="virtual-nurse"),
    "study": st.Page(study_page, title="Study session", icon="⏱️", url_path="study"),
    "researcher": st.Page(research_page, title="Researcher", icon="📊", url_path="researcher"),
}


def foot(research_link: bool = True) -> None:
    with st.container(horizontal=True, vertical_alignment="center", key="ng-footrow"):
        ui.footer()
        if research_link:
            st.page_link(PAGES["researcher"], label="Researcher page", icon=":material/analytics:")


def _keep_view() -> None:
    st.session_state["ng_view"] = st.session_state.get("ng_view_w") or st.session_state.get("ng_view", "glance")


running = study.is_running()
if running:
    # Locked: only the study page, so the participant cannot leave mid-session.
    page = st.navigation([st.Page(study_page, title="Study session", icon="⏱️", url_path="study", default=True)],
                         position="hidden")
else:
    page = st.navigation(list(PAGES.values()), position="hidden")
current = page.url_path or "handoff"

with st.container(key="ng-topbar", horizontal=True, vertical_alignment="center"):
    if running:
        s = st.session_state["study"]
        st.html(ui.brand(f"<b>Study session</b> · run {s['run_id']} · seed {s['seed']}"), width="stretch")
    else:
        st.html(ui.brand(), width="stretch")
        if current in MODES:
            st.segmented_control("View", list(VIEWS), format_func=VIEWS.get, required=True, key="ng_view_w",
                                 default=st.session_state.get("ng_view", "glance"), on_change=_keep_view,
                                 label_visibility="collapsed")
        mode = st.segmented_control("Mode", list(MODES), format_func=MODES.get, key=f"ng_mode_{current}",
                                    default=current if current in MODES else None, label_visibility="collapsed")
        if current != "study" and st.button("Start study mode", type="primary", key="ng_start_study"):
            st.switch_page(PAGES["study"])
        if mode and mode != current:
            st.switch_page(PAGES[mode])

page.run()
