"""Study mode: an AWARE-style crossover session, start to finish.

Flow: anonymous run ID -> first view with 2 cases (4 questions each) -> SUS and
NASA-TLX -> second view with the other 2 cases -> SUS and NASA-TLX -> export.

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


def make_steps(plan: list[dict], questions: dict[str, list[dict]]) -> list[dict]:
    steps = []
    for block in plan:
        for case_id in block["cases"]:
            for q in questions.get(case_id, []):
                steps.append({"kind": "question", "view": block["view"], "case_id": case_id, "question": q})
        steps.append({"kind": "survey", "view": block["view"]})
    steps.append({"kind": "done"})
    return steps


# ------------------------------------------------------------------ summaries

def summarize(rows: list[dict], steps: list[dict]) -> list[dict]:
    """One row per question (time, interactions, screens, answer, correct) and per survey."""
    out = []
    questions = {s["question"]["id"]: s["question"] for s in steps if s["kind"] == "question"}
    for qid, q in questions.items():
        mine = [r for r in rows if r["question_id"] == qid]
        shown = next((r for r in mine if r["event"] == "question_shown"), None)
        answer = next((r for r in mine if r["event"] == "answer_submit"), None)
        if not shown:
            continue
        seconds = None
        if answer:
            t0 = datetime.fromisoformat(shown["ts_utc"].replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(answer["ts_utc"].replace("Z", "+00:00"))
            seconds = round((t1 - t0).total_seconds(), 2)
        actions = [r for r in mine if r["event"] in events.INTERACTIONS]
        screens = {r["target"] for r in actions if r["event"] == "tab_switch"}
        value = answer["value"] if answer else ""
        correct = scoring.check_answer(q, value) if answer else False
        out.append({"run_id": shown["run_id"], "seed": shown["seed"], "view": shown["view"],
                    "case_id": shown["case_id"], "question_id": qid, "kind": q["kind"],
                    "time_s": seconds, "interactions": len(actions), "screens_visited": len(screens) + 1,
                    "answer": value, "correct": "" if correct is None else int(correct),
                    "sus": "", "tlx_raw": ""})
    for r in rows:
        if r["event"] == "survey_submit" and r["target"] in ("SUS_score", "TLX_raw"):
            row = next((o for o in out if o["question_id"] == f"survey-{r['view']}"), None)
            if row is None:
                row = {"run_id": r["run_id"], "seed": r["seed"], "view": r["view"], "case_id": "",
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


def save_local(run_id: str, events_csv: str, summary_csv: str) -> Path | None:
    """Also write the CSVs to logs/ when the disk is writable (it does not survive a cloud restart)."""
    try:
        LOG_DIR.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        (LOG_DIR / f"{run_id}_{stamp}_events.csv").write_text(events_csv, encoding="utf-8")
        (LOG_DIR / f"{run_id}_{stamp}_summary.csv").write_text(summary_csv, encoding="utf-8")
        return LOG_DIR
    except OSError:
        return None


# ------------------------------------------------------------------ UI

def _reset() -> None:
    for key in list(st.session_state.keys()):
        if key in ("study", "events", "log_context", "seed_default", "seed_input") \
                or key.startswith(("tab_", "fs_", "meds_", "q_", "sus_", "tlx_")):
            del st.session_state[key]


def _start_screen() -> None:
    st.header("Study session")
    st.markdown(
        "Each session shows two cases in each view, asks 4 questions per case, then asks for a "
        "SUS and NASA-TLX rating of each view. Times and interface actions are logged.\n\n"
        "Use an anonymous run ID such as **R017**. Never enter a name.\n\n"
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
                                     "steps": make_steps(plan, questions), "i": 0, "shown": set()}
        st.session_state["events"] = []
        st.session_state["log_context"] = {"run_id": run_id, "seed": int(seed)}
        events.log("session_start", target="plan", value=json.dumps(plan))
        st.rerun()


def _set_context(**kw) -> None:
    ctx = st.session_state["log_context"]
    ctx.update(kw)


def _advance() -> None:
    st.session_state["study"]["i"] += 1


def _question_step(study: dict, step: dict, slot) -> None:
    q, i = step["question"], study["i"]
    _set_context(view=step["view"], case_id=step["case_id"], question_id=q["id"])
    if i not in study["shown"]:
        study["shown"].add(i)
        events.log("question_shown", target=q["kind"], value=q["text"])
    n_q = sum(1 for s in study["steps"] if s["kind"] == "question")
    q_no = sum(1 for s in study["steps"][:i + 1] if s["kind"] == "question")
    with slot.container(border=True):   # in the sidebar, so it stays in view while the participant scrolls
        st.caption(f"Question {q_no} of {n_q} · {VIEW_NAMES[step['view']]} · patient {step['case_id']}")
        with st.form(f"q_{q['id']}", clear_on_submit=True):
            st.markdown(f"**{q['text']}**")
            kind, key = q["answer_type"], f"q_in_{q['id']}"
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
            events.log("answer_submit", target="cant_find" if cant else "submit",
                       value="" if cant else (answer or ""))
            _advance()
            st.rerun()
    VIEW_RENDER[step["view"]](data.load_case(step["case_id"]))


def _survey_step(study: dict, step: dict) -> None:
    view = step["view"]
    _set_context(view=view, case_id="", question_id="")
    st.header(f"Rate the {VIEW_NAMES[view]}")
    st.caption("Think only about the view you just used.")
    with st.form(f"survey_{view}"):
        st.subheader("System Usability Scale")
        st.caption("1 = strongly disagree, 5 = strongly agree")
        sus = [st.radio(f"{n}. {text}", [1, 2, 3, 4, 5], index=None, horizontal=True, key=f"sus_{view}_{n}")
               for n, text in enumerate(scoring.SUS_ITEMS, start=1)]
        st.subheader("NASA Task Load Index")
        tlx = {}
        for key, name, prompt, low, high in scoring.TLX_SCALES:
            tlx[key] = st.slider(f"{name}: {prompt}", 0, 100, 50, step=5, key=f"tlx_{view}_{key}",
                                 help=f"0 = {low}, 100 = {high}")
        done = st.form_submit_button("Submit ratings", type="primary")
    if done:
        if any(r is None for r in sus):
            st.error("Please answer all 10 SUS items.")
            return
        for n, r in enumerate(sus, start=1):
            events.log("survey_submit", target=f"SUS-{n}", value=r)
        for key, v in tlx.items():
            events.log("survey_submit", target=f"TLX-{key}", value=v)
        events.log("survey_submit", target="SUS_score", value=scoring.sus_score(sus))
        events.log("survey_submit", target="TLX_raw", value=round(scoring.tlx_raw(tlx), 2))
        _advance()
        st.rerun()


def _done_step(study: dict) -> None:
    _set_context(view="", case_id="", question_id="")
    if "ended" not in study:
        study["ended"] = True
        events.log("session_end")
    rows = st.session_state["events"]
    summary = summarize(rows, study["steps"])
    summary_cols = ["run_id", "seed", "view", "case_id", "question_id", "kind", "time_s", "interactions",
                    "screens_visited", "answer", "correct", "sus", "tlx_raw"]
    events_csv, summary_csv = to_csv(rows, events.COLUMNS), to_csv(summary, summary_cols)
    if "saved" not in study:
        study["saved"] = str(save_local(study["run_id"], events_csv, summary_csv) or "")
    st.header("Session complete")
    st.success(f"Run {study['run_id']} · seed {study['seed']} · {len(rows)} events logged.")
    st.dataframe(summary, hide_index=True, width="stretch")
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


def render(question_slot=None) -> None:
    """question_slot: a sidebar container for the question card (defaults to the sidebar's end)."""
    study = st.session_state.get("study")
    question_slot = question_slot if question_slot is not None else st.sidebar
    if not study:
        _start_screen()
        return
    step = study["steps"][study["i"]]
    with st.sidebar:
        st.caption(f"Run {study['run_id']} · step {study['i'] + 1} of {len(study['steps'])}")
        if st.button("Abandon session"):
            events.log("session_abandoned")
            _reset()
            st.rerun()
    if step["kind"] == "question":
        _question_step(study, step, question_slot)
    elif step["kind"] == "survey":
        _survey_step(study, step)
    else:
        _done_step(study)
