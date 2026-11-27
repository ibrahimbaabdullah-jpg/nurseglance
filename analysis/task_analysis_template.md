# Research question 2, part 1: how much work does each view ask for?

{{HEADLINE}}

Produced by `analysis/replay.py` and `analysis/task_analysis.py` (this file is generated
from `analysis/task_analysis_template.md`). Data: `docs/task_replay.json` and the
per-question table `docs/task_analysis.csv` (version 1.1); the earlier versions' runs are
kept as `docs/task_replay_v0.2.json`, `docs/task_replay_v0.3.json` and their CSVs.

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
  the previous one left the tabbed view, which opens on its Summary tab. The two
  practice questions before each view are answered but not measured.
- **Checks:** at the end of each path, the script confirms that every value the path
  names is on screen (or in the hover text), submits the answer key, and compares its
  click and screen counts with the app's own event log. All 32 paths matched the log,
  and the app scored every lookup, trend and timing key as correct.
- **Screen:** {{VIEWPORT}} pixels (a common laptop), Chromium. The study question sits in
  the sidebar, so the main area holds only the view.

## Counting rules

| Count | Rule |
| --- | --- |
| Clicks | A tab, a MAR section or a Flowsheet section change. A Flowsheet section change is 2 clicks (open the list, pick the section). |
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

![Estimated seconds per question, version 1.1](figures/task_time.png)

The same chart for earlier versions is `figures/task_time_v0.3.png` and
`figures/task_time_v0.2.png`. All the charts share one scale. {{SENSITIVITY}}

### Per question, version 1.1

Scroll counts include page scrolls; the path column lists clicks and table scrolls.

{{QUESTIONS}}

## Version 1.2: the same paths in the new look

Version 1.2 gives both views the look of a design mockup (white top bar and cards,
Inter and Space Grotesk; see `docs/design/`). NurseGlance keeps one patient on one
1440×900 screen: vasoactive and sedation drips sit in their organ-system cards, the other
infusions in the patient card, and due doses in a Tasks & meds column. The replay was run
again on version 1.2 at 1440×900 (`docs/sensitivity/task_replay_1440x900_v1.2.json`):
all 32 paths gave the same clicks, scrolls, hovers, targets and screens as version 1.1,
the app's event log matched every path, and in study mode every NurseGlance card of every case now
ends above the bottom of a 1440×900 screen. The numbers above therefore hold for
version 1.2. Version 1.2.1 was replayed twice more at 1440×900 (`docs/sensitivity/task_replay_1440x900_v1.2.1_run1.json` and `_run2.json`; it changed no layout that
a path uses): of the 96 path measurements in the three runs, 95 were identical, and one
run counted one extra table scroll for C1-Q4 in the tabbed view, a timing artifact of the
replay rather than a change in the app.

## What changed in version 1.1

Version 1.1 follows a review of the screens against the AWARE trial's design and the
virtual-nursing fatigue study (both from Dr. Saif Khairat's group) and against the nurse
survey that motivates the project:

- **The tabbed view** gained a Summary tab, which it opens on: latest vital signs,
  infusions running at handoff and 12-hour intake and output, as the summary screen of a
  current EHR shows them. It also gained a patient banner (code status, allergies,
  isolation) and separate Problems and Lines & drains tabs, and the Meds tab became the
  MAR with a Home meds section. The Summary tab answers two current-value lookups with no
  click, so the control is faster than in version 0.3. This keeps the comparison fair.
- **NurseGlance** gained a patient header with the reason for admission and safety chips
  (code status, allergies, isolation, VTE prophylaxis), and its medication strip became a
  task strip: infusions running now with their titration, care done in the last 12 hours,
  and doses and turns due in the next 12 hours. The eight panels sit in four columns.
- **The study screen** gained two practice questions before each view and a break between
  the views, as in the protocol. Neither is timed.

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
- The no-scroll result for NurseGlance depends on the screen and the questions. In
  version 1.1 all eight panels fit on a 1920×1080 screen for all four cases, but on
  1440×900 the last rows of the complex cases' lower panels fell below the edge (none of
  the 16 answers was there). In version 1.2 every card of every case ends above the
  bottom of a 1440×900 screen in study mode (on the Handoff page, whose patient picker and
  title add height, the complex cases' lowest rows fall below it). On a 1366×768 screen (version 1.2.1,
  `docs/sensitivity/task_replay_1366x768_v1.2.1.json`), NurseGlance needed one scroll in
  its 16 paths, for C2-Q3 (the cefepime dose at the foot of the Tasks & meds column):
  3.4 s per question against 14.8 s for the tabbed view, which needed 2.9 scrolls per
  question there.
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
