#!/usr/bin/env python3
"""Replay every task-analysis path in the running app, count its steps and check the answer is on screen.

    streamlit run streamlit_app.py &            # the app must be running
    pip install -r requirements-analysis.txt    # Playwright for Python, then: playwright install chromium
    python analysis/replay.py                   # -> docs/task_replay.json

Two study sessions are run with seeds whose plans are complementary (seed 2 puts
S2 and C2 in NurseGlance and S1 and C1 in the tabbed view; seed 6 the reverse), so
each of the 16 questions is answered once in each view, in study order. For each
question the script follows the path in analysis/paths.py and counts:

  clicks   tab, Meds section and flowsheet group changes (a group change is 2 clicks)
  scrolls  scroll gestures of the page, a table or a dropdown list. One gesture moves
           up to 87.5% of the visible height (65% of the width for tables, whose
           pinned label column does not move), like Page Down. A jump to the top or
           end of a table (dragging its scroll bar) is one gesture.
  hovers   pointing at a value to read its tooltip or a timeline dose
  targets  values read (one per table row, row or list item)

For tables it tries scrolling from where the table is, and jumping to either end
first, and keeps whichever needs fewer gestures. It checks that every value the
path names is on screen (or in the tooltip) at the end, submits the answer key,
and finally compares its click counts with the app's own event log.

These counts are design-level estimates of a scripted expert path, not user data.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.paths import PATHS, SYNTHESIS_ANSWERS  # noqa: E402
from app import data, study, tabbed  # noqa: E402

SEEDS = (2, 6)
PAGE_STEP, GRID_V_STEP, GRID_H_STEP, LIST_STEP = 0.875, 0.875, 0.65, 0.875
SETTLE_MS = 1400

HELPERS = r"""
() => {
  if (window.__ta) return;
  const ta = {};
  ta.main = () => document.querySelector('[data-testid="stMain"]');
  ta.top = () => { const h = document.querySelector('[data-testid="stHeader"]'); return h ? Math.max(0, h.getBoundingClientRect().bottom) : 0; };
  ta.fit = (el) => {                       // signed page scroll that brings el fully into view
    const r = el.getBoundingClientRect(), top = ta.top(), bot = window.innerHeight;
    if (r.top < top || r.height > bot - top) return r.top - top - 8;
    if (r.bottom > bot) return r.bottom - bot + 8;
    return 0;
  };
  ta.grid = () => { const g = [...document.querySelectorAll('[data-testid="stDataFrame"]')];
                    return g.length ? g[0] : null; };
  ta.sc = () => ta.grid().querySelector('.dvn-scroller');
  ta.geom = () => { const s = ta.sc(), t = ta.grid().querySelector('table');
    const n = +t.getAttribute('aria-rowcount'); const rh = s.scrollHeight / n;
    return {top: s.scrollTop, left: s.scrollLeft, h: s.clientHeight, w: s.clientWidth,
            maxTop: s.scrollHeight - s.clientHeight, maxLeft: s.scrollWidth - s.clientWidth, rh, n: n - 1}; };
  ta.cols = () => [...ta.grid().querySelectorAll('thead th')].map(t => t.innerText.trim());
  ta.rows = () => [...ta.grid().querySelectorAll('tbody tr')].map(tr => ({
      idx: +tr.getAttribute('aria-rowindex') - 2, cells: [...tr.children].map(c => c.innerText.trim())}));
  ta.match = (m) => {                       // first visible row matching a label or a list of strings
    const g = ta.geom();
    for (const r of ta.rows()) {
      const ok = typeof m === 'string' ? r.cells[0] === m
        : m.every(s => r.cells.some(c => c.toLowerCase().includes(s.toLowerCase())));
      if (!ok) continue;
      const y = g.rh + r.idx * g.rh - g.top;
      return {idx: r.idx, cells: r.cells, full: y >= g.rh - 0.5 && y + g.rh <= g.h + 0.5};
    }
    return null;
  };
  ta.synced = () => {                      // has the accessible table caught up with the scroll position?
    const g = ta.geom(), r = ta.rows();
    if (!r.length) return g.n === 0;
    const first = Math.floor(g.top / g.rh), idx = r.map(x => x.idx);
    const cols = ta.cols(), left = g.left;
    return Math.min(...idx) <= first && Math.max(...idx) >= first && (left > 0 || cols[0] !== undefined);
  };
  window.__ta = ta;
}
"""


class PathError(RuntimeError):
    pass


class Replay:
    def __init__(self, page, shots: Path | None):
        self.p = page
        self.shots = shots

    # ------------------------------------------------------------- basics
    def js(self, expr, arg=None):
        self.p.evaluate(HELPERS)
        return self.p.evaluate(expr, arg) if arg is not None else self.p.evaluate(expr)

    def settle(self, ms=SETTLE_MS):
        """Wait for Streamlit to finish rerunning after a click."""
        self.p.wait_for_timeout(400)
        for _ in range(60):
            busy = self.p.evaluate("""() => !!document.querySelector('[data-testid="stStatusWidget"]')
                || !!document.querySelector('[data-stale="true"]')""")
            if not busy:
                break
            self.p.wait_for_timeout(200)
        self.p.wait_for_timeout(max(0, ms - 400))

    def page_fit(self, locator) -> int:
        """Scroll the page until locator is fully in view; return the gestures used."""
        locator.first.wait_for(state="attached", timeout=8000)
        handle = locator.first.element_handle()
        delta = self.js("el => __ta.fit(el)", handle)
        if abs(delta) < 1:
            return 0
        step = PAGE_STEP * self.js("() => __ta.main().clientHeight")
        self.js(f"() => __ta.main().scrollBy(0, {delta})")
        self.p.wait_for_timeout(250)
        return math.ceil(abs(delta) / step)

    def grid_wait(self):
        self.p.wait_for_timeout(120)
        for _ in range(20):
            if self.js("() => __ta.synced()"):
                break
            self.p.wait_for_timeout(100)
        self.p.wait_for_timeout(80)

    def reset_view(self):
        self.js("() => { __ta.main().scrollTo(0, 0); }")
        if self.js("() => !!__ta.grid()"):
            self.js("() => { const s = __ta.sc(); s.scrollTop = 0; s.scrollLeft = 0; }")
        self.p.wait_for_timeout(300)

    # ------------------------------------------------------------- tabbed controls
    def current_group(self):
        box = self.p.locator('[data-testid="stSelectbox"]').filter(has_text="Flowsheet group")
        for _ in range(30):
            if box.count():
                value = box.first.locator('input[role="combobox"]').input_value()
                if value:
                    return value
            self.p.wait_for_timeout(200)
        return None

    def radio(self, anchor_text):
        return self.p.locator('[data-testid="stRadio"]').filter(has_text=anchor_text).first

    def checked(self, radio) -> str:
        return radio.locator("label:has(input:checked)").inner_text().strip()

    def click_radio(self, anchor, name, rec):
        radio = self.radio(anchor)
        if self.checked(radio) == name:
            raise PathError(f"'{name}' is already selected; the path step is not needed")
        rec["scroll_page"] += self.page_fit(radio)
        radio.get_by_text(name, exact=True).click()
        self.settle()

    def choose_group(self, name, case, rec):
        box = self.p.locator('[data-testid="stSelectbox"]').filter(has_text="Flowsheet group").first
        if self.current_group() == name:
            raise PathError(f"flowsheet group '{name}' is already selected")
        rec["scroll_page"] += self.page_fit(box)
        box.click()
        self.p.wait_for_timeout(500)
        listbox = self.p.locator('[role="listbox"]').first
        groups = vitals_groups(case)
        idx = groups.index(name)
        opt_h = self.p.locator('[role="option"]').first.bounding_box()["height"]
        list_h = listbox.bounding_box()["height"]
        need = max(0.0, (idx + 1) * opt_h - list_h)
        rec["scroll_list"] += math.ceil(need / (LIST_STEP * list_h)) if need > 0 else 0
        self.p.get_by_role("option", name=name, exact=True).click()   # Playwright scrolls the list for us
        self.settle()

    # ------------------------------------------------------------- tables
    def grid_rows(self, matcher, rec):
        """Bring a matching row fully into view inside the table, with the fewest gestures."""
        hit = self.js("m => __ta.match(m)", matcher)
        if hit and hit["full"]:
            return hit
        g = self.js("() => __ta.geom()")
        step = GRID_V_STEP * (g["h"] - g["rh"])
        start = g["top"]
        best = None
        for plan in ("down", "up", "end_up", "home_down"):
            self.js(f"() => {{ __ta.sc().scrollTop = {start}; }}")
            self.p.wait_for_timeout(120)
            n = 0
            if plan == "end_up":
                self.js("() => { const s = __ta.sc(); s.scrollTop = s.scrollHeight; }")
                n = 1
            elif plan == "home_down":
                self.js("() => { __ta.sc().scrollTop = 0; }")
                n = 1
            direction = -1 if plan in ("up", "end_up") else 1
            for _ in range(80):
                self.grid_wait()
                hit = self.js("m => __ta.match(m)", matcher)
                if hit and hit["full"]:
                    break
                g2 = self.js("() => __ta.geom()")
                at_edge = g2["top"] <= 0.5 if direction < 0 else g2["top"] >= g2["maxTop"] - 0.5
                if at_edge:
                    hit = None
                    break
                self.js(f"() => {{ __ta.sc().scrollTop += {direction * step}; }}")
                n += 1
            if hit and hit["full"] and (best is None or n < best[0]):
                best = (n, plan, self.js("() => __ta.sc().scrollTop"))
        if best is None:
            raise PathError(f"row {matcher!r} not found in the table")
        self.js(f"() => {{ __ta.sc().scrollTop = {best[2]}; }}")
        self.p.wait_for_timeout(200)
        rec["scroll_grid"] += best[0]
        rec["log"].append(f"table rows {matcher!r}: {best[0]} gesture(s) ({best[1]})")
        return self.js("m => __ta.match(m)", matcher)

    def grid_cols(self, targets: list[str], rec):
        """Scroll sideways until every target column has been on screen (scanning passes those between)."""
        want = set(targets)
        if want <= set(self.js("() => __ta.cols()")):
            return
        g = self.js("() => __ta.geom()")
        step = GRID_H_STEP * g["w"]
        start = g["left"]
        best = None
        for plan in ("right", "left", "end_left", "home_right"):
            self.js(f"() => {{ __ta.sc().scrollLeft = {start}; }}")
            self.p.wait_for_timeout(120)
            n, seen = 0, set()
            if plan == "end_left":
                self.js("() => { const s = __ta.sc(); s.scrollLeft = s.scrollWidth; }")
                n = 1
            elif plan == "home_right":
                self.js("() => { __ta.sc().scrollLeft = 0; }")
                n = 1
            direction = -1 if plan in ("left", "end_left") else 1
            for _ in range(60):
                self.grid_wait()
                self.p.wait_for_timeout(250)   # column headers update a little after rows
                seen |= want & set(self.js("() => __ta.cols()"))
                if seen == want:
                    break
                g2 = self.js("() => __ta.geom()")
                at_edge = g2["left"] <= 0.5 if direction < 0 else g2["left"] >= g2["maxLeft"] - 0.5
                if at_edge:
                    break
                self.js(f"() => {{ __ta.sc().scrollLeft += {direction * step}; }}")
                n += 1
            if seen == want and (best is None or n < best[0]):
                best = (n, plan, self.js("() => __ta.sc().scrollLeft"))
        if best is None:
            raise PathError(f"columns {targets} not reachable")
        self.js(f"() => {{ __ta.sc().scrollLeft = {best[2]}; }}")
        self.p.wait_for_timeout(200)
        rec["scroll_grid"] += best[0]
        rec["log"].append(f"table columns {targets}: {best[0]} gesture(s) ({best[1]})")

    def check_cells(self, row, cols):
        """Read the visible target cells of a row (retrying while the table renders)."""
        shown = {}
        for _ in range(10):
            self.p.wait_for_timeout(300)
            hit = self.js("m => __ta.match(m)", row)
            visible = self.js("() => __ta.cols()")
            shown = {c: hit["cells"][visible.index(c)] for c in cols if hit and c in visible}
            if shown and all(shown.values()):   # targets now off screen were seen while scanning
                return shown
        raise PathError(f"{row}: expected values at {cols}, saw {shown}")

    def do_grid(self, step, case, rec):
        grid_loc = self.p.locator('[data-testid="stDataFrame"]').first
        rec["scroll_page"] += self.page_fit(grid_loc)
        labels = [r for r in step["rows"] if isinstance(r, str)]
        rec["targets"] += len(step["rows"])
        for row in step["rows"]:
            if not isinstance(row, str):
                hit = self.grid_rows(row, rec)
                rec["seen"].append({" + ".join(row): " | ".join(hit["cells"])})
        if not labels:
            return
        cols = {row: resolve_cols(case, step["table"], row, step["cols"], rec.get("vitals_group")) for row in labels}
        self.grid_rows(labels[0], rec)
        together = all((self.js("m => __ta.match(m)", row) or {}).get("full") for row in labels)
        if together:   # rows on screen at once are scanned in one sideways pass
            self.grid_cols(sorted({c for cs in cols.values() for c in cs}), rec)
            for row in labels:
                rec["seen"].append({row: self.check_cells(row, cols[row])})
            return
        for n, row in enumerate(labels):
            if n:
                self.grid_rows(row, rec)
            self.grid_cols(cols[row], rec)
            rec["seen"].append({row: self.check_cells(row, cols[row])})

    # ------------------------------------------------------------- NurseGlance
    def glance_locator(self, step):
        if step["kind"] == "row":
            return self.p.locator(".ng-row").filter(
                has=self.p.locator(".ng-label", has_text=step["label"])).filter(
                has=self.p.locator(f'.ng-label:text-is("{step["label"]}")'))
        if step["kind"] == "li":
            return self.p.locator(".ng-list li").filter(has_text=step["text"])
        if step["kind"] == "ytick":
            return self.p.locator(".js-plotly-plot .ytick text").filter(has_text=step["text"])
        raise ValueError(step)

    def do_see(self, step, rec):
        loc = self.glance_locator(step)
        rec["scroll_page"] += self.page_fit(loc)
        text = loc.first.text_content() or ""
        if step["expect"] not in text:
            raise PathError(f"{step} : saw {text!r}")
        rec["targets"] += 1
        rec["seen"].append({step.get("label") or step.get("text"): " ".join(text.split())})

    def do_hover(self, step, rec):
        if step["kind"] == "row":
            loc = self.glance_locator(step)
            rec["scroll_page"] += self.page_fit(loc)
            loc.first.hover()
            self.p.wait_for_timeout(300)
            text = loc.first.get_attribute("title") or ""
        else:
            plot = self.p.locator(".js-plotly-plot").first
            ti, pi = plot.evaluate("""(gd, a) => {
                const t = gd.data.findIndex(d => String((d.y || [''])[0]).toLowerCase().includes(a[0].toLowerCase())
                                                  && d.mode === 'markers');
                const k = t < 0 ? -1 : (gd.data[t].text || []).findIndex(s => s.includes(a[1]));
                return [t, k]; }""", [step["name"], step["expect"]])
            if ti < 0 or pi < 0:
                raise PathError(f"no timeline dose for {step}")
            point = plot.locator(".scatterlayer .trace").nth(ti).locator(".points path").nth(pi)
            rec["scroll_page"] += self.page_fit(point)
            box = point.bounding_box()
            self.p.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            self.p.wait_for_timeout(500)
            text = self.p.locator(".js-plotly-plot .hoverlayer").first.text_content() or ""
        if step["expect"] not in text:
            raise PathError(f"{step}: hover text {text!r}")
        rec["hovers"] += 1
        rec["targets"] += 1
        rec["seen"].append({step.get("label") or step.get("name"): " ".join(text.split())[:160]})

    # ------------------------------------------------------------- one question
    def run_path(self, qid, view, case):
        rec = {"question_id": qid, "view": view, "case_id": case["case_id"], "clicks": 0,
               "app_interactions_expected": 0, "tabs": [], "scroll_page": 0, "scroll_grid": 0,
               "scroll_list": 0, "hovers": 0, "targets": 0, "think": 0, "think_why": [],
               "seen": [], "log": []}
        if view == "tabbed":
            box = self.p.locator('[data-testid="stSelectbox"]').filter(has_text="Flowsheet group")
            rec["vitals_group"] = self.current_group() if box.count() else None
        for step in PATHS[qid][view]:
            kind = step["do"]
            if kind == "tab":
                self.click_radio("Notes/Problems", step["name"], rec)
                rec["clicks"] += 1
                rec["app_interactions_expected"] += 1
                rec["tabs"].append(step["name"])
                if step["name"] == "Vitals":
                    rec["vitals_group"] = self.current_group()
            elif kind == "section":
                self.click_radio("Active orders", step["name"], rec)
                rec["clicks"] += 1
                rec["app_interactions_expected"] += 1
            elif kind == "group":
                self.choose_group(step["name"], case, rec)
                rec["vitals_group"] = step["name"]
                rec["clicks"] += 2
                rec["app_interactions_expected"] += 1
            elif kind == "grid":
                self.do_grid(step, case, rec)
            elif kind == "see":
                self.do_see(step, rec)
            elif kind == "hover":
                self.do_hover(step, rec)
            elif kind == "think":
                rec["think"] += step["n"]
                rec["think_why"].append(step["why"])
            rec["log"].append(f"{kind}: {step.get('name') or step.get('label') or step.get('text') or ''}".strip())
        rec["screens"] = 1 + len(set(rec["tabs"])) if view == "tabbed" else 1
        rec.pop("vitals_group", None)
        if self.shots:
            self.p.screenshot(path=str(self.shots / f"{qid}_{view}.png"))
        return rec


# ------------------------------------------------------------- data helpers (same code as the app)

def vitals_groups(case) -> list[str]:
    df = tabbed._obs_frame(case)
    ref = data.handoff(case)
    chart = df[(df["source"] != "labevents") & (df["t"] >= ref - timedelta(hours=24))]
    return sorted(chart["category"].dropna().unique())


def resolve_cols(case, table, label, specs, group) -> list[str]:
    df = tabbed._obs_frame(case)
    ref = data.handoff(case)
    if table == "labs":
        pv = tabbed._pivot(df[df["source"] == "labevents"])
    else:
        chart = df[(df["source"] != "labevents") & (df["t"] >= ref - timedelta(hours=24))]
        pv = tabbed._pivot(chart[chart["category"] == group])
    row = pv.loc[label]
    filled = [c for c in pv.columns if row[c] != ""]
    out = []
    for spec in specs:
        if spec == "last":
            out.append(filled[-1])
        elif spec == "window":
            year = ref.year
            start = ref - timedelta(hours=12)
            inside = [c for c in filled if data.ts(f"{year}-{c}") >= start]
            out += [inside[0], inside[-1]]
        elif spec.startswith("find:"):
            out.append(next(c for c in filled if str(row[c]).startswith(spec[5:])))
    return list(dict.fromkeys(out))


def answer_for(q) -> str:
    if q["answer_type"] == "text":
        return SYNTHESIS_ANSWERS[q["id"]]
    if q["answer_type"] == "number":
        return data.fmt_num(q["answer"])
    return str(q["answer"])


# ------------------------------------------------------------- session driver

def run_session(page, seed: int, shots: Path | None, url: str) -> tuple[list[dict], list[dict]]:
    r = Replay(page, shots)
    page.goto(url)
    page.wait_for_timeout(4000)
    page.get_by_text("Study session", exact=True).click()
    page.wait_for_timeout(2000)
    steps = study.make_steps(study.make_plan(seed), study.load_questions())
    first = steps[0]
    expect = f"{study.VIEW_NAMES[first['view']]} · patient {first['case_id']}"
    for _attempt in range(4):
        page.get_by_label("Run ID").fill(f"TA{seed}")
        field = page.get_by_test_id("stNumberInputField")
        field.fill(str(seed))
        field.press("Tab")
        page.wait_for_timeout(800)
        page.get_by_role("button", name="Start session").click()
        page.wait_for_timeout(3000)
        if expect in page.get_by_text("Question 1 of 16").first.inner_text():
            break
        page.get_by_role("button", name="Abandon session").click()   # the seed did not take; start again
        page.wait_for_timeout(2500)
        page.get_by_text("Study session", exact=True).click()
        page.wait_for_timeout(2000)
    else:
        raise SystemExit(f"could not start a session with seed {seed}")
    records = []
    for step in steps:
        if step["kind"] == "question":
            q, view = step["question"], step["view"]
            form = page.locator('[data-testid="stForm"]').first
            try:
                form.get_by_text(q["text"], exact=True).wait_for(timeout=10000)
            except Exception:
                page.screenshot(path="/tmp/claude-0/replay_fail.png", full_page=True)
                raise
            r.reset_view()
            case = data.load_case(step["case_id"])
            try:
                rec = r.run_path(q["id"], view, case)
            except PathError as err:
                page.screenshot(path="/tmp/claude-0/replay_fail.png")
                raise SystemExit(f"{q['id']} {view}: {err}")
            rec["seed"] = seed
            records.append(rec)
            print(f"seed {seed} {q['id']:6} {view:7} clicks {rec['clicks']} scrolls "
                  f"{rec['scroll_page'] + rec['scroll_grid'] + rec['scroll_list']} hovers {rec['hovers']}")
            r.js("() => __ta.main().scrollTo(0, 0)")
            answer = answer_for(q)
            if q["answer_type"] == "choice":
                form.get_by_text(answer, exact=True).click()
            elif q["answer_type"] == "text":
                form.locator("textarea").fill(answer)
            else:
                form.locator('input[type="text"]').first.fill(answer)
            page.wait_for_timeout(300)
            form.get_by_role("button", name="Submit answer").click()
            page.wait_for_timeout(SETTLE_MS + 600)
        elif step["kind"] == "survey":
            page.get_by_text("System Usability Scale").wait_for(timeout=10000)
            items = page.locator('[data-testid="stForm"] [data-testid="stRadio"]')
            for i in range(items.count()):
                items.nth(i).get_by_text("3", exact=True).click()
                page.wait_for_timeout(120)
            page.get_by_role("button", name="Submit ratings").click()
            page.wait_for_timeout(SETTLE_MS + 600)
    page.get_by_text("Session complete").wait_for(timeout=10000)
    with page.expect_download() as dl:
        page.get_by_role("button", name="Download summary (CSV)").click()
    summary = list(csv.DictReader(io.StringIO(Path(dl.value.path()).read_text(encoding="utf-8"))))
    return records, summary


def main(argv=None) -> int:
    from playwright.sync_api import sync_playwright

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://localhost:8501")
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "task_replay.json")
    ap.add_argument("--shots", type=Path, default=None, help="folder for an end-of-path screenshot per question")
    args = ap.parse_args(argv)
    if args.shots:
        args.shots.mkdir(parents=True, exist_ok=True)

    all_records, problems = [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for seed in SEEDS:
            ctx = browser.new_context(viewport={"width": args.width, "height": args.height}, accept_downloads=True)
            page = ctx.new_page()
            records, summary = run_session(page, seed, args.shots, args.url)
            by_q = {row["question_id"]: row for row in summary}
            for rec in records:
                app = by_q.get(rec["question_id"], {})
                rec["app_interactions"] = int(app.get("interactions") or 0)
                rec["app_screens"] = int(app.get("screens_visited") or 0)
                rec["app_correct"] = app.get("correct", "")
                if rec["app_interactions"] != rec["app_interactions_expected"]:
                    problems.append(f"{rec['question_id']} {rec['view']}: app logged {rec['app_interactions']} "
                                    f"interactions, path has {rec['app_interactions_expected']}")
                if rec["app_screens"] != rec["screens"]:
                    problems.append(f"{rec['question_id']} {rec['view']}: app logged {rec['app_screens']} "
                                    f"screens, path has {rec['screens']}")
                if rec["app_correct"] == "0":
                    problems.append(f"{rec['question_id']} {rec['view']}: the app scored the key as wrong")
            all_records += records
            ctx.close()
        browser.close()

    out = {"viewport": [args.width, args.height], "seeds": list(SEEDS),
           "steps": {"page": PAGE_STEP, "table_vertical": GRID_V_STEP, "table_horizontal": GRID_H_STEP,
                     "list": LIST_STEP},
           "app_log_matches": not problems, "problems": problems,
           "records": sorted(all_records, key=lambda r: (r["question_id"], r["view"]))}
    args.out.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(all_records)} paths to {args.out}")
    for line in problems:
        print("  PROBLEM", line)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
