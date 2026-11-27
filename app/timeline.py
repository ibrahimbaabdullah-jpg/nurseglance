"""Infusions running at handoff and doses in the next 12 h, shared by both views and virtual-nurse mode.

timeline_rows() feeds NurseGlance's patient card and Tasks & meds column, the control's Summary tab and the
virtual-nurse checklist. timeline_figure() is the 12-hour Plotly timeline that versions 0.2 to 1.1 drew under
the NurseGlance panels; version 1.2 replaced it with the Tasks & meds column, and it is kept for the tests
and for replaying those versions.
"""
from __future__ import annotations

from datetime import timedelta

import plotly.graph_objects as go

from app import data


def timeline_rows(case: dict) -> tuple[list[dict], list[dict]]:
    """(doses due in the next 12 h, infusions running at handoff)."""
    ref = data.handoff(case)
    end = ref + timedelta(hours=case.get("windows", {}).get("lookahead_hours", 12))
    end = data.ts(case.get("windows", {}).get("lookahead_end")) or end
    doses = [m for m in case["med_administrations"] if m.get("relative") == "after_handoff"
             and m.get("t") and ref <= data.ts(m["t"]) <= end]
    running = []
    for label in sorted({i["label"] for i in case["infusions"] if i.get("running_at_handoff")}):
        segs = sorted((data.ts(i["start"]), data.ts(i["end"]) if i.get("end") else end, i)
                      for i in case["infusions"] if i["label"] == label and i.get("start"))
        current = [s for s in segs if s[0] <= ref <= s[1] and s[2].get("running_at_handoff")]
        if not current:
            continue
        # Follow back-to-back rate segments forward to find when the drip actually stops.
        stop = max(s[1] for s in current)
        for start, seg_end, _ in segs:
            if start <= stop + timedelta(minutes=5) and seg_end > stop:
                stop = seg_end
        row = dict(current[-1][2])
        row["bar_end"] = min(stop, end).isoformat()
        running.append(row)
    return doses, running


def timeline_figure(case: dict) -> go.Figure:
    ref = data.handoff(case)
    end = data.ts(case["windows"]["lookahead_end"])
    doses, running = timeline_rows(case)
    fig = go.Figure()
    for inf in sorted(running, key=lambda r: r["label"], reverse=True):
        stop = data.ts(inf["bar_end"])
        rate = f"{data.fmt_num(inf.get('rate'))} {inf.get('rate_unit') or ''}".strip()
        fig.add_trace(go.Scatter(
            x=[ref, stop], y=[f"▬ {inf['label']}"] * 2, mode="lines",
            line=dict(width=8, color="#90caf9"), showlegend=False,
            hovertemplate=f"{inf['label']}<br>rate at handoff: {rate}<extra></extra>"))
    names = sorted({d["name"] for d in doses}, reverse=True)
    for name in names:
        rows = [d for d in doses if d["name"] == name]
        text = [f"{name}<br>{data.fmt_time(d['t'])}"
                + (f"<br>{data.fmt_num(d['dose'])} {d.get('dose_unit') or ''}" if d.get("dose") else "")
                for d in rows]
        fig.add_trace(go.Scatter(
            x=[data.ts(d["t"]) for d in rows], y=[f"● {name}"] * len(rows), mode="markers",
            marker=dict(size=11, color="#1565c0", symbol="diamond"), showlegend=False,
            text=text, hovertemplate="%{text}<extra></extra>"))
    if not doses and not running:
        fig.add_annotation(text="No medication doses or running infusions in the next 12 h",
                           x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False)
    n_rows = len(names) + len(running)
    fig.add_vline(x=ref, line_dash="dot", line_color="#c62828")
    fig.update_layout(
        height=max(180, 26 * n_rows + 80), margin=dict(l=10, r=10, t=10, b=30),
        xaxis=dict(type="date", range=[ref - timedelta(minutes=15), end], dtick=2 * 3600 * 1000,
                   tickformat="%H:%M", showgrid=True),
        yaxis=dict(automargin=True, tickfont=dict(size=11), visible=n_rows > 0),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    return fig
