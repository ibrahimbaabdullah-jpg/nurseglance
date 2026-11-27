"""Researcher console: the allocation list, a check of each session's files, and the planned analysis.

For the study team, not for participants. Nothing typed or uploaded here is stored
on the server. The summary by view is descriptive (medians and percentages); the
protocol's primary analysis is a mixed-effects model run in R (docs/protocol.md).
"""
from __future__ import annotations

import io
import statistics

import pandas as pd
import streamlit as st

from app import data, events, study

EXAMPLE_EVENTS = data.ROOT / "docs" / "mock_session_events.csv"


@st.cache_data(show_spinner=False)
def _allocation(n: int, master_seed: int) -> list[dict]:
    from analysis.allocation import allocation
    return allocation(n, master_seed)


def allocation_tab() -> None:
    st.markdown("Each seed fixes three things: which view comes first, and which standard and which complex patient "
                "go with NurseGlance. That makes 8 sequences, and every block of 8 nurses gets all 8. Every "
                "half-block of 4 is balanced too (2 start with each view; each patient goes with NurseGlance "
                "twice), so the protocol keeps one list per role: 20 bedside and 20 virtual nurses, each list "
                "with its own master seed. Someone outside the session team makes the lists and keeps the master "
                "seeds private until enrollment ends.")
    c1, c2 = st.columns(2)
    n = c1.number_input("Nurses in this list (one role)", min_value=4, max_value=200, value=20, step=4)
    master = c2.text_input("Master seed (not stored or shown again)", type="password",
                           help="Any whole number. The same master seed always gives the same list.")
    if not master:
        st.caption("Type a master seed to build the list.")
        return
    try:
        master_seed = int(master)
    except ValueError:
        st.error("The master seed must be a whole number.")
        return
    rows = pd.DataFrame(_allocation(int(n), master_seed))
    first = rows["first_view"].value_counts()
    st.caption(f"{len(rows)} nurses · {first.get('glance', 0)} start with NurseGlance, "
               f"{first.get('tabbed', 0)} with the tabbed view · "
               f"{rows.groupby(['first_view', 'glance_cases']).ngroups} distinct view-and-patient pairings.")
    st.dataframe(rows, hide_index=True, width="stretch", height=300)
    st.download_button("Download the allocation list (CSV)", rows.to_csv(index=False), "allocation.csv", "text/csv")


def check_run(rows: list[dict]) -> dict:
    """What a complete session has: 16 answers, 2 SUS and 2 NASA-TLX scores, and an end event."""
    answered = {r["question_id"] for r in rows if r["event"] == "answer_submit"}
    shown = {r["question_id"] for r in rows if r["event"] == "question_shown"}
    surveys = [r for r in rows if r["event"] == "survey_submit" and r["target"] in ("SUS_score", "TLX_raw")]
    seed = rows[0]["seed"]
    steps = study.make_steps(study.make_plan(int(seed)), study.load_questions()) if str(seed).isdigit() else []
    planned = {s["question"]["id"] for s in steps if s["kind"] == "question"}
    paused = sum(1 for r in rows if r["event"] == "pause")
    problems = []
    if planned and answered != planned:
        problems.append(f"{len(planned - answered)} planned questions not answered")
    if len(surveys) < 4:
        problems.append(f"{len(surveys)} of 4 survey scores")
    if not any(r["event"] == "session_end" for r in rows):
        problems.append("no session_end event")
    if any(r["event"] == "session_abandoned" for r in rows):
        problems.append("abandoned")
    return {"run_id": rows[0]["run_id"], "seed": seed, "questions_shown": len(shown & planned) if planned else len(shown),
            "answered": len(answered & planned) if planned else len(answered), "survey_scores": len(surveys),
            "pauses": paused, "complete": not problems, "problems": "; ".join(problems) or "none"}


def _median(values) -> str:
    vals = [float(v) for v in values if v not in ("", None)]
    return f"{statistics.median(vals):.1f}" if vals else "–"


def summary_by_view(summary: list[dict]) -> pd.DataFrame:
    out = []
    for view in ("tabbed", "glance"):
        qs = [r for r in summary if r["view"] == view and r["kind"] != "survey"]
        scored = [r for r in qs if r["correct"] != ""]
        surveys = [r for r in summary if r["view"] == view and r["kind"] == "survey"]
        out.append({"View": study.VIEW_NAMES[view], "Questions": len(qs),
                    "Median time (s)": _median(r["time_s"] for r in qs),
                    "Median interactions": _median(r["interactions"] for r in qs),
                    "Correct (auto-scored)": f"{sum(int(r['correct']) for r in scored)} of {len(scored)}"
                    if scored else "–",
                    "Median SUS": _median(r["sus"] for r in surveys),
                    "Median NASA-TLX": _median(r["tlx_raw"] for r in surveys)})
    return pd.DataFrame(out)


def files_tab() -> None:
    st.markdown("Upload the event logs that study mode downloads at the end of each session "
                "(`<run>_events.csv`). The console checks that each run is complete and summarizes it by view.")
    files = st.file_uploader("Event logs (CSV)", type="csv", accept_multiple_files=True)
    use_example = st.checkbox("Use the scripted example run instead (a replay script, not a nurse)",
                              value=not files)
    frames = []
    for f in files or []:
        frames.append(pd.read_csv(f, dtype=str, keep_default_na=False))
    if use_example and EXAMPLE_EVENTS.exists():
        frames.append(pd.read_csv(EXAMPLE_EVENTS, dtype=str, keep_default_na=False))
    if not frames:
        return
    df = pd.concat(frames, ignore_index=True)
    missing = [c for c in events.COLUMNS if c not in df.columns]
    if missing:
        st.error(f"These files are not study event logs: missing columns {', '.join(missing)}.")
        return
    runs = {run: grp.to_dict("records") for run, grp in df.groupby("run_id", sort=False)}
    checks = pd.DataFrame([check_run(rows) for rows in runs.values()])
    st.markdown("**Completeness**")
    st.dataframe(checks, hide_index=True, width="stretch")
    summary = []
    for rows in runs.values():
        seed = rows[0]["seed"]
        if not str(seed).isdigit():
            continue
        steps = study.make_steps(study.make_plan(int(seed)), study.load_questions())
        summary += study.summarize(rows, steps)
    if not summary:
        return
    st.markdown("**By view** (descriptive; the planned analysis is a mixed-effects model)")
    st.dataframe(summary_by_view(summary), hide_index=True, width="stretch")
    buf = io.StringIO()
    pd.DataFrame(summary).to_csv(buf, index=False)
    st.download_button("Download one row per question (CSV)", buf.getvalue(), "summary_all_runs.csv", "text/csv")
    if use_example:
        st.caption("The example rows come from a scripted replay of study mode, so the times measure a script, not "
                   "a nurse. No nurse has used the app in a study.")


def analysis_tab() -> None:
    st.markdown("""
**Primary outcome:** seconds per question, from the question appearing to the answer, minus paused time.

**Primary model** (R, `lme4` and `lmerTest`, Kenward-Roger degrees of freedom):

```r
lmer(log(time_s) ~ view + period + case_type + case_position + question_type + view:case_type
     + (1 + view | nurse) + (1 | question), data = questions)
```

`case_position` (1 or 2 within the view, in the summary CSV) separates the order of the standard and complex case,
which affected ICU providers' information-processing burden in Khairat et al. (JAMIA 2026).

The result is the ratio of geometric mean times, NurseGlance to tabbed, with a 95% confidence interval.

**Secondary outcomes,** with the Holm correction: accuracy (logistic mixed model), synthesis rubric scores
(cumulative-link mixed model), clicks and screens (Poisson or negative binomial mixed models), and SUS and NASA-TLX
(linear mixed models with view and period and a random intercept for each nurse).

**Sample size:** 34 nurses give 80% power for a within-nurse effect of d<sub>z</sub> = 0.5; the target is 40 to
allow for withdrawals. Practice questions are logged but left out of every analysis.

The full protocol is `docs/protocol.md`. It needs IRB approval and a faculty principal investigator before any nurse
is contacted.
""", unsafe_allow_html=True)


def render() -> None:
    st.header("Researcher console")
    st.caption("For the study team. Nothing typed or uploaded here is stored on the server.")
    t1, t2, t3 = st.tabs(["Allocation list", "Session files", "Planned analysis"])
    with t1:
        allocation_tab()
    with t2:
        files_tab()
    with t3:
        analysis_tab()
