#!/usr/bin/env python3
"""Write docs/loinc_mapping.csv: MIMIC local codes -> LOINC for the vitals and labs NurseGlance shows.

    python etl/loinc_mapping.py              # build the table from the map below
    python etl/loinc_mapping.py --verify     # also look up each code's LOINC name at NLM

MIMIC-IV on FHIR codes chart and lab items with MIMIC's own code systems
(d_items, d_labitems), so the dashboard's values are not interoperable as they
stand. This table is the documented local-to-standard bridge.

Where the codes come from (column "code_source"):
  mimic_v1_d_labitems  the loinc_code column of d_labitems in the MIMIC-IV demo v1.0
                       (v2.x dropped that column). Kept when correct, replaced when
                       the code is deprecated or does not fit the unit or method.
  mimic_fhir_ed        the LOINC codes MIMIC-IV-ED on FHIR uses for ED vital signs.
  author               chosen by the author by property, system and method.

--verify asks NLM Clinical Tables (clinicaltables.nlm.nih.gov, LOINC) for each
code's long common name and records the date. Check anything marked "review".
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from etl import config  # noqa: E402

OUT = config.REPO_ROOT / "docs/loinc_mapping.csv"

# element_id, MIMIC item ID, LOINC code (blank = none found), code source, note
MAP = [
    ("heart_rate", "220045", "8867-4", "mimic_fhir_ed", ""),
    ("heart_rhythm", "220048", "8884-9", "author", ""),
    ("map", "220052", "76214-6", "author", "Arterial line mean"),
    ("map", "220181", "76536-2", "author", "Non-invasive (cuff) mean"),
    ("map", "MAP_CALC", "8478-0", "author", "Calculated (SBP + 2 x DBP) / 3 by NurseGlance; method-less code"),
    ("sbp", "220050", "76215-3", "author", "Arterial line systolic"),
    ("sbp", "220179", "8480-6", "mimic_fhir_ed", "Non-invasive systolic"),
    ("map", "220180", "8462-4", "mimic_fhir_ed", "Non-invasive diastolic (used for calculated MAP)"),
    ("map", "220051", "76213-8", "author", "Arterial line diastolic (used for calculated MAP)"),
    ("cvp", "220074", "60985-9", "author", ""),
    ("resp_rate", "220210", "9279-1", "mimic_fhir_ed", ""),
    ("spo2", "220277", "59408-5", "author",
     "MIMIC-IV-ED on FHIR uses 2708-6 (arterial blood, method-less); 59408-5 names pulse oximetry"),
    ("fio2", "223835", "3150-0", "author", "MIMIC charts FiO2 as a percentage"),
    ("peep", "220339", "20077-4", "author", "PEEP set on the ventilator"),
    ("vent_mode", "223849", "20124-4", "author", "Value is coded text; FHIR v2.1.0 carries only MIMIC's numeric code"),
    ("temperature", "223761", "8310-5", "mimic_fhir_ed", "Fahrenheit; NurseGlance converts to Celsius"),
    ("temperature", "223762", "8310-5", "mimic_fhir_ed", "Celsius"),
    ("temperature", "TEMP_C", "8310-5", "mimic_fhir_ed", "The value NurseGlance shows, always in Celsius"),
    ("gcs_total", "GCS_TOTAL", "9269-2", "author", "Sum of eye + verbal + motor charted at the same time"),
    ("gcs_total", "220739", "9267-6", "author", "Eye opening"),
    ("gcs_total", "223900", "9270-0", "author", "Verbal"),
    ("gcs_total", "223901", "9268-4", "author", "Motor"),
    ("rass", "228096", "", "author", "No LOINC term found (NLM searches 'richmond', 'RASS', 'agitation sedation')"),
    ("pain", "223791", "72514-3", "author",
     "review: MIMIC charts pain as categories (None ... Worst) coded 0-10, not a patient-reported number"),
    ("cam_icu", "228337", "52495-9", "author", "review: one code for the CAM as a whole; MIMIC charts its features separately"),
    ("braden_total", "BRADEN_TOTAL", "38227-5", "author", "Sum of the six Braden subscales charted at the same time"),
    ("fall_risk", "MORSE_TOTAL", "59460-6", "author", "Sum of the six Morse items charted at the same time"),
    ("weight", "226512", "29463-7", "author", "Admission weight"),
    ("weight", "224639", "29463-7", "author", "Daily weight"),
    ("glucose_poc", "225664", "41653-7", "author", "Fingerstick (glucometer)"),
    ("glucose_poc", "226537", "2339-0", "author", "Whole blood"),
    ("glucose_poc", "220621", "2345-7", "author", "Serum glucose charted in chartevents"),
    ("urine_output_6h", "UO_6H", "9187-6", "author", "6-hour total; LOINC has 1, 8, 10, 12 and 24 h urine output but no 6 h term"),
    ("intake_12h", "INTAKE_12H", "9107-4", "author", "Approximate: MIMIC input events prorated by time"),
    ("output_12h", "OUTPUT_12H", "9261-9", "author", ""),
    ("net_12h", "NET_12H", "9096-9", "author", ""),
    ("lactate", "50813", "32693-4", "author", "Blood gas lactate (whole blood); MIMIC v1.0 gave no code"),
    ("lactate", "52442", "32693-4", "author", "MIMIC v1.0 gave no code"),
    ("ph", "50820", "11558-4", "author", "Blood gas pH; specimen may be arterial or venous, so the specimen-neutral code"),
    ("pco2", "50818", "11557-6", "author", "Specimen-neutral, as for pH"),
    ("po2", "50821", "11556-8", "author", "Specimen-neutral, as for pH"),
    ("creatinine", "50912", "2160-0", "mimic_v1_d_labitems", ""),
    ("bun", "51006", "3094-0", "mimic_v1_d_labitems", ""),
    ("potassium", "50971", "2823-3", "mimic_v1_d_labitems", ""),
    ("sodium", "50983", "2951-2", "mimic_v1_d_labitems", ""),
    ("magnesium", "50960", "19123-9", "author",
     "MIMIC v1.0 gives 2601-3 (moles/volume), but MIMIC reports mg/dL, a mass/volume unit"),
    ("glucose_lab", "50931", "2345-7", "author", "MIMIC v1.0 gives 6777-7, which LOINC has deprecated"),
    ("wbc", "51301", "6690-2", "author",
     "MIMIC v1.0 gives 804-5 (manual count); a CBC white count is usually automated. review"),
    ("hemoglobin", "51222", "718-7", "mimic_v1_d_labitems", ""),
    ("platelets", "51265", "777-3", "mimic_v1_d_labitems", ""),
    ("inr", "51237", "6301-6", "author", "MIMIC v1.0 gives 5895-7, which LOINC has deprecated"),
]


def mimic_labels(csv_dir: Path) -> dict[str, tuple[str, str]]:
    """item ID -> (label, unit) from d_items and d_labitems, when the CSV demo is present."""
    out: dict[str, tuple[str, str]] = {}
    for rel, unit_col in (("icu/d_items.csv.gz", "unitname"), ("hosp/d_labitems.csv.gz", None)):
        path = csv_dir / rel
        if not path.exists():
            continue
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                unit = (row.get(unit_col) or "") if unit_col else ""
                out[row["itemid"]] = (row["label"], "" if unit == "None" else unit)
    return out


def loinc_name(code: str) -> str | None:
    query = urllib.parse.urlencode({"terms": code, "df": "LOINC_NUM,LONG_COMMON_NAME", "maxList": 5})
    url = f"https://clinicaltables.nlm.nih.gov/api/loinc_items/v3/search?{query}"
    with urllib.request.urlopen(url, timeout=20) as resp:
        hits = json.load(resp)[3]
    return next((name for num, name in hits if num == code), None)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv-dir", type=Path, default=config.DEFAULT_CSV_DIR)
    parser.add_argument("--verify", action="store_true", help="look up each code's name at NLM Clinical Tables")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)

    old = {}
    if args.out.exists():
        with open(args.out, newline="", encoding="utf-8") as handle:
            old = {(r["element_id"], r["mimic_item_id"]): r for r in csv.DictReader(handle)}
    labels = mimic_labels(args.csv_dir)
    rows = []
    for element, item, code, source, note in MAP:
        prev = old.get((element, item), {})
        label, unit = labels.get(item, (prev.get("mimic_label") or "NurseGlance derived value", prev.get("mimic_unit", "")))
        name, verified = prev.get("loinc_long_name", ""), prev.get("verified", "")
        if args.verify and code:
            name = loinc_name(code) or "NOT FOUND"
            verified = f"NLM Clinical Tables {date.today().isoformat()}"
        rows.append({"element_id": element, "mimic_item_id": item, "mimic_label": label, "mimic_unit": unit,
                     "loinc_code": code, "loinc_long_name": name, "code_source": source,
                     "verified": verified if code else "", "note": note})
    with open(args.out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    bad = [r for r in rows if r["loinc_long_name"] in ("NOT FOUND",) or "Deprecated" in r["loinc_long_name"]]
    print(f"Wrote {len(rows)} rows ({sum(bool(r['loinc_code']) for r in rows)} with a LOINC code) to {args.out}")
    for r in bad:
        print(f"  check {r['loinc_code']}: {r['loinc_long_name']}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
