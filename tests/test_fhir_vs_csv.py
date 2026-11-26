"""Check that values built from FHIR match the MIMIC-IV demo CSV tables.

Samples 20 numeric observations per case and looks each one up in the CSV
(same patient or stay, item ID and chart time). Skipped when the CSV demo or
the processed case files are missing, for example in CI.

    NURSEGLANCE_CSV_DIR=path/to/mimic-iv-demo/2.2 pytest tests/test_fhir_vs_csv.py
"""
import json
import os
import random
from pathlib import Path

import pandas as pd
import pytest

from etl import config

CSV_DIR = Path(os.environ.get("NURSEGLANCE_CSV_DIR", config.DEFAULT_CSV_DIR))
PROCESSED = Path(os.environ.get("NURSEGLANCE_PROCESSED_DIR", config.PROCESSED_DIR))
CASE_FILES = sorted(PROCESSED.glob("case_*.json"))
SAMPLE_SIZE = 20
NEGATED = {str(i) for i in config.NEGATE_ITEMS}

# FHIR source -> (CSV table, key column, value column)
TABLES = {
    "chartevents": ("icu/chartevents", "stay_id", "valuenum"),
    "outputevents": ("icu/outputevents", "stay_id", "value"),
    "labevents": ("hosp/labevents", "subject_id", "valuenum"),
}

pytestmark = pytest.mark.skipif(not (CSV_DIR / "icu").exists() or not CASE_FILES,
                                reason="needs the MIMIC-IV demo CSV files and data/processed/case_*.json")


def read_csv(name, columns):
    for path in (CSV_DIR / f"{name}.csv.gz", CSV_DIR / f"{name}.csv"):
        if path.exists():
            return pd.read_csv(path, usecols=columns)
    raise FileNotFoundError(name)


@pytest.fixture(scope="module")
def tables():
    return {src: read_csv(name, [key, "itemid", "charttime", col]) for src, (name, key, col) in TABLES.items()}


@pytest.mark.parametrize("case_file", CASE_FILES, ids=lambda p: p.stem)
def test_sampled_values_match_csv(case_file, tables):
    case = json.loads(case_file.read_text(encoding="utf-8"))
    keys = {"stay_id": int(case["stay"]["stay_id"]), "subject_id": int(case["patient"]["subject_id"])}
    candidates = [o for o in case["observations"]
                  if o["source"] in TABLES and o["value"] is not None and o["item_id"] not in NEGATED]
    assert candidates, "no observations to check"
    sample = random.Random(0).sample(candidates, min(SAMPLE_SIZE, len(candidates)))

    mismatches = []
    for o in sample:
        _, key, col = TABLES[o["source"]]
        df = tables[o["source"]]
        rows = df[(df[key] == keys[key]) & (df["itemid"] == int(o["item_id"]))
                  & (df["charttime"] == o["t"].replace("T", " "))]
        values = [float(v) for v in rows[col].dropna()]
        if not any(abs(v - o["value"]) < 1e-6 for v in values):
            mismatches.append(f"{o['source']} item {o['item_id']} at {o['t']}: FHIR {o['value']} vs CSV {values}")
    assert not mismatches, "\n".join(mismatches)
