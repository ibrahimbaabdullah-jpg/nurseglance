# NurseGlance

> **Research prototype — not for clinical use; not clinically validated.**

A nurse-centered ICU handoff dashboard built on HL7 FHIR data from the open
MIMIC-IV Clinical Database Demo on FHIR. It shows the same four ICU patients in two
ways: a conventional tabbed EHR-style view (the control) and the NurseGlance view,
one screen organized by organ system with sparklines, abnormal highlighting and a
12-hour medication and infusion timeline.

## What's here

| File | What it does |
| --- | --- |
| `etl/select_cases.py` | Ranks ICU stays in the MIMIC-IV demo (CSV) and suggests 2 standard and 2 complex handoff cases |
| `etl/build_cases.py` | Reads the FHIR demo and writes `data/processed/case_<id>.json` for each case |
| `etl/coverage.py` | Reports how many handoff data elements FHIR can fill (research question 1) |
| `etl/config.py` | Item IDs, time windows and file paths, all in one place |
| `etl/value_codes.py` | Rebuilds `docs/value_codes.csv`, which restores text that FHIR carries only as a numeric code |
| `streamlit_app.py`, `app/` | The dashboard: `glance.py` (NurseGlance view), `tabbed.py` (control view), `timeline.py` (12 h timeline), `data.py` (shared loading) |
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
eligible stays). Rerun it after your download to confirm you get the same list.

| Case | Stay | Handoff | Unit | Why |
| --- | --- | --- | --- | --- |
| S1 | 33846653 | 2137-06-22 07:00, ICU day 4 | MICU/SICU | 29 F, insulin pump complication; no ventilation or pressors |
| S2 | 37509585 | 2169-01-16 07:00, ICU day 2 | Neuro SICU | 63 F, subarachnoid hemorrhage; no ventilation or pressors |
| C1 | 32359580 | 2146-06-23 19:00, ICU day 2 | MICU | 69 M, cirrhosis; ventilated, norepinephrine and vasopressin, CRRT |
| C2 | 37093652 | 2177-03-26 19:00, ICU day 3 | MICU/SICU | 88 M, melena; ventilated, norepinephrine weaning, new central and arterial lines |

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
- **eMAR coverage.** The demo has eMAR records for only some admissions. S1 has
  none, so its 12-hour medication timeline is empty.
- **Code status** is rarely charted in the demo. When a hospital diagnosis code for
  DNR status (Z66 or V49.86) exists, the NurseGlance view shows "DNR (dx code)" and
  says where it came from; the tabbed view shows the same code in the problem list.
- **Control view tabs** are a radio control, not `st.tabs`, so each tab change is a
  real interaction that study mode (Day 3) can log as a click and a screen visit.
- **Thresholds** marked "placeholder" in `docs/data_elements.csv` are yours to set
  and cite. Labs with no threshold use each result's own reference range.

## How it was tested

- 32 tests (`pytest`): unit and synthetic ETL tests (windows, calculated MAP, GCS,
  urine output per kg, drip titration, line days, lab flags), the FHIR-vs-CSV check,
  the restored text codes, and the app's data helpers, timeline and panels for every case.
- The full pipeline ran on the official FHIR demo v2.1.0 and CSV demo v2.2 from
  PhysioNet (checksums verified). The FHIR-vs-CSV test passes for all 4 cases.
- Both views were clicked through for all 4 cases in a headless browser with no errors.

## Data

MIMIC data is de-identified and shared under the ODbL v1.0. See
`DATA_LICENSE.md` for attribution and the share-alike terms. Raw downloads stay
out of git; the small processed case files are committed so the app can deploy.
