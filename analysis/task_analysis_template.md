# Research question 2, part 1: how much work does each view ask for?

{{HEADLINE}}

Produced by `analysis/replay.py` and `analysis/task_analysis.py` (this file is generated
from `analysis/task_analysis_template.md`). Data: `docs/task_replay.json` (version 0.3),
`docs/task_replay_before.json` (version 0.2), and the per-question tables
`docs/task_analysis.csv` and `docs/task_analysis_before.csv`.

## What was measured

- **Tasks:** the 16 study questions, 4 per case (lookup, trend, timing, synthesis), in
  each of the two views.
- **Paths:** for each question and view, the shortest path to the data the answer key
  names: fewest clicks first, then fewest scrolls (`analysis/paths.py`). For a
  synthesis question, the path covers the values that the rubric's first concern needs
  for a score of 2.
- **Replay:** a Playwright script runs the app's own study mode with two seeds whose
  plans are complementary, so each question is answered once in each view, in study
  order. Questions about the same patient follow each other, so a path starts wherever
  the previous one left the tabbed view.
- **Checks:** at the end of each path, the script confirms that every value the path
  names is on screen (or in the hover text), submits the answer key, and compares its
  click and screen counts with the app's own event log. All 32 paths matched the log,
  and the app scored every lookup, trend and timing key as correct.
- **Screen:** {{VIEWPORT}} pixels (a common laptop), Chromium. The study question sits in
  the sidebar, so the main area holds only the view.

## Counting rules

| Count | Rule |
| --- | --- |
| Clicks | A tab, a Meds section or a flowsheet group change. A group change is 2 clicks (open the list, pick the group). |
| Scrolls | One gesture moves the page, a table or a dropdown list by up to 87.5% of its visible height (like Page Down), or 65% of a table's width (its label column stays put). Jumping to the start or end of a table (dragging its scroll bar) is one gesture. For tables, the script tries scrolling from where the table is and jumping to either end first, and keeps the shorter. |
| Hovers | Pointing at a value to read its tooltip or a timeline dose. |
| Screens | 1 plus the number of different tabs opened (the app's own definition). |

## Keystroke-Level Model

Operator times from Card, Moran and Newell (1980), as used by Kieras (2001): pointing
(P) 1.10 s, mouse button press and release (BB) 0.20 s, mental preparation (M) 1.35 s.
Answer entry is left out because it is the same in both views.

| Step | Operators |
| --- | --- |
| Start | M (decide where to look) |
| Each click | M + P + BB |
| Each scroll gesture | M + P (KLM has no scroll operator; P stands for the wheel or drag movement, M for searching what came into view) |
| Each hover | P (the reading is counted below) |
| Each value read | M (a table row, a panel row, a list item or a tooltip) |
| Each extra step | M (for example, compare two values or find the lowest in a row) |

## Results

{{SUMMARY}}

![Estimated seconds per question, version 0.3](figures/task_time.png)

The same chart for version 0.2 is `figures/task_time_before.png`. Both charts share one
scale. On a 1920×1080 screen (`docs/sensitivity/task_replay_1920x1080.json`), version 0.3
gave 12.2 s for the tabbed view and 3.2 s for NurseGlance, again with no NurseGlance
scrolls or hovers.

### Per question, version 0.3

Scroll counts include page scrolls; the path column lists clicks and table scrolls.

{{QUESTIONS}}

## What changed between version 0.2 and 0.3

Both views changed, for reasons recorded in `docs/heuristic_evaluation.md`:

- **NurseGlance** was redesigned so a nurse can answer without scrolling or hovering:
  shorter labels on one line, the 12-hour range printed under each trended value, empty
  elements folded into one line per panel, and a medication strip at the top listing
  every infusion running now and the next dose of each drug with its time.
- **The tabbed view** was made closer to a current EHR, so the comparison is not against
  a straw man: newest columns first, calculated scores (GCS total, Braden, Morse) in the
  flowsheet group where their parts are charted, running infusions listed first, and
  upcoming doses first in the MAR. This made the tabbed view faster too.
- **The study screen** moved the question into the sidebar, which removed most page
  scrolling in both views.

## Limits of these numbers

- They describe an expert who knows where everything is and makes no errors. They are
  design-level estimates, not data from nurses, and they are not evidence that either
  view is safer or better for patients.
- KLM gives every search the same 1.35 s. Finding one value among about 58 on a dense
  screen like NurseGlance likely takes longer than that, so the model probably favors
  NurseGlance. Only the user study can measure search time.
- The no-scroll result for NurseGlance depends on the screen and the questions. All
  eight panels fit on a 1920×1080 screen for all four cases. On 1440×900 they fit for
  the standard cases, but the last rows of the complex cases' lower panels fall below
  the edge (none of the 16 answers is there). On 1366×768 every case needs a scroll.
- Treating a scroll gesture as one pointing operation is an assumption.
- The tabbed view is the author's own control, not a commercial EHR. A real EHR may offer
  shortcuts (search, saved views) or cost more (log-ins, slower screens, more tabs).
- The 16 questions and their answer keys were written by the author for these 4 cases
  and still need clinical review.

## References

- Card SK, Moran TP, Newell A. The keystroke-level model for user performance time with
  interactive systems. Commun ACM. 1980;23(7):396-410.
- Kieras D. Using the keystroke-level model to estimate execution times. University of
  Michigan; 2001.
