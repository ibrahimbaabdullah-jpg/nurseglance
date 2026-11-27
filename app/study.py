"""Study mode: an AWARE-style crossover session, start to finish.

Flow (protocol section 5): anonymous run ID -> 2 practice questions on the practice
stay -> first view with 2 cases (4 timed questions each) -> SUS and NASA-TLX -> a
2-minute break -> 2 practice questions -> second view with the other 2 cases -> SUS
and NASA-TLX -> debrief notes and export. Practice answers are logged, never scored.
The facilitator can pause; paused time is logged and left out of the question's time.
"End early" stops a session but keeps what was logged, for export and analysis.

Each view gets one standard and one complex case, so each participant sees each
case once. Three things are randomized with a seeded generator, and the seed is
logged: the view order, which case pair goes with which view, and the case order
within each view. Flags are always off here, so the comparison tests layout only.
"""
from __future__ import annotations

import csv
import io
import json
import random
import re
from datetime import datetime
from pathlib import Path

import streamlit as st

from app import data, events, glance, scoring, tabbed

QUESTIONS_FILE = data.ROOT / "docs" / "case_questions.json"
PRACTICE_FILE = data.ROOT / "docs" / "practice_questions.json"
BREAK_S = 120
LOG_DIR = data.ROOT / "logs"
VIEW_NAMES = {"tabbed": "Tabbed EHR view", "glance": "NurseGlance view"}
VIEW_RENDER = {"tabbed": tabbed.render, "glance": glance.render}
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,16}$")


def load_questions() -> dict[str, list[dict]]:
    with open(QUESTIONS_FILE, encoding="utf-8") as handle:
        rows = json.load(handle)["questions"]
    by_case: dict[str, list[dict]] = {}
    for q in rows:
        by_case.setdefault(q["case_id"], []).append(q)
    return by_case


def load_practice() -> list[dict]:
    if not PRACTICE_FILE.exists():
        return []
    with open(PRACTICE_FILE, encoding="utf-8") as handle:
        return json.load(handle)["questions"]


def make_plan(seed: int, standard=("S1", "S2"), complex_=("C1", "C2")) -> list[dict]:
    """Two blocks, one per view, each with one standard and one complex case."""
    rng = random.Random(seed)
    views = ["tabbed", "glance"]
    rng.shuffle(views)
    std, cpx = list(standard), list(complex_)
    rng.shuffle(std)
    rng.shuffle(cpx)
    blocks = []
    for view, s, c in zip(views, std, cpx):
        cases = [s, c]
        rng.shuffle(cases)
        blocks.append({"view": view, "cases": cases})
    return blocks


def make_steps(plan: list[dict], questions: dict[str, list[dict]],
               practice: list[dict] | None = None) -> list[dict]:
    """Per view: practice questions (unscored), the timed questions, then the surveys.

    A break follows the first view's surveys. Practice questions are split evenly
    between the views, in file order.
    """
    steps = []
    per_view = len(practice or []) // max(len(plan), 1)
    for b, block in enumerate(plan):
        for q in (practice or [])[b * per_view:(b + 1) * per_view]:
            steps.append({"kind": "practice", "view": block["view"], "case_id": q["case_id"], "question": q})
        for case_id in block["cases"]:
            for q in questions.get(case_id, []):
                steps.append({"kind": "question", "view": block["view"], "case_id": case_id, "question": q})
        steps.append({"kind": "survey", "view": block["view"]})
        if b < len(plan) - 1:
            steps.append({"kind": "break", "view": ""})
    steps.append({"kind": "done"})
    return steps


def _parse(ts_utc: str) -> datetime:
    return datetime.fromisoformat(ts_utc.replace("Z", "+00:00"))


def paused_seconds(rows: list[dict], t0: datetime, t1: datetime) -> float:
    """Seconds between t0 and t1 spent paused (pause ... resume pairs in the log)."""
    total, start = 0.0, None
    for r in rows:
        if r["event"] == "pause":
            start = _parse(r["ts_utc"])
        elif r["event"] == "resume" and start is not None:
            end = _parse(r["ts_utc"])
            lo, hi = max(start, t0), min(end, t1)
            total += max(0.0, (hi - lo).total_seconds())
            start = None
    return total


# ------------------------------------------------------------------ summaries

def summarize(rows: list[dict], steps: list[dict]) -> list[dict]:
    """One row per question (time, interactions, screens, answer, correct) and per survey."""
    out = []
    questions = {s["question"]["id"]: s["question"] for s in steps if s["kind"] == "question"}
    # Position of each case within its view (1 or 2). With one standard and one complex case per view,
    # a complex case in position 1 means the view started with the complex case, an order that raised
    # information-processing burden in ICU providers (Khairat et al., JAMIA 2026).
    position: dict[str, int] = {}
    for view in dict.fromkeys(s["view"] for s in steps if s["kind"] == "question"):
        cases = list(dict.fromkeys(s["case_id"] for s in steps if s["kind"] == "question" and s["view"] == view))
        position.update({c: n for n, c in enumerate(cases, start=1)})
    for qid, q in questions.items():
        mine = [r for r in rows if r["question_id"] == qid]
        shown = next((r for r in mine if r["event"] == "question_shown"), None)
        answer = next((r for r in mine if r["event"] == "answer_submit"), None)
        if not shown:
            continue
        seconds = None
        if answer:
            t0, t1 = _parse(shown["ts_utc"]), _parse(answer["ts_utc"])
            seconds = round((t1 - t0).total_seconds() - paused_seconds(rows, t0, t1), 2)
        actions = [r for r in mine if r["event"] in events.INTERACTIONS]
        screens = {r["target"] for r in actions if r["event"] == "tab_switch"}
        value = answer["value"] if answer else ""
        correct = scoring.check_answer(q, value) if answer else None   # never answered: missing, not wrong
        out.append({"run_id": shown["run_id"], "seed": shown["seed"], "view": shown["view"],
                    "case_id": shown["case_id"], "case_position": position.get(shown["case_id"], ""),
                    "question_id": qid, "kind": q["kind"],
                    "time_s": seconds, "interactions": len(actions), "screens_visited": len(screens) + 1,
                    "answer": value, "correct": "" if correct is None else int(correct),
                    "sus": "", "tlx_raw": ""})
    for r in rows:
        if r["event"] == "survey_submit" and r["target"] in ("SUS_score", "TLX_raw"):
            row = next((o for o in out if o["question_id"] == f"survey-{r['view']}"), None)
            if row is None:
                row = {"run_id": r["run_id"], "seed": r["seed"], "view": r["view"], "case_id": "", "case_position": "",
                       "question_id": f"survey-{r['view']}", "kind": "survey", "time_s": "",
                       "interactions": "", "screens_visited": "", "answer": "", "correct": "",
                       "sus": "", "tlx_raw": ""}
                out.append(row)
            row["sus" if r["target"] == "SUS_score" else "tlx_raw"] = r["value"]
    return out


def to_csv(rows: list[dict], columns: list[str]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def save_local(run_id: str, events_csv: str, summary_csv: str, stamp: str | None = None) -> Path | None:
    """Also write the CSVs to logs/ when the disk is writable (it does not survive a cloud restart).

    Saving again with the same stamp overwrites that run's files, so a later debrief note
    reaches the saved copy instead of a second file.
    """
    try:
        LOG_DIR.mkdir(exist_ok=True)
        stamp = stamp or datetime.now().strftime("%Y%m%d-%H%M%S")
        (LOG_DIR / f"{run_id}_{stamp}_events.csv").write_text(events_csv, encoding="utf-8")
        (LOG_DIR / f"{run_id}_{stamp}_summary.csv").write_text(summary_csv, encoding="utf-8")
        return LOG_DIR
    except OSError:
        return None


# ------------------------------------------------------------------ UI

def _reset() -> None:
    for key in list(st.session_state.keys()):
        if key in ("study", "events", "log_context", "seed_default", "seed_input", "debrief") \
                or key.startswith(("tab_", "fs_", "meds_", "q_", "sus_", "tlx_")):
            del st.session_state[key]


def _start_screen() -> None:
    st.header("Study session")
    st.markdown(
        "Each session uses both views. In each view the nurse answers 2 practice questions, then 8 timed "
        "questions on 2 patients (4 each), then rates the view with the SUS and NASA-TLX. A 2-minute break "
        "separates the views. Times and interface actions are logged; there is a Pause button for "
        "interruptions.\n\n"
        "Type the run ID and seed from the allocation list (Researcher page). Use an anonymous run ID such "
        "as **R017**. Never enter a name.\n\n"
        "This is a demonstration of a study design. Collecting data from real nurses for research "
        "needs IRB approval; until then, results from this mode are design-level estimates only.")
    with st.form("study_start"):
        run_id = st.text_input("Run ID", placeholder="R017")
        # The default must not change between reruns: a new default makes Streamlit treat the
        # field as a new widget and silently drop a seed the user typed.
        default_seed = st.session_state.setdefault("seed_default", random.SystemRandom().randint(1, 9999))
        seed = st.number_input("Random seed", min_value=0, max_value=10**6, value=default_seed, key="seed_input",
                               help="Logged with every row. Reuse a seed to reproduce a session's order.")
        go = st.form_submit_button("Start session", type="primary")
    if go:
        if not RUN_ID_PATTERN.match(run_id or ""):
            st.error("Run ID must be 1-16 letters, digits, - or _ (for example R017).")
            return
        questions = load_questions()
        plan = make_plan(int(seed))
        st.session_state["study"] = {"run_id": run_id, "seed": int(seed), "plan": plan,
                                     "steps": make_steps(plan, questions, load_practice()), "i": 0,
                                     "shown": set(), "paused": False}
        st.session_state["events"] = []
        st.session_state["log_context"] = {"run_id": run_id, "seed": int(seed)}
        events.log("session_start", target="plan", value=json.dumps(plan))
        st.rerun()


def _set_context(**kw) -> None:
    ctx = st.session_state["log_context"]
    ctx.update(kw)


def context_for(study: dict, ctx: dict | None) -> dict | None:
    """The log context to restore for a study, or None when the current one is already the study's.

    Once a session has ended the other pages come back, and the Handoff page clears the
    context while the virtual-nurse page replaces it, so returning to the study restores it.
    """
    if ctx and ctx.get("run_id") == study["run_id"]:
        return None
    return {"run_id": study["run_id"], "seed": study["seed"]}


def study_rows(study: dict, rows: list[dict]) -> list[dict]:
    """Only this session's events (the virtual-nurse page logs to the same list once a study has ended)."""
    return [r for r in rows if r.get("run_id") == study["run_id"]]


def _advance() -> None:
    st.session_state["study"]["i"] += 1


def progress_text(study: dict, i: int) -> tuple[str, float]:
    """'Question 3 of 16 · patient 1 of 4 · NurseGlance view', and the fraction of timed questions done."""
    step = study["steps"][i]
    view = VIEW_NAMES.get(step.get("view"), "")
    if step["kind"] == "practice":
        in_view = [s for s in study["steps"] if s["kind"] == "practice" and s["view"] == step["view"]]
        n = next(k for k, s in enumerate(in_view, start=1) if s is step)
        return f"Practice {n} of {len(in_view)} · not scored · {view}", _done_fraction(study, i)
    n_q = sum(1 for s in study["steps"] if s["kind"] == "question")
    q_no = sum(1 for s in study["steps"][:i + 1] if s["kind"] == "question")
    order = [c for block in study["plan"] for c in block["cases"]]
    return (f"Question {q_no} of {n_q} · patient {order.index(step['case_id']) + 1} of {len(order)} · {view}",
            _done_fraction(study, i))


def _done_fraction(study: dict, i: int) -> float:
    n_q = sum(1 for s in study["steps"] if s["kind"] == "question") or 1
    return sum(1 for s in study["steps"][:i] if s["kind"] == "question") / n_q


def _question_step(study: dict, step: dict, slot) -> None:
    q, i = step["question"], study["i"]
    practice = step["kind"] == "practice"
    _set_context(view=step["view"], case_id=step["case_id"], question_id=q["id"])
    if i not in study["shown"]:
        study["shown"].add(i)
        events.log("practice_shown" if practice else "question_shown", target=q["kind"], value=q["text"])
    label, frac = progress_text(study, i)
    with slot.container(border=True, key="ng-qcard"):   # in the sidebar, so it stays in view while scrolling
        st.caption(label)
        st.progress(frac)
        with st.form(f"q_{q['id']}_{i}", clear_on_submit=True):
            st.markdown(f"**{q['text']}**")
            kind, key = q["answer_type"], f"q_in_{q['id']}_{i}"
            if kind == "choice":
                answer = st.radio("Answer", q["options"], index=None, horizontal=True, key=key)
            elif kind == "text":
                answer = st.text_area("Answer", key=key, height=90)
            elif kind == "time":
                answer = st.text_input("Answer (24-hour time, HH:MM)", key=key, placeholder="21:30")
            else:
                answer = st.text_input(f"Answer ({q.get('unit', '')})", key=key)
            submit = st.form_submit_button("Submit answer", type="primary", width="stretch")
            cant = st.form_submit_button("I can't find it", width="stretch")
        if submit or cant:
            events.log("practice_submit" if practice else "answer_submit", target="cant_find" if cant else "submit",
                       value="" if cant else (answer or ""))
            _advance()
            st.rerun()
        st.caption("Answer from the chart only. After 3 minutes the facilitator will ask for your best answer.")
    VIEW_RENDER[step["view"]](data.load_case(step["case_id"]))


def _survey_step(study: dict, step: dict) -> None:
    view = step["view"]
    _set_context(view=view, case_id="", question_id="")
    st.header(f"How was working with the {VIEW_NAMES[view]}?")
    st.caption("Two short questionnaires about the 2 patients you just finished in this view, about 3 minutes. "
               "Think only about this view. There are no right or wrong answers.")
    with st.form(f"survey_{view}", border=False):
        with st.container(border=True):
            st.markdown("**Part 1 of 2 · Usability: System Usability Scale**")
            st.caption("For each statement, choose how much you agree. 1 = strongly disagree, 5 = strongly agree.")
            sus = [st.radio(f"{n}. {text}", [1, 2, 3, 4, 5], index=None, horizontal=True, key=f"sus_{view}_{n}")
                   for n, text in enumerate(scoring.SUS_ITEMS, start=1)]
        with st.container(border=True):
            st.markdown("**Part 2 of 2 · Workload: NASA Task Load Index**")
            st.caption("Move each slider to show how the questions in this view felt.")
            tlx = {}
            for key, name, prompt, low, high in scoring.TLX_SCALES:
                tlx[key] = st.slider(f"{name}: {prompt}", 0, 100, 50, step=5, key=f"tlx_{view}_{key}",
                                     help=f"0 = {low}, 100 = {high}")
        done = st.form_submit_button("Submit and continue", type="primary")
    if done:
        if any(r is None for r in sus):
            st.error("Please answer all 10 usability statements.")
            return
        for n, r in enumerate(sus, start=1):
            events.log("survey_submit", target=f"SUS-{n}", value=r)
        for key, v in tlx.items():
            events.log("survey_submit", target=f"TLX-{key}", value=v)
        events.log("survey_submit", target="SUS_score", value=scoring.sus_score(sus))
        events.log("survey_submit", target="TLX_raw", value=round(scoring.tlx_raw(tlx), 2))
        _advance()
        st.rerun()


def _break_step(study: dict) -> None:
    _set_context(view="", case_id="", question_id="")
    if "break_logged" not in study:
        study["break_logged"] = True
        events.log("break_start")
    nxt = next(s for s in study["steps"][study["i"]:] if s.get("view"))
    st.header("Break, about 2 minutes")
    st.markdown(f"Stand up, look away from the screen, and have some water. Next: the **{VIEW_NAMES[nxt['view']]}**, "
                "with 2 practice questions and then 2 new patients.")
    st.caption(f"The break is {BREAK_S // 60} minutes in the protocol; the facilitator starts the second view.")
    if st.button("Start the second view", type="primary"):
        events.log("break_end")
        _advance()
        st.rerun()


def _done_step(study: dict) -> None:
    _set_context(view="", case_id="", question_id="")
    if "ended" not in study:
        study["ended"] = True
        events.log("session_end")
    rows = study_rows(study, st.session_state.get("events", []))
    summary = summarize(rows, study["steps"])
    summary_cols = ["run_id", "seed", "view", "case_id", "case_position", "question_id", "kind", "time_s", "interactions",
                    "screens_visited", "answer", "correct", "sus", "tlx_raw"]
    events_csv, summary_csv = to_csv(rows, events.COLUMNS), to_csv(summary, summary_cols)
    stamp = study.setdefault("stamp", datetime.now().strftime("%Y%m%d-%H%M%S"))
    if "saved" not in study:
        study["saved"] = str(save_local(study["run_id"], events_csv, summary_csv, stamp) or "")
    if study.get("abandoned"):
        st.header("Session ended early")
        st.warning(f"Run {study['run_id']} · seed {study['seed']} · {len(rows)} events logged before the session "
                   "was ended. Download the files: the data so far stays in the analysis, marked as abandoned.")
    else:
        st.header("Session complete")
        st.success(f"Run {study['run_id']} · seed {study['seed']} · {len(rows)} events logged.")
    with st.form("debrief"):
        st.markdown("**Debrief** (facilitator's notes; protocol step 6)")
        note = st.text_area("Which view would you use at handoff, and why? Was anything missing or misleading?",
                            key="debrief", height=110)
        if st.form_submit_button("Save notes to the log"):
            events.log("debrief_note", value=note)
            study.pop("saved", None)   # save again, so the note reaches the saved copy
            st.rerun()
    # Text cells: survey rows leave the question columns blank, which Arrow cannot mix with numbers.
    st.dataframe([{k: "" if v is None else str(v) for k, v in r.items()} for r in summary], hide_index=True,
                 width="stretch")
    c1, c2, c3 = st.columns(3)
    c1.download_button("Download event log (CSV)", events_csv, f"{study['run_id']}_events.csv", "text/csv",
                       type="primary")
    c2.download_button("Download summary (CSV)", summary_csv, f"{study['run_id']}_summary.csv", "text/csv")
    if c3.button("Start a new session"):
        _reset()
        st.rerun()
    st.caption("Download both files now. On Streamlit Community Cloud, files saved on the server do not "
               "survive a restart; a real study would run locally or log to a database."
               + (f" A copy was also saved to {study['saved']}." if study.get("saved") else ""))


def end_early(study: dict) -> None:
    """Stop a session before its last step: log session_abandoned and go to the export screen.

    Nothing is discarded, so a nurse who completed one view still contributes that view's data
    (protocol section 8). The Researcher page marks such a run as abandoned. "Start a new session"
    on the export screen clears it.
    """
    events.log("session_abandoned", target=study["steps"][study["i"]]["kind"],
               value=sum(1 for s in study["steps"][:study["i"]] if s["kind"] == "question"))
    study["abandoned"] = True
    study["ended"] = True   # no session_end event: that event means the session was completed
    study["paused"] = False
    study["i"] = len(study["steps"]) - 1


def is_running() -> bool:
    study = st.session_state.get("study")
    return bool(study) and study["steps"][study["i"]]["kind"] != "done"


def _pause_screen(study: dict) -> None:
    st.header("Paused")
    st.markdown("The view is hidden and the time is not counted while the session is paused.")
    if st.button("Resume", type="primary"):
        study["paused"] = False
        events.log("resume")
        st.rerun()


def render(question_slot=None) -> None:
    """question_slot: a sidebar container for the question card (defaults to the sidebar)."""
    study = st.session_state.get("study")
    if not study:
        _start_screen()
        return
    restored = context_for(study, st.session_state.get("log_context"))
    if restored:
        st.session_state["log_context"] = restored
    step = study["steps"][study["i"]]
    with st.sidebar:
        st.markdown(f"**Study session** · run {study['run_id']} · seed {study['seed']}")
        question_slot = question_slot if question_slot is not None else st.container()
        if step["kind"] != "done":
            c1, c2 = st.columns(2)
            if c1.button("Pause", disabled=study.get("paused", False), width="stretch"):
                study["paused"] = True
                events.log("pause")
                st.rerun()
            if c2.button("End early", width="stretch",
                         help="Ends the session now. The answers so far are kept and can be downloaded, as the "
                              "protocol keeps a nurse who finished only one view."):
                end_early(study)
                st.rerun()
            st.caption("Other modes are hidden until the session ends.")
    if study.get("paused"):
        _pause_screen(study)
        return
    if step["kind"] in ("question", "practice"):
        _question_step(study, step, question_slot)
    elif step["kind"] == "survey":
        _survey_step(study, step)
    elif step["kind"] == "break":
        _break_step(study)
    else:
        _done_step(study)
