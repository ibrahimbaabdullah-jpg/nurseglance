#!/usr/bin/env python3
"""Turn the replayed paths into keystroke-level time estimates, a table and a chart.

    python analysis/task_analysis.py      # reads docs/task_replay.json (current version) and the
                                          # earlier versions' docs/task_replay_v*.json
                                          # -> docs/task_analysis*.csv, docs/figures/task_time*.svg,
                                          #    docs/task_analysis.md

Keystroke-Level Model (Card, Moran & Newell 1980; operator times as in Kieras 2001):
  P  point with the mouse          1.10 s
  BB press and release a button    0.20 s
  M  mental preparation            1.35 s

How a path becomes operators (mouse only; typing the answer is left out because
it is the same in both views):
  each click             M + P + BB   decide, point, click
  each scroll gesture    M + P        P stands in for one wheel or drag movement
                                      (KLM has no scroll operator); M to search
                                      what came into view
  each hover             P            point at the value; its reading is the M below
  each value read        M            find and read one value (a table row, a
                                      panel row, a list item or a tooltip)
  each extra step        M            e.g. add three GCS components, compare two values
  plus one M at the start to decide where to look.

These are design-level estimates for an expert following the shortest path, not
measurements of people.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import study  # noqa: E402

P, BB, M = 1.10, 0.20, 1.35
REPLAY = ROOT / "docs" / "task_replay.json"
OUT_CSV = ROOT / "docs" / "task_analysis.csv"
OUT_SVG = ROOT / "docs" / "figures" / "task_time.svg"
VIEW_LABEL = {"glance": "NurseGlance", "tabbed": "Tabbed EHR"}
KIND_LABEL = {"lookup": "Lookup", "trend": "Trend", "timing": "Timing", "synthesis": "Synthesis"}


def klm(rec: dict) -> dict:
    scrolls = rec["scroll_page"] + rec["scroll_grid"] + rec["scroll_list"]
    mental = 1 + rec["clicks"] + scrolls + rec["targets"] + rec["think"]
    seconds = mental * M + rec["clicks"] * (P + BB) + (scrolls + rec["hovers"]) * P
    return {"scrolls": scrolls, "mental": mental, "seconds": round(seconds, 2)}


def readable(line: str) -> str:
    """Turn a replay log line into a short phrase for the table."""
    import ast
    import re
    kind, _, rest = line.partition(": ")
    if kind in ("tab", "section"):
        return f"{rest} {kind}"
    if kind == "group":
        return f"{rest} Flowsheet section"
    m = re.match(r"table (rows|columns) (.+): (\d+) gesture", line)
    if not m:
        return line
    what, target, n = m.group(1), ast.literal_eval(m.group(2)), int(m.group(3))
    count = f"{n} scroll{'s' if n != 1 else ''}"
    if what == "rows":
        name = target if isinstance(target, str) else " ".join(t for t in target if t != "True")
        return f"find {name} row ({count})"
    if len(target) == 1:
        return f"scroll to {target[0]} ({count})"
    return f"scan {target[0]} to {target[-1]} ({count})"


def build_rows(replay: dict) -> list[dict]:
    questions = {q["id"]: q for qs in study.load_questions().values() for q in qs}
    rows = []
    for rec in replay["records"]:
        q = questions[rec["question_id"]]
        k = klm(rec)
        steps = [readable(line) for line in rec["log"] if not line.startswith(("grid", "think", "see:", "hover:"))]
        rows.append({
            "question_id": rec["question_id"], "case_id": rec["case_id"],
            "case_type": "standard" if rec["case_id"].startswith("S") else "complex",
            "kind": q["kind"], "view": rec["view"],
            "clicks": rec["clicks"], "screens": rec["screens"], "scrolls": k["scrolls"],
            "scrolls_page": rec["scroll_page"], "scrolls_table": rec["scroll_grid"], "scrolls_list": rec["scroll_list"],
            "hovers": rec["hovers"], "values_read": rec["targets"], "extra_steps": rec["think"],
            "mental_steps": k["mental"], "klm_seconds": k["seconds"],
            "app_logged_interactions": rec["app_interactions"], "app_logged_screens": rec["app_screens"],
            "path": "; ".join(steps) or "read on the first screen",
            "extra_step_reason": "; ".join(rec["think_why"]),
        })
    order = {qid: n for n, qid in enumerate(sorted({r["question_id"] for r in rows},
                                                   key=lambda s: ("SC".index(s[0]), s)))}
    return sorted(rows, key=lambda r: (order[r["question_id"]], r["view"]))


def summarize(rows: list[dict]) -> list[dict]:
    out = []
    for case_type in ("standard", "complex", "all"):
        for view in ("tabbed", "glance"):
            sel = [r for r in rows if r["view"] == view and (case_type == "all" or r["case_type"] == case_type)]
            n = len(sel)
            out.append({"case_type": case_type, "view": view, "questions": n,
                        **{f"mean_{k}": round(sum(r[k] for r in sel) / n, 2)
                           for k in ("clicks", "scrolls", "hovers", "screens", "klm_seconds")}})
    return out


# ------------------------------------------------------------------ chart (hand-written SVG)

def svg_chart(rows: list[dict], title: str, xmax: int | None = None) -> str:
    """Dumbbell: estimated seconds per question, tabbed vs NurseGlance, standard and complex panels."""
    blue, orange = "#257de0", "#f47230"          # categorical slots 1 and 2 (validated, light mode)
    ink, ink2, grid = "#191919", "#666666", "#e6e6e6"
    qids = list(dict.fromkeys(r["question_id"] for r in rows))
    val = {(r["question_id"], r["view"]): r for r in rows}
    if xmax is None:
        xmax = (int(max(r["klm_seconds"] for r in rows) / 10) + 1) * 10
    W, left, right, top, row_h, gap = 760, 210, 70, 78, 26, 34
    x = lambda s: left + (W - left - right) * s / xmax  # noqa: E731
    standard = [q for q in qids if q.startswith("S")]
    complex_ = [q for q in qids if q.startswith("C")]
    H = top + row_h * len(qids) + gap * 2 + 46
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           f'font-family="Source Sans Pro, Helvetica, Arial, sans-serif" role="img" '
           f'aria-label="Estimated seconds to answer each question in the tabbed EHR view and in NurseGlance">',
           f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
           f'<text x="16" y="26" font-size="16" font-weight="600" fill="{ink}">{title}</text>',
           f'<text x="16" y="46" font-size="12" fill="{ink2}">Keystroke-level estimate of the shortest scripted path, '
           f'in seconds (design-level, not user data). 1440×900 screen.</text>']
    # legend
    out.append(f'<circle cx="{W - 250}" cy="22" r="5" fill="{orange}"/>'
               f'<text x="{W - 240}" y="26" font-size="12" fill="{ink}">Tabbed EHR view</text>'
               f'<circle cx="{W - 130}" cy="22" r="5" fill="{blue}"/>'
               f'<text x="{W - 120}" y="26" font-size="12" fill="{ink}">NurseGlance</text>')
    y = top
    kinds = {r["question_id"]: r["kind"] for r in rows}
    plot_top = y
    for title, group in (("Standard cases", standard), ("Complex cases", complex_)):
        out.append(f'<text x="16" y="{y + 4}" font-size="12" font-weight="600" fill="{ink}">{title}</text>')
        y += gap - 12
        for q in group:
            cy = y + row_h / 2
            t, g = val[(q, "tabbed")], val[(q, "glance")]
            out.append(f'<text x="16" y="{cy + 4}" font-size="12" fill="{ink}">{q}</text>'
                       f'<text x="64" y="{cy + 4}" font-size="12" fill="{ink2}">{KIND_LABEL[kinds[q]]}</text>')
            out.append(f'<line x1="{x(g["klm_seconds"]):.1f}" y1="{cy}" x2="{x(t["klm_seconds"]):.1f}" y2="{cy}" '
                       f'stroke="#b3b3b3" stroke-width="2"/>')
            for rec, color in ((t, orange), (g, blue)):
                tip = (f'{q} {VIEW_LABEL[rec["view"]]}: {rec["klm_seconds"]:.1f} s · {rec["clicks"]} clicks · '
                       f'{rec["scrolls"]} scrolls · {rec["hovers"]} hovers')
                out.append(f'<circle cx="{x(rec["klm_seconds"]):.1f}" cy="{cy}" r="5" fill="{color}" '
                           f'stroke="#ffffff" stroke-width="2"><title>{tip}</title></circle>')
            out.append(f'<text x="{x(t["klm_seconds"]) + 9:.1f}" y="{cy + 4}" font-size="11" fill="{ink2}">'
                       f'{t["klm_seconds"]:.0f}</text>')
            out.append(f'<text x="{x(g["klm_seconds"]) - 9:.1f}" y="{cy + 4}" font-size="11" fill="{ink2}" '
                       f'text-anchor="end">{g["klm_seconds"]:.0f}</text>')
            y += row_h
        y += 12
    # axis and grid (drawn last, beneath via insertion)
    axis = []
    for s in range(0, xmax + 1, 10):
        axis.append(f'<line x1="{x(s):.1f}" y1="{plot_top - 8}" x2="{x(s):.1f}" y2="{y - 6}" stroke="{grid}" stroke-width="1"/>'
                    f'<text x="{x(s):.1f}" y="{y + 10}" font-size="11" fill="{ink2}" text-anchor="middle">{s}</text>')
    axis.append(f'<text x="{x(xmax / 2):.1f}" y="{y + 28}" font-size="12" fill="{ink2}" text-anchor="middle">'
                f'seconds</text>')
    out[2:2] = axis
    out.append("</svg>")
    return "\n".join(out)


CURRENT = "1.1"
# Earlier versions, kept so the report can show what each redesign changed (oldest first).
EARLIER = {
    "0.2": "before the heuristic-evaluation fixes",
    "0.3": "after the heuristic-evaluation fixes",
}
OUT_MD = ROOT / "docs" / "task_analysis.md"
SENSITIVITY = ROOT / "docs" / "sensitivity" / "task_replay_1920x1080.json"


def version_files(version: str) -> tuple[Path, Path, Path]:
    """Replay JSON, per-question CSV and chart for a version (the current one has no suffix)."""
    suffix = "" if version == CURRENT else f"_v{version}"
    return (ROOT / "docs" / f"task_replay{suffix}.json", ROOT / "docs" / f"task_analysis{suffix}.csv",
            ROOT / "docs" / "figures" / f"task_time{suffix}.svg")


def write_csv(rows: list[dict], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def mean_seconds(rows: list[dict], view: str) -> float:
    sel = [r["klm_seconds"] for r in rows if r["view"] == view]
    return sum(sel) / len(sel)


def summary_table(versions: dict[str, list[dict]]) -> str:
    lines = ["| Version | Cases | View | Clicks | Scrolls | Hovers | Screens | Estimated seconds |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for label, rows in versions.items():
        for s in summarize(rows):
            lines.append(f"| {label} | {s['case_type']} | {VIEW_LABEL[s['view']]} | {s['mean_clicks']:.1f} | "
                         f"{s['mean_scrolls']:.1f} | {s['mean_hovers']:.1f} | {s['mean_screens']:.1f} | "
                         f"{s['mean_klm_seconds']:.1f} |")
    return "\n".join(lines)


def question_table(rows: list[dict]) -> str:
    by: dict[str, dict[str, dict]] = {}
    for r in rows:
        by.setdefault(r["question_id"], {})[r["view"]] = r
    lines = ["| Question | Kind | Tabbed: clicks, scrolls, screens | Tabbed path | NurseGlance: scrolls, hovers | "
             "Seconds (tabbed / NurseGlance) |", "| --- | --- | --- | --- | --- | --- |"]
    for q, d in by.items():
        t, g = d["tabbed"], d["glance"]
        lines.append(f"| {q} | {KIND_LABEL[t['kind']]} | {t['clicks']}, {t['scrolls']}, {t['screens']} | {t['path']} | "
                     f"{g['scrolls']}, {g['hovers']} | {t['klm_seconds']:.1f} / {g['klm_seconds']:.1f} |")
    return "\n".join(lines)


def glance_effort(rows: list[dict]) -> str:
    g = [r for r in rows if r["view"] == "glance"]
    if not any(r["clicks"] or r["scrolls"] or r["hovers"] for r in g):
        return "NurseGlance needed no clicks, scrolls or hovers for any question"
    busy = sum(1 for r in g if r["clicks"] or r["scrolls"] or r["hovers"])
    return f"NurseGlance needed a scroll or hover for {busy} of {len(g)} questions"


def sensitivity_text() -> str:
    if not SENSITIVITY.exists():
        return "No 1920×1080 replay has been run for this version."
    rows = build_rows(json.loads(SENSITIVITY.read_text(encoding="utf-8")))
    return (f"On a 1920×1080 screen (`docs/sensitivity/task_replay_1920x1080.json`), version {CURRENT} gave "
            f"{mean_seconds(rows, 'tabbed'):.1f} s for the tabbed view and {mean_seconds(rows, 'glance'):.1f} s "
            f"for NurseGlance. {glance_effort(rows)}.")


def write_markdown(versions: dict[str, list[dict]], viewport) -> None:
    now = versions[CURRENT]
    head = (f"In version {CURRENT}, the shortest path to an answer took an estimated "
            f"**{mean_seconds(now, 'tabbed'):.1f} s** in the tabbed view and **{mean_seconds(now, 'glance'):.1f} s** "
            f"in NurseGlance, averaged over the 16 questions")
    earlier = [f"version {v}: {mean_seconds(r, 'tabbed'):.1f} s and {mean_seconds(r, 'glance'):.1f} s"
               for v, r in versions.items() if v != CURRENT]
    if earlier:
        head += " (" + "; ".join(reversed(earlier)) + ")"
    head += (f". {glance_effort(now)} on a {viewport[0]}×{viewport[1]} screen. "
             "These are design-level estimates of a scripted expert path, not measurements of nurses.")
    template = (ROOT / "analysis" / "task_analysis_template.md").read_text(encoding="utf-8")
    text = (template.replace("{{HEADLINE}}", head)
            .replace("{{VIEWPORT}}", f"{viewport[0]}×{viewport[1]}")
            .replace("{{SUMMARY}}", summary_table(versions))
            .replace("{{SENSITIVITY}}", sensitivity_text())
            .replace("{{QUESTIONS}}", question_table(now)))
    OUT_MD.write_text(text, encoding="utf-8")


def main() -> int:
    versions: dict[str, list[dict]] = {}
    for version in [*EARLIER, CURRENT]:
        replay_path, _, _ = version_files(version)
        if not replay_path.exists():
            continue
        replay = json.loads(replay_path.read_text(encoding="utf-8"))
        if not replay.get("app_log_matches"):
            print(f"Warning: version {version}: the replay's counts did not match the app's log:",
                  replay.get("problems"))
        versions[version] = build_rows(replay)
    if CURRENT not in versions:
        raise SystemExit(f"{version_files(CURRENT)[0]} is missing: run analysis/replay.py first")
    xmax = (int(max(r["klm_seconds"] for rows in versions.values() for r in rows) / 10) + 1) * 10
    # Earlier versions' CSVs and charts stay as their own runs wrote them; only the current one is rebuilt.
    # The x axis spans every version, so all the charts share one scale.
    _, out_csv, out_svg = version_files(CURRENT)
    write_csv(versions[CURRENT], out_csv)
    out_svg.parent.mkdir(parents=True, exist_ok=True)
    out_svg.write_text(svg_chart(versions[CURRENT], f"Estimated time to find each answer (version {CURRENT})", xmax),
                       encoding="utf-8")
    replay = json.loads(version_files(CURRENT)[0].read_text(encoding="utf-8"))
    write_markdown(versions, replay["viewport"])
    print(f"Wrote the CSVs, charts and {OUT_MD}")
    for label, data_rows in versions.items():
        for s in summarize(data_rows):
            print(f"  {label:4} {s['case_type']:8} {VIEW_LABEL[s['view']]:12} clicks {s['mean_clicks']:4} scrolls "
                  f"{s['mean_scrolls']:4} hovers {s['mean_hovers']:4} screens {s['mean_screens']:4} "
                  f"KLM {s['mean_klm_seconds']:5} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
