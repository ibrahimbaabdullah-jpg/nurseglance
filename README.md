# NurseGlance

> **Research prototype — not for clinical use; not clinically validated.**

**Live demo:** https://ibrahimbaabdullah-jpg-nurseglance-streamlit-app-uvwgbm.streamlit.app/

**Demo video (3 min, captioned):** [docs/video/nurseglance_demo.mp4](docs/video/nurseglance_demo.mp4) ·
**Technical report:** [PDF](docs/pdf/technical_report.pdf) · **One-page brief:** [PDF](docs/pdf/brief.pdf)

A nurse-centered ICU handoff dashboard built on HL7 FHIR data from the open
MIMIC-IV Clinical Database Demo on FHIR. It shows the same four ICU patients in two
ways: a conventional tabbed EHR-style view (the control) and the NurseGlance view,
one laptop screen with a patient card (reason for admission, code status, allergies,
safety chips, other infusions), seven organ-system cards with sparklines and
abnormal highlighting, and a Tasks & meds column (care done in the last 12 hours,
doses and turns due next).

## Why this project: alignment with Dr. Saif Khairat's work

| NurseGlance element | Work it builds on |
| --- | --- |
| Tabbed "control" view vs. NurseGlance "intervention" view; 2 standard + 2 complex ICU cases | AWARE crossover RCT of an ICU visualization dashboard vs. the EHR (Khairat et al., JMIR Res Protoc 2025; NCT05937646; NIH NLM R01LM013606) |
| Study mode: logged interface actions, time per question, answer accuracy, SUS and NASA-TLX | The AWARE protocol's primary and secondary outcomes |
| Nurse-specific data elements, organ-system layout, task timeline | ICU nurses' stated visualization needs (Lindroth et al., Appl Clin Inform 2022) and Khairat's nurse EHR usability and well-being work (JMIR Nursing 2020) |
| Virtual-nurse mode with a 10-minute break prompt and a completeness counter | Virtual-nurse cognitive fatigue at 9.8-11.9 minutes (Khairat et al., JMIR Hum Factors 2025) and task completeness (SAGE Open Nursing 2025); NINR R01NR021711 on nurse job demands |
| Logs and surveys collected together | Actual vs. perceived EHR measures diverge (Khairat et al., Perspect Health Inf Manag 2022) |

AWARE's participants are physicians and advanced practice providers. NurseGlance asks
whether the same approach helps bedside and virtual nurses.

## Research ethics and what the results are

- **No human-subjects data.** No nurse has used this app as a study participant.
  Study mode shows that a session can run end to end and export clean data; a real
  study needs IRB approval and would run in a research lab. The proposed protocol is
  `docs/protocol.md`.
- **Click and time results are design-level estimates** from scripted runs, not user
  outcomes. Any feedback from nurse colleagues is informal formative feedback, not
  study data, and no identifiable data is recorded.
- **No PHI.** Only the de-identified MIMIC-IV demo is used; nothing comes from any
  workplace EHR.

## What's here

| File | What it does |
| --- | --- |
| `etl/select_cases.py` | Ranks ICU stays in the MIMIC-IV demo (CSV) and suggests 2 standard and 2 complex handoff cases |
| `etl/build_cases.py` | Reads the FHIR demo and writes `data/processed/case_<id>.json` for each case (and the practice stay, from `etl/practice_case.json`, into `data/processed/practice/`) |
| `etl/coverage.py` | Reports how many handoff data elements FHIR can fill (research question 1) |
| `etl/config.py` | Item IDs, time windows and file paths, all in one place |
| `etl/value_codes.py` | Rebuilds `docs/value_codes.csv`, which restores text that FHIR carries only as a numeric code |
| `etl/loinc_mapping.py` | Writes `docs/loinc_mapping.csv`: 50 MIMIC items mapped to LOINC, each name checked at NLM (`--verify`) |
| `docs/coverage.md` | Research question 1 write-up: coverage by organ system, FHIR vs CSV completeness, gaps and causes |
| `analysis/` | Task analysis: the shortest path to every study answer in each view (`paths.py`), a Playwright replay that measures it in the running app (`replay.py`), and keystroke-level estimates (`task_analysis.py`) |
| `docs/task_analysis.md` | Clicks, scrolls, screens and estimated seconds per question, for versions 0.2, 0.3 and 1.1 |
| `docs/heuristic_evaluation.md` | Draft heuristic evaluation of both views (Nielsen's 10, severity 0 to 4), with what versions 0.3 and 1.1 changed |
| `docs/brief.md` ([PDF](docs/pdf/brief.pdf)) | One-page summary of the project, its results and the proposed study |
| `docs/technical_report.md` ([PDF](docs/pdf/technical_report.pdf)) | Six-page technical report: background, methods, results for the three research questions, limitations, equity and responsible use |
| `docs/protocol.md` ([PDF](docs/pdf/protocol.pdf)) | Proposed crossover usability study with ICU and virtual nurses, modeled on the AWARE trial; not started, needs IRB approval |
| `analysis/sample_size.py`, `analysis/allocation.py` | The protocol's sample size (34 nurses for d<sub>z</sub> = 0.5, recruit 40) and its balanced allocation list |
| `tools/build_pdf.py` | Renders a Markdown file in `docs/` to PDF (pandoc and Chromium) |
| `tools/record_demo.py`, `docs/video/` | Records the captioned demo video from the running app, with subtitles (`.srt`) and a narration script |
| `streamlit_app.py`, `app/` | The dashboard: `ui.py` (shared look: top bar, colors, fonts), `glance.py` (NurseGlance view), `tabbed.py` (control view), `timeline.py` (dose and infusion rows), `data.py` (shared loading) |
| `static/fonts/`, `docs/design/` | Inter and Space Grotesk (SIL Open Font License, served by the app so no font service is called) and screenshots of the design mockup that version 1.2 follows |
| `app/study.py`, `app/events.py`, `app/scoring.py` | Study mode: seeded randomization, practice questions, break, pause, event log, SUS and raw NASA-TLX scoring, debrief notes, CSV export |
| `app/research.py` | Researcher page: the allocation list from a private master seed, a check of uploaded session files, and the planned analysis |
| `app/flags.py` | 8 transparent rule-based flags, each showing its rule, values, times and FHIR IDs (off in study mode) |
| `app/vn.py` | Virtual-nurse mode: admission and discharge checklists, session timer, 10-minute break prompt |
| `docs/case_questions.json` | The 16 handoff questions (4 per case) with answer keys and the synthesis rubric |
| `docs/practice_questions.json` | 4 practice questions on a fifth stay (2 before each view), logged but never scored |
| `docs/data_elements.csv` | Starter list of 58 handoff data elements by organ system, for you to edit |
| `tests/` | Unit tests, a synthetic end-to-end test, and a FHIR-vs-CSV check |
| `download_data.sh` | Downloads both datasets from PhysioNet and checks their checksums |

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

./download_data.sh                   # about 65 MB into data/raw/

python etl/select_cases.py           # suggests cases -> etl/cases.json, docs/cases_draft.md
# Review the suggestions, edit etl/cases.json if you swap a case, then:
python etl/build_cases.py            # -> data/processed/case_S1.json ... case_C2.json
pytest                               # all tests, including FHIR vs CSV
python etl/coverage.py               # -> docs/coverage.csv
python etl/loinc_mapping.py --verify # -> docs/loinc_mapping.csv
streamlit run streamlit_app.py       # opens the dashboard at http://localhost:8501
```

The processed case files are committed, so the app runs (and deploys to
Streamlit Community Cloud) without downloading anything.

If your data lives elsewhere, pass `--csv-dir` and `--fhir-dir`. The FHIR
reader accepts PhysioNet's names (`MimicPatient.ndjson.gz`) and unzipped or
unprefixed copies.

## Suggested cases (already generated)

`select_cases.py` was run on the MIMIC-IV demo v2.2 downloaded from PhysioNet, and
`build_cases.py` on the FHIR demo v2.1.0. The results are in
`etl/cases.json`, `docs/cases_draft.md` and `docs/case_candidates.csv` (all 41
eligible stays). S1 was then swapped by hand for the rank-8 standard candidate,
because the first-ranked stay has no eMAR records. Rerunning `select_cases.py`
resets `etl/cases.json` to the automatic picks.

| Case | Stay | Handoff | Unit | Why |
| --- | --- | --- | --- | --- |
| S1 | 36496303 | 2144-10-31 19:00, ICU day 3 | CVICU | 40 F, left iliac vein thrombosis; no ventilation or pressors |
| S2 | 37509585 | 2169-01-16 07:00, ICU day 2 | Neuro SICU | 63 F, subarachnoid hemorrhage; no ventilation or pressors |
| C1 | 32359580 | 2146-06-23 19:00, ICU day 2 | MICU | 69 M, cirrhosis; ventilated, norepinephrine and vasopressin, CRRT |
| C2 | 37093652 | 2177-03-26 19:00, ICU day 3 | MICU/SICU | 87 M, melena; ventilated, norepinephrine weaning, new central and arterial lines |

These are rankings, not clinical judgments. Both complex patients died later in
the admission; if you'd rather use a survivor, the next complex candidate
(stay 34100191, E. coli sepsis, CCU) is a ready swap. Edit `etl/cases.json`.

## What one case file contains

- `patient`, `stay`: age, sex, unit, ICU day, handoff time
- `elements`: one summary per row of `docs/data_elements.csv`, with the latest
  value, 12-hour trend, abnormal flag, and the FHIR resource ID it came from.
  Drips show the current rate, time of last change and the rate 12 hours ago.
  Lines and devices show their day count.
- `observations`: every charted value, lab and output in the window
- `infusions`, `med_administrations`, `med_orders_active`, `devices`, `diagnoses`

## Design decisions worth knowing

- **Times.** FHIR timestamps carry UTC offsets. They are converted back to
  Boston wall-clock time, which matches the CSV tables exactly.
- **Windows.** 24 h before handoff for vitals, I&O and drips; 72 h for labs;
  12 h after handoff for doses due. Change them in `etl/config.py`.
- **Code systems.** The FHIR demo changed its URL base between releases. The
  scripts match identifiers by suffix and item IDs by code, so both work.
- **RASS goal.** MIMIC stores the goal without its minus sign (goal -3 is stored
  as 3). The ETL restores the sign.
- **GCS.** An intubated patient's verbal score is charted as 1, the same as
  "No Response". When ventilation is in place the GCS note says to report it with a T.
- **Due medications.** eMAR doses given in the 12 h after handoff stand in for
  what was due, because the data has no separate schedule.
- **Intake and output** totals are approximate (ICU input events in mL, prorated by time).
- **Organ systems.** The starter list adds a Heme/ID group (temperature, WBC,
  hemoglobin, platelets, INR, antibiotics). Fold it into another panel if you want seven.
- **Coded text.** FHIR demo v2.1.0 carries some charted text items only as
  MIMIC's numeric code (ventilator mode "CMV/ASSIST/AutoFlow" arrives as 49; pain
  level, CAM-ICU likewise). `etl/value_codes.py` rebuilds the code-to-text table
  from the CSV demo into `docs/value_codes.csv` (40 pairs, 10 items), and
  `build_cases.py` restores the text. This is a FHIR data-quality finding worth
  reporting under research question 1.
- **eMAR coverage.** The demo has eMAR records for only some admissions (6 of the
  top 10 standard candidates have none). Cases were checked for eMAR data so every
  case has doses given and due.
- **Code status** is rarely charted in the demo. When a hospital diagnosis code for
  DNR status (Z66 or V49.86) exists, both views show DNR and say it came from a
  diagnosis code.
- **Reason for admission.** When the patient came through the emergency department,
  the ED chief complaint (FHIR Observation, LOINC 8661-1) is shown as the reason for
  admission, and the ED's medication reconciliation as the home medication list.
  Otherwise the first 3 disease diagnoses are shown, and the screen says that FHIR
  carries no diagnosis priority.
- **Same safety facts in both views.** Code status, allergies and isolation sit in
  the control's patient banner and in NurseGlance's header chips, so the comparison
  is about layout, not about which view has more data.
- **Control view tabs** are a radio control, not `st.tabs`, so each tab change is a
  real interaction that study mode can log as a click and a screen visit.
- **Standard codes.** MIMIC-IV on FHIR codes chart and lab items in MIMIC's own code
  systems. `docs/loinc_mapping.csv` maps each item NurseGlance shows to LOINC; hovering
  a value shows its LOINC code and name. Five codes from MIMIC-IV v1.0 were replaced
  (two deprecated, one unit mismatch, one manual-count code, blood gases had none).
- **Fall risk and restraints.** The starter item IDs had no rows in the demo. Fall
  risk is now the sum of the six Morse Fall Scale items; restraints use items 227945
  and 227948.
- **Version 0.3 redesign.** After a heuristic evaluation, NurseGlance got short labels,
  12-hour ranges under trended values, H/L badges, folded empty rows and a medication
  strip (running infusions and next doses) at the top. The tabbed control was made
  closer to a current EHR (newest columns first, scores beside their parts, running
  infusions and upcoming doses first) so the comparison is fair, and the study question
  moved to the sidebar. See `docs/heuristic_evaluation.md`.
- **Version 1.1 screen review.** The screens were reviewed against the AWARE trial,
  the virtual-nursing fatigue study and the ICU nurse survey. The control gained a
  Summary tab (which it opens on), a patient banner, Problems and Lines & drains tabs
  and a MAR with home medications. NurseGlance gained the patient header with safety
  chips and the three-row task strip. Study mode gained practice questions, a break, a
  pause that stops the clock and debrief notes; virtual-nurse mode gained a review
  note for the bedside nurse; a Researcher page was added. The turn interval in the
  task strip (every 2 hours) is a placeholder rule.
- **Version 1.2 look.** The screens follow a design mockup (`docs/design/`): a white
  top bar with the view switch (Glance or Tabbed EHR), the mode switch (Handoff or
  Virtual nurse) and a "Start study mode" button; white cards on a light grey page;
  Inter and Space Grotesk. NurseGlance keeps one patient on one 1440×900 screen: a
  patient card with safety chips and the infusions no card lists, seven organ-system
  cards (vasoactive and sedation drips sit in their cards with any 12 h titration),
  and a Tasks & meds column that replaces the task strip and the 12 h timeline below
  the fold. Flags are cards that name their rule and source. The tabbed control uses
  the same patient card and an EHR tab strip. Virtual-nurse mode has a session band
  under the top bar (break reminder snoozes 5 minutes). Content rules kept: no
  "stable" or "improving" labels, allergies shown as not in the FHIR demo, only data
  that exists, and no buttons that do nothing.
- **Thresholds** marked "placeholder" in `docs/data_elements.csv` are yours to set
  and cite. Labs with no threshold use each result's own reference range.

## Modes

The top bar holds the view switch (Glance view or Tabbed EHR view), the mode switch
(Handoff or Virtual nurse) and "Start study mode". The Researcher page is linked at
the foot of each page.

- **Handoff:** pick a patient and a view; switch on the rule-based flags if you like.
- **Study session:** anonymous run ID and seed, then 2 practice questions and the
  first view with 2 cases (4 questions each), SUS and NASA-TLX, a 2-minute break, 2
  practice questions and the second view with the other 2 cases, SUS and NASA-TLX,
  debrief notes and a CSV download. View order, which standard and complex case go
  with which view, and case order within each view are randomized with a logged seed.
  Each participant sees each case once. The question sits in the sidebar with a
  progress bar; Pause hides the view and stops the clock. While a session runs, the
  other pages are hidden. Streamlit cannot see raw mouse clicks or scrolling, so
  "interactions" are logged interface actions (tab switches, toggles, selects). Files
  saved on Streamlit Community Cloud do not survive a restart, so download the CSVs
  at the end; a real study would run locally or log to a database.
- **Virtual nurse:** an admission or discharge review built from the same case data:
  what is already in the chart, a grouped checklist that marks which items the chart
  already shows, a session timer, a break prompt after 10 minutes (take a break or
  remind again in 5 minutes), and a review note to hand to the bedside nurse.
- **Researcher:** the allocation list built from a private master seed, a check of
  uploaded session files (complete, answered, surveys, pauses) with medians by view,
  and the planned analysis.

Event log columns: `run_id, seed, ts_utc, view, case_id, question_id, event, target, value`.
Events: `session_start, practice_shown, practice_submit, question_shown, tab_switch,
toggle, answer_submit, survey_submit, break_start, break_end, pause, resume,
debrief_note, session_abandoned, session_end`.

## How it was tested

- 85 tests (`pytest`), including SUS and NASA-TLX scoring against hand-calculated
  examples, randomization balance over 200 seeds, the answer keys checked against the
  case files, the flags' evidence, and the protocol's sample size and allocation balance. Also: unit and synthetic ETL tests (windows, calculated MAP, GCS,
  urine output per kg, drip titration, line days, lab flags), the FHIR-vs-CSV check,
  the restored text codes, and the app's data helpers, timeline and panels for every case.
- The full pipeline ran on the official FHIR demo v2.1.0 and CSV demo v2.2 from
  PhysioNet (checksums verified). The FHIR-vs-CSV test passes for all 4 cases.
- Every page, case, view, tab, MAR section and Flowsheet section was clicked through in
  a headless browser at 1440×900 (161 screens, version 1.2) with no errors and no
  sideways page scroll, and the study session's pause, resume and abandon were checked.
- Two full scripted study sessions (16 questions, 4 practice questions, 2 surveys and a
  break each) exported clean CSVs; one is the Researcher page's example run
  (`docs/mock_session_events.csv`).
- `analysis/replay.py` answers all 16 questions in both views through the study mode,
  checks each answer is on screen, and confirms the app's event log counts the same
  clicks and screens (`pip install -r requirements-analysis.txt`, then
  `playwright install chromium`, with the app running).

## Data

MIMIC data is de-identified and shared under the ODbL v1.0. See
`DATA_LICENSE.md` for attribution and the share-alike terms. Raw downloads stay
out of git; the small processed case files are committed so the app can deploy.

## Versions and citing

| Version | Commit | What it holds |
| --- | --- | --- |
| v0.1 | `63fdd56` | Both views, 4 cases, README (the minimum viable prototype) |
| v0.2 | `f582b5a` | Study mode, rule-based flags, virtual-nurse mode |
| v0.3 | `fd2791a` | Heuristic evaluation and redesign of both views, task analysis |
| v1.0 | `501957c` | Evaluation protocol, technical report, brief and demo video |
| v1.1 | `378bab0` | Screen review: Summary tab and patient banner in the control, header chips and task strip in NurseGlance, practice questions, break and pause in study mode, Researcher page |
| v1.2 | latest `main` | The design mockup's look: top bar, patient card, organ-system cards, Tasks & meds column, flag cards, virtual-nurse session band; self-hosted fonts |

To cite NurseGlance, use `CITATION.cff` (GitHub's "Cite this repository" button reads
it). A Zenodo DOI will be added here once a release is archived. Code is MIT-licensed; the
MIMIC-derived data files are ODbL (see `DATA_LICENSE.md`).
