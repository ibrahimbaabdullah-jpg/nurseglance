"""Record a captioned demo video of the running app (Playwright + ffmpeg).

Run, with the app on localhost:8501:
    python tools/record_demo.py --out /path/to/nurseglance_demo.mp4

Captions are drawn into the page as it records, so the video reads without sound.
The same captions are written next to the video as an .srt file, and narration.md
beside it is the script to read over it. A pointer is drawn because
headless video shows none. Native hover tooltips do not appear in headless video,
so the demo shows the timeline's hover labels instead.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

W, H = 1440, 900

OVERLAY_JS = r"""
() => {
  if (window.__demo) return;
  const css = document.createElement('style');
  css.textContent = `
    #demo-cap { position: fixed; left: 50%; bottom: 34px; transform: translateX(-50%);
      max-width: 1060px; padding: 14px 24px; border-radius: 12px; z-index: 2147483000;
      background: rgba(18,18,22,.90); color: #fff; font: 500 23px/1.35 "Source Sans 3", "Source Sans Pro", sans-serif;
      text-align: center; box-shadow: 0 6px 24px rgba(0,0,0,.25); transition: opacity .25s; }
    #demo-cap:empty { opacity: 0; }
    #demo-card { position: fixed; inset: 0; z-index: 2147483001; background: #0f1b2d; color: #fff;
      display: none; flex-direction: column; justify-content: center; padding: 0 140px;
      font-family: "Source Sans 3", "Source Sans Pro", sans-serif; }
    #demo-card h1 { font-size: 54px; margin: 0 0 18px; font-weight: 700; letter-spacing: -.5px; }
    #demo-card p { font-size: 27px; line-height: 1.45; margin: 0 0 14px; color: #dfe6f0; }
    #demo-card .small { font-size: 20px; color: #9fb0c6; margin-top: 26px; }
    #demo-card li { font-size: 26px; line-height: 1.4; margin: 0 0 14px; color: #e8eef6; }
    #demo-card ul { padding-left: 28px; margin: 0; }
    .demo-hl { position: fixed; z-index: 2147482999; border: 3px solid #f47230; border-radius: 8px;
      box-shadow: 0 0 0 4px rgba(244,114,48,.22); pointer-events: none; transition: all .3s; }
    #demo-ptr { position: fixed; z-index: 2147483002; width: 22px; height: 30px; pointer-events: none;
      left: -40px; top: -40px; }
  `;
  document.head.appendChild(css);
  const cap = document.createElement('div'); cap.id = 'demo-cap'; document.body.appendChild(cap);
  const card = document.createElement('div'); card.id = 'demo-card'; document.body.appendChild(card);
  const ptr = document.createElement('div'); ptr.id = 'demo-ptr';
  ptr.innerHTML = '<svg viewBox="0 0 22 30" width="22" height="30"><path d="M2 2 L2 24 L8 18 L12 28 L16 26 L12 17 L20 17 Z" fill="#111" stroke="#fff" stroke-width="1.6"/></svg>';
  document.body.appendChild(ptr);
  document.addEventListener('mousemove', e => { ptr.style.left = e.clientX + 'px'; ptr.style.top = e.clientY + 'px'; }, true);
  window.__demo = {
    cap: t => { cap.textContent = t || ''; },
    card: html => { card.innerHTML = html || ''; card.style.display = html ? 'flex' : 'none';
                    ptr.style.display = html ? 'none' : 'block'; },
    hl: (sel, nth) => {
      document.querySelectorAll('.demo-hl').forEach(n => n.remove());
      if (!sel) return false;
      const els = document.querySelectorAll(sel); const el = els[nth || 0];
      if (!el) return false;
      const r = el.getBoundingClientRect(); const b = document.createElement('div');
      b.className = 'demo-hl';
      Object.assign(b.style, {left: (r.left - 6) + 'px', top: (r.top - 6) + 'px',
                              width: (r.width + 12) + 'px', height: (r.height + 12) + 'px'});
      document.body.appendChild(b); return true;
    },
  };
}
"""


class Demo:
    def __init__(self, page):
        self.page = page
        self.t0 = time.monotonic()
        self.cues: list[list] = []

    def now(self) -> float:
        return time.monotonic() - self.t0

    def overlay(self) -> None:
        self.page.evaluate(OVERLAY_JS)

    def close_cue(self) -> None:
        """End the open caption, first holding it long enough to read aloud (about 145 words a minute)."""
        if self.cues and self.cues[-1][1] is None:
            start, _, text = self.cues[-1]
            need = len(text.split()) / 2.4 + 0.8
            if self.now() - start < need:
                self.wait(need - (self.now() - start))
            self.cues[-1][1] = self.now()

    def cap(self, text: str, hold: float = 0.0) -> None:
        self.close_cue()
        self.overlay()
        self.page.evaluate("t => window.__demo.cap(t)", text)
        if text:
            self.cues.append([self.now(), None, text])
        self.wait(hold)

    def card(self, html: str, text: str, hold: float) -> None:
        self.close_cue()
        self.overlay()
        self.page.evaluate("t => window.__demo.cap('')", None)
        self.page.evaluate("h => window.__demo.card(h)", html)
        self.cues.append([self.now(), None, text])
        self.wait(max(hold, len(text.split()) / 2.4 + 0.8))
        self.close_cue()
        self.page.evaluate("() => window.__demo.card('')")

    def hl(self, selector: str | None, nth: int = 0) -> None:
        self.overlay()
        self.page.evaluate("([s, n]) => window.__demo.hl(s, n)", [selector, nth])

    def wait(self, seconds: float) -> None:
        if seconds:
            self.page.wait_for_timeout(int(seconds * 1000))

    def settle(self) -> None:
        self.page.wait_for_timeout(500)
        for _ in range(80):
            if self.page.locator('[data-testid="stStatusWidget"]').count() == 0:
                break
            self.page.wait_for_timeout(200)
        self.page.wait_for_timeout(500)
        self.overlay()

    def point(self, locator, click: bool = False) -> None:
        box = locator.bounding_box()
        if not box:
            return
        x, y = box["x"] + min(box["width"] / 2, 60), box["y"] + box["height"] / 2
        self.page.mouse.move(x, y, steps=18)
        self.wait(0.25)
        if click:
            locator.click()
            self.settle()

    def scroll_main(self, y: int) -> None:
        self.page.evaluate("""y => { const m = document.querySelector('[data-testid="stMain"]');
                                     m.scrollTo({top: y, behavior: 'smooth'}); }""", y)
        self.wait(1.2)

    def finish(self) -> None:
        self.close_cue()


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(cues: list[list], path: Path, offset: float) -> None:
    lines = []
    for i, (a, b, text) in enumerate(cues, start=1):
        lines += [str(i), f"{srt_time(max(0, a - offset))} --> {srt_time(max(0, b - offset))}", text, ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_narration(cues: list[list], path: Path, offset: float, video: Path, seconds: float) -> None:
    mmss = lambda t: f"{int(max(0, t - offset)) // 60}:{int(max(0, t - offset)) % 60:02d}"
    lines = ["# Demo video: narration script", "",
             f"The video (`{video.name}`, {int(seconds) // 60} min {int(seconds) % 60} s, {W}×{H}) is recorded "
             "from the running app by `tools/record_demo.py`. Its captions are drawn into the picture, so it "
             f"works without sound, and `{video.with_suffix('.srt').name}` holds the same captions as subtitles.",
             "",
             "To add a voice-over, read each line when its caption appears. Each caption stays up long enough "
             "to read aloud at about 145 words a minute. After any change to the app, record again with "
             "`python tools/record_demo.py --out docs/video/nurseglance_demo.mp4` (app running on port 8501).",
             "", "| Start | End | Narration |", "| --- | --- | --- |"]
    lines += [f"| {mmss(a)} | {mmss(b)} | {text} |" for a, b, text in cues]
    lines += ["", "Research prototype, not for clinical use. Click and time figures in the video are "
              "design-level estimates from scripted runs, not measurements of nurses.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def sidebar_pick(demo: Demo, label: str) -> None:
    sb = demo.page.locator('[data-testid="stSidebar"]')
    demo.point(sb.get_by_text(label, exact=True), click=True)


def pick_patient(demo: Demo, prefix: str) -> None:
    page = demo.page
    box = page.locator('[data-testid="stSidebar"] [data-testid="stSelectbox"]').first
    demo.point(box)
    box.locator("input").click()
    opts = page.locator('[role="option"]')
    opts.first.wait_for()
    for i in range(opts.count()):
        if opts.nth(i).inner_text().startswith(prefix):
            demo.point(opts.nth(i), click=True)
            return
    raise SystemExit(f"no patient option starting with {prefix}")


def run(url: str, out: Path) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="ngvideo-"))
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": W, "height": H}, record_video_dir=str(tmp),
                                  record_video_size={"width": W, "height": H})
        page = ctx.new_page()
        demo = Demo(page)
        page.goto(url)
        page.wait_for_selector('[data-testid="stSidebar"]')
        demo.settle()
        pick_patient(demo, "C1")
        demo.page.mouse.move(W - 40, H - 40)
        start = demo.now()

        demo.card("<h1>NurseGlance</h1><p>A nurse-centered ICU handoff dashboard built on HL7 FHIR data.</p>"
                  "<p>It compares an organ-system view with a tabbed EHR-style view of the same patients.</p>"
                  "<p class='small'>Research prototype, not for clinical use · de-identified MIMIC-IV demo data, "
                  "dates shifted</p>",
                  "NurseGlance: a nurse-centered ICU handoff dashboard built on HL7 FHIR data. "
                  "Research prototype, not for clinical use.", 7)

        # The control view
        demo.cap("The control: a tabbed EHR-style view of the same FHIR data, here for a ventilated "
                 "patient on two vasopressors.")
        sidebar_pick(demo, "Tabbed EHR view (control)")
        main = page.locator('[data-testid="stMain"]')
        demo.wait(4)
        demo.hl('[data-testid="stDataFrame"]')
        demo.cap("Vitals sit in flowsheet groups, one table per group, newest column first.", 5)
        demo.hl(None)
        demo.cap("Labs are one long table: 94 results for this patient in the last 72 hours.")
        demo.point(main.get_by_text("Labs", exact=True).first, click=True)
        demo.wait(4.5)
        demo.cap("Drips and doses are under another tab, in sections. Answering one handoff question "
                 "can mean several tabs and scrolls.")
        demo.point(main.get_by_text("Meds", exact=True).first, click=True)
        demo.point(main.get_by_text("Infusions", exact=True).first, click=True)
        demo.wait(5)

        # NurseGlance
        demo.cap("NurseGlance shows the same patient on one screen, organized by organ system.")
        sidebar_pick(demo, "NurseGlance (organ systems)")
        demo.wait(4.5)
        demo.hl(".ng-meds")
        demo.cap("At the top: every infusion running now with its rate, and the next dose of each drug "
                 "in the 12 hours after handoff.", 8)
        demo.hl('.ng-row[data-eid="map"]')
        demo.point(page.locator('.ng-row[data-eid="map"]'))
        demo.cap("Each value shows the latest reading, a trend arrow, the 12-hour range and a sparkline. "
                 "An H or L badge marks a value outside its threshold.", 8)
        demo.hl('.ng-row[data-eid="vasoactive_drips"]')
        demo.point(page.locator('.ng-row[data-eid="vasoactive_drips"]'))
        demo.cap("Drips show their rate, the last titration and when they started.", 6)
        demo.hl(".ng-empty", 0)
        demo.cap("\"None\", \"not charted\" and \"not in FHIR demo\" stay separate, so a true negative "
                 "is never mistaken for missing data.", 7)
        demo.hl(None)
        demo.cap("")
        plot = page.locator(".js-plotly-plot").first
        plot.scroll_into_view_if_needed()
        demo.settle()
        demo.cap("Below the panels, a 12-hour timeline shows each dose and infusion after handoff. "
                 "Pointing at a dose shows its name and time.", 3)
        pts = page.locator(".js-plotly-plot .scatterlayer .points path")
        if pts.count():
            target = pts.nth(min(3, pts.count() - 1))
            box = target.bounding_box()
            if box:
                page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=20)
        demo.wait(5)
        demo.scroll_main(0)

        # Flags
        flag_box = page.locator('[data-testid="stSidebar"] [data-testid="stCheckbox"]').get_by_text("Rule-based flags")
        demo.cap("Optional rule-based flags. Each one shows its rule, the values, their times and FHIR ids. "
                 "Thresholds are placeholders, and flags are off in study mode.")
        demo.point(flag_box, click=True)
        demo.wait(8)
        demo.point(flag_box, click=True)

        # Study mode
        demo.cap("Study mode runs an AWARE-style crossover session, start to finish.")
        sidebar_pick(demo, "Study session")
        demo.wait(3)
        page.get_by_label("Run ID").click()
        page.keyboard.type("DEMO1", delay=90)
        field = page.get_by_test_id("stNumberInputField")
        field.click()
        field.fill("")
        page.keyboard.type("6", delay=90)
        field.press("Tab")
        demo.cap("A logged seed sets the view order and which patients go with each view.", 3)
        demo.point(page.get_by_role("button", name="Start session"), click=True)
        demo.wait(1.5)
        demo.hl('[data-testid="stSidebar"] [data-testid="stForm"]')
        demo.cap("The question stays beside the view. Every click, screen and answer is logged with its time.", 6)
        demo.hl('.ng-meds')
        demo.cap("Here the answer is in the infusion strip: norepinephrine 0.2 mcg/kg/min.", 5)
        demo.hl(None)
        form = page.locator('[data-testid="stForm"]').first
        form.locator('input[type="text"]').first.click()
        page.keyboard.type("0.2", delay=120)
        demo.point(form.get_by_role("button", name="Submit answer"), click=True)
        demo.cap("After each view come the System Usability Scale and NASA-TLX, and the session exports "
                 "CSV files for analysis.", 7)
        abandon = page.get_by_role("button", name="Abandon session")
        if abandon.count():
            abandon.click()
            demo.settle()

        # Virtual-nurse mode
        demo.cap("Virtual-nurse mode: admission and discharge checklists, a session timer, and a break "
                 "prompt at 10 minutes.")
        sidebar_pick(demo, "Virtual-nurse mode")
        demo.wait(4)
        boxes = page.locator('[data-testid="stMain"] [data-testid="stCheckbox"]')
        for i in range(min(3, boxes.count())):
            demo.point(boxes.nth(i), click=True)
        demo.cap("Virtual nurses showed cognitive fatigue within about 10 to 12 minutes of an encounter "
                 "in a 2025 eye-tracking study.", 7)
        demo.cap("")

        demo.card("<h1>What the prototype shows so far</h1><ul>"
                  "<li>FHIR can supply 57 of 58 nurse handoff data elements (98%).</li>"
                  "<li>Scripted expert paths: 3.2 s per question in NurseGlance against 12.9 s in the tabbed "
                  "view, with no clicks or scrolls. These are design-level estimates, not nurse data.</li>"
                  "<li>A heuristic evaluation found 10 major usability problems; version 0.3 fixed them.</li>"
                  "<li>Next: a crossover study with 40 ICU and virtual nurses, after IRB approval.</li></ul>",
                  "So far: FHIR can supply 57 of 58 handoff elements. Scripted expert paths take 3.2 s per "
                  "question in NurseGlance against 12.9 s in the tabbed view (design-level estimates, not "
                  "nurse data). Next: a crossover study with ICU and virtual nurses, after IRB approval.", 16)
        demo.card("<h1>NurseGlance</h1>"
                  "<p>Code, reports and protocol: github.com/ibrahimbaabdullah-jpg/nurseglance</p>"
                  "<p>Ibrahim Baabdallah · 2026</p>"
                  "<p class='small'>Research prototype, not for clinical use. Data: MIMIC-IV Clinical Database "
                  "Demo on FHIR v2.1.0 (PhysioNet, ODbL).</p>",
                  "Code, reports and protocol: github.com/ibrahimbaabdullah-jpg/nurseglance.", 6)
        demo.finish()
        video = page.video.path()
        ctx.close()
        browser.close()
    raw = Path(video)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Trim the page load before the title card, then encode H.264 for wide playback.
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-i", str(raw),
                    "-c:v", "libx264", "-preset", "medium", "-crf", "26", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", "-an", str(out)], check=True)
    write_srt(demo.cues, out.with_suffix(".srt"), start)
    seconds = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                    "default=nw=1:nk=1", str(out)], capture_output=True, text=True).stdout)
    write_narration(demo.cues, out.parent / "narration.md", start, out, seconds)
    shutil.rmtree(tmp, ignore_errors=True)
    print(out, f"{demo.now() - start:.0f} s")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", default="http://localhost:8501")
    ap.add_argument("--out", type=Path, required=True)
    run(**vars(ap.parse_args()))


if __name__ == "__main__":
    main()
