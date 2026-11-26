"""Shared settings for the NurseGlance ETL.

Every MIMIC item ID below was checked against d_items / d_labitems in the
MIMIC-IV Clinical Database Demo v2.2. Edit the lists here, not inside the scripts.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Default data locations. download_data.sh puts the files here; override with
# --fhir-dir / --csv-dir if yours live somewhere else.
DEFAULT_FHIR_DIR = REPO_ROOT / "data/raw/physionet.org/files/mimic-iv-fhir-demo/2.1.0/fhir"
DEFAULT_CSV_DIR = REPO_ROOT / "data/raw/physionet.org/files/mimic-iv-demo/2.2"

CASES_FILE = REPO_ROOT / "etl/cases.json"
PROCESSED_DIR = REPO_ROOT / "data/processed"
DATA_ELEMENTS_FILE = REPO_ROOT / "docs/data_elements.csv"

# Time windows (hours) around the handoff time.
LOOKBACK_HOURS = 24      # vitals, assessments, I&O, infusions before handoff
TREND_HOURS = 12         # window used for trends and "last 12 h" summaries
LAB_LOOKBACK_HOURS = 72  # labs are drawn less often, so look further back
LOOKAHEAD_HOURS = 12     # medications given in the next shift (task timeline)

# Nursing shift changes used as candidate handoff times (24-hour clock).
SHIFT_CHANGE_HOURS = (7, 19)

# ---- MIMIC item IDs -------------------------------------------------------

HEART_RATE = 220045

# Invasive mechanical ventilation (procedureevents)
INVASIVE_VENT = 225792
NONINVASIVE_VENT = 225794

# Vasopressors (inputevents). Used to mark a case as "complex".
VASOPRESSORS = {
    221906: "Norepinephrine",
    221289: "Epinephrine",
    222315: "Vasopressin",
    221749: "Phenylephrine",
    229630: "Phenylephrine (50/250)",
    229632: "Phenylephrine (200/250)",
    221662: "Dopamine",
}
# Inotropes shown with vasoactive drips but not used for case selection.
INOTROPES = {221653: "Dobutamine", 221986: "Milrinone"}

SEDATION_ANALGESIA = {
    222168: "Propofol",
    225150: "Dexmedetomidine (Precedex)",
    229420: "Dexmedetomidine (Precedex)",
    221744: "Fentanyl",
    225942: "Fentanyl (Concentrate)",
    221668: "Midazolam (Versed)",
}

# Blood pressure pairs used to calculate MAP when no mean was charted.
BP_SOURCES = {
    "arterial": {"sys": 220050, "dia": 220051, "mean": 220052},
    "noninvasive": {"sys": 220179, "dia": 220180, "mean": 220181},
}

GCS_COMPONENTS = {"eye": 220739, "verbal": 223900, "motor": 223901}

# MIMIC stores the RASS goal as a positive number (goal -3 has valuenum 3).
# The ETL restores the minus sign for these items.
NEGATE_ITEMS = {228299}

# Weight for mL/kg/h calculations: daily weight first, then admission weight.
WEIGHT_ITEMS = (224639, 226512)

# Urine output items (outputevents). GU irrigant volume in is subtracted.
URINE_ITEMS = {226559, 226560, 226561, 226584, 226563, 226564, 226565,
               226567, 226557, 226558, 227489}
GU_IRRIGANT_IN = 227488
# Output items that are not volumes (skipped in totals).
NON_VOLUME_OUTPUT_ITEMS = {227487}

# Carrier fluids charted in the same order as a drug (e.g. vancomycin in D5W).
# Left out of category matches such as "cat:Antibiotics" but still counted as intake.
CARRIER_FLUIDS = {220949: "Dextrose 5%", 225158: "NaCl 0.9%"}

# Lines, airways and devices (procedureevents) shown with day counts.
DEVICE_ITEMS = {
    225792: "Invasive ventilation",
    225794: "Non-invasive ventilation",
    225752: "Arterial line",
    224263: "Multi-lumen central line",
    224264: "PICC line",
    224560: "PA catheter",
    224270: "Dialysis catheter",
    224267: "Cordis/introducer",
    224268: "Trauma line",
    225204: "Midline",
    224274: "PIV 22 gauge",
    224275: "PIV 20 gauge",
    224276: "PIV 16 gauge",
    224277: "PIV 18 gauge",
    229351: "Foley catheter",
    225802: "CRRT",
    225441: "Hemodialysis",
}
