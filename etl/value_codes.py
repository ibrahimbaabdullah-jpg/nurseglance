#!/usr/bin/env python3
"""Rebuild the code -> text table for MIMIC text items that FHIR carries as numbers.

    python etl/value_codes.py            # -> docs/value_codes.csv

The MIMIC-IV demo on FHIR (v2.1.0) stores some charted text items, such as
ventilator mode and CAM-ICU, as their numeric MIMIC code only. This script reads
the CSV demo's chartevents, where each row has both the text and the code, and
writes one row per (item, code) pair. build_cases.py reads that file to put the
text back. The table is small and committed, so building cases needs no CSV.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from etl import config  # noqa: E402


def build_table(chartevents: Path) -> pd.DataFrame:
    ids = set(config.CODED_TEXT_ITEMS)
    rows = []
    for chunk in pd.read_csv(chartevents, usecols=["itemid", "value", "valuenum"], chunksize=500_000,
                         keep_default_na=False, na_values={"valuenum": [""]}):
        chunk = chunk[chunk["itemid"].isin(ids) & chunk["valuenum"].notna() & (chunk["value"] != "")]
        rows.append(chunk)
    df = pd.concat(rows)
    df["value"] = df["value"].str.strip().str.rstrip(".")
    counts = (df.groupby(["itemid", "valuenum", "value"]).size().rename("n").reset_index()
              .sort_values(["itemid", "valuenum", "n"], ascending=[True, True, False]))
    # One text per code: keep the most frequent spelling.
    table = counts.drop_duplicates(["itemid", "valuenum"]).rename(columns={"valuenum": "code", "value": "text"})
    table["label"] = table["itemid"].map(config.CODED_TEXT_ITEMS)
    return table[["itemid", "label", "code", "text", "n"]]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv-dir", type=Path, default=config.DEFAULT_CSV_DIR)
    parser.add_argument("--out", type=Path, default=config.VALUE_CODES_FILE)
    args = parser.parse_args(argv)
    path = args.csv_dir / "icu" / "chartevents.csv.gz"
    if not path.exists():
        path = args.csv_dir / "icu" / "chartevents.csv"
    table = build_table(path)
    table.to_csv(args.out, index=False)
    print(f"Wrote {len(table)} code -> text pairs for {table['itemid'].nunique()} items to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
