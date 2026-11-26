"""Event log for study and virtual-nurse sessions.

One row per event, following the schema in the build plan:
run_id, seed, ts_utc, view, case_id, question_id, event, target, value.

Streamlit cannot see raw mouse clicks or scrolling, so a "click" here is a logged
interface action: a tab switch, a toggle or a select. The protocol says so.
"""
from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

COLUMNS = ["run_id", "seed", "ts_utc", "view", "case_id", "question_id", "event", "target", "value"]
INTERACTIONS = {"tab_switch", "toggle"}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def active() -> bool:
    return bool(st.session_state.get("log_context"))


def log(event: str, target: str = "", value="") -> None:
    """Append one event using the current context (run, view, case, question). No-op outside a session."""
    ctx = st.session_state.get("log_context")
    if not ctx:
        return
    st.session_state.setdefault("events", []).append({
        "run_id": ctx.get("run_id", ""), "seed": ctx.get("seed", ""), "ts_utc": now_utc(),
        "view": ctx.get("view", ""), "case_id": ctx.get("case_id", ""),
        "question_id": ctx.get("question_id", ""), "event": event, "target": target,
        "value": "" if value is None else value})


def on_change_logger(key: str, event: str = "toggle", prefix: str = ""):
    """Callback for a widget's on_change that logs its new value as the target."""
    def _callback():
        log(event, target=f"{prefix}{st.session_state.get(key)}")
    return _callback
