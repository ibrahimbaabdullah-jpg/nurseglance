# NurseGlance

> **Research prototype — not for clinical use; not clinically validated.**

**Live demo:** https://ibrahimbaabdullah-jpg-nurseglance-streamlit-app-uvwgbm.streamlit.app/

A nurse-centered ICU handoff dashboard built on HL7 FHIR data from the open
MIMIC-IV Clinical Database Demo on FHIR. It shows the same four ICU patients in two
ways: a conventional tabbed EHR-style view (the control) and the NurseGlance view,
one screen organized by organ system with sparklines, abnormal highlighting and a
12-hour medication and infusion timeline.

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
  study needs IRB approval and would run in a research lab.
- **Click and time results are design-level estimates** from scripted runs, not user
  outcomes. Any feedback from nurse colleagues is informal formative feedback, not
  study data, and no identifiable data is recorded.
- **No PHI.** Only the de-identified MIMIC-IV demo is used; nothing comes from any
  workplace EHR.

## What's here

| File | What it does |
| --- | --- |
| `etl/select_cases.py` | Ranks ICU stays in the MIMIC-IV demo (CSV) and suggests 2 standard and 2 complex handoff cases |
| `etl/build_cases.py` | Reads the FHIR demo and writes `data/processed/case_<id>.json` for each case |
| `etl/coverage.py` | Reports how many handoff data elements FHIR can fill (research question 1) |
| `etl/config.py` | Item IDs, time windows and file paths, all in one place |
| `etl/value_codes.py` | Rebuilds `docs/value_codes.csv`, which restores text that FHIR carries only as a numeric code |
| `etl/loinc_mapping.py` | Writes `docs/loinc_mapping.csv`: 50 MIMIC items mapped to LOINC, each name checked at NLM (`--verify`) |
| `docs/coverage.md` | Research question 1 write-up: coverage by organ system, FHIR vs CSV completeness, gaps and causes |
| `streamlit_app.py`, `app/` | The dashboard: `glance.py` (NurseGlance view), `tabbed.py` (control view), `timeline.py` (12 h timeline), `data.py` (shared loading) |
| `app/study.py`, `app/events.py`, `app/scoring.py` | Study mode: seeded randomization, event log, SUS and raw NASA-TLX scoring, CSV export |
| `app/flags.py` | 8 transparent rule-based flags, each showing its rule, values, times and FHIR IDs (off in study mode) |
| `app/vn.py` | Virtual-nurse mode: admission and discharge checklists, session timer, 10-minute break prompt |
| `docs/case_questions.json` | The 16 handoff questions (4 per case) with answer keys and the synthesis rubric |
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
  12 h after handoff for the medication timeline. Change them in `etl/config.py`.
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
  case has a 12-hour medication timeline.
- **Code status** is rarely charted in the demo. When a hospital diagnosis code for
  DNR status (Z66 or V49.86) exists, the NurseGlance view shows "DNR (dx code)" and
  says where it came from; the tabbed view shows the same code in the problem list.
- **Control view tabs** are a radio control, not `st.tabs`, so each tab change is a
  real interaction that study mode (Day 3) can log as a click and a screen visit.
- **Standard codes.** MIMIC-IV on FHIR codes chart and lab items in MIMIC's own code
  systems. `docs/loinc_mapping.csv` maps each item NurseGlance shows to LOINC; hovering
  a value shows its LOINC code and name. Five codes from MIMIC-IV v1.0 were replaced
  (two deprecated, one unit mismatch, one manual-count code, blood gases had none).
- **Fall risk and restraints.** The starter item IDs had no rows in the demo. Fall
  risk is now the sum of the six Morse Fall Scale items; restraints use items 227945
  and 227948.
- **Thresholds** marked "placeholder" in `docs/data_elements.csv` are yours to set
  and cite. Labs with no threshold use each result's own reference range.

## Modes

- **Explore:** pick a patient and a view; switch on the rule-based flags if you like.
- **Study session:** anonymous run ID, then the first view with 2 cases (4 questions
  each), SUS and NASA-TLX, the second view with the other 2 cases, SUS and NASA-TLX,
  and a CSV download. View order, which standard and complex case go with which
  view, and case order within each view are randomized with a logged seed. Each
  participant sees each case once. Streamlit cannot see raw mouse clicks or
  scrolling, so "interactions" are logged interface actions (tab switches, toggles,
  selects). Files saved on Streamlit Community Cloud do not survive a restart, so
  download the CSVs at the end; a real study would run locally or log to a database.
- **Virtual-nurse mode:** an admission or discharge checklist built from the same
  case data, with a session timer, a completeness counter and an optional break
  prompt after 10 minutes.

Event log columns: `run_id, seed, ts_utc, view, case_id, question_id, event, target, value`.
Events: `session_start, question_shown, tab_switch, toggle, answer_submit, survey_submit, session_end`.

## How it was tested

- 56 tests (`pytest`), including SUS and NASA-TLX scoring against hand-calculated
  examples, randomization balance over 200 seeds, the answer keys checked against the
  case files, and the flags' evidence. Also: unit and synthetic ETL tests (windows, calculated MAP, GCS,
  urine output per kg, drip titration, line days, lab flags), the FHIR-vs-CSV check,
  the restored text codes, and the app's data helpers, timeline and panels for every case.
- The full pipeline ran on the official FHIR demo v2.1.0 and CSV demo v2.2 from
  PhysioNet (checksums verified). The FHIR-vs-CSV test passes for all 4 cases.
- Both views were clicked through for all 4 cases in a headless browser with no errors,
  and a full mock study session (16 questions, 2 surveys) exported a clean CSV.

## Data

MIMIC data is de-identified and shared under the ODbL v1.0. See
`DATA_LICENSE.md` for attribution and the share-alike terms. Raw downloads stay
out of git; the small processed case files are committed so the app can deploy.
