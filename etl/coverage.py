#!/usr/bin/env python3
"""How much of what nurses need at handoff can come from FHIR? (Research question 1)

    python etl/coverage.py

Reads data/processed/case_*.json (from build_cases.py) and writes docs/coverage.csv.

    mappable = the element has a source in the FHIR demo files at all
    filled   = that source had a value for the case in its time window
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

if __package__ in (None, ""):  # allow "python etl/coverage.py"
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from etl import config  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--processed-dir", type=Path, default=config.PROCESSED_DIR)
    parser.add_argument("--out", type=Path, default=config.REPO_ROOT / "docs/coverage.csv")
    args = parser.parse_args(argv)

    files = sorted(args.processed_dir.glob("case_*.json"))
    if not files:
        print(f"No case_*.json files in {args.processed_dir}. Run etl/build_cases.py first.")
        return 1
    cases = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    order = {"S": 0, "C": 1}
    cases.sort(key=lambda c: (order.get(c["case_id"][:1], 2), c["case_id"]))
    ids = [c["case_id"] for c in cases]
    element_ids = list(cases[0]["elements"])

    rows = []
    for el_id in element_ids:
        first = cases[0]["elements"][el_id]
        row = {"element_id": el_id, "organ_system": first["organ_system"], "label": first["label"],
               "source": first["source"], "mappable": "yes" if first.get("mappable") else "no"}
        for case in cases:
            row[case["case_id"]] = "yes" if case["elements"].get(el_id, {}).get("has_data") else "no"
        rows.append(row)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    groups = defaultdict(list)
    for row in rows:
        groups[row["organ_system"]].append(row)
    header = f"{'Organ system':<20}{'Elements':>9}{'Mappable':>10}" + "".join(f"{i:>8}" for i in ids)
    print(header)
    print("-" * len(header))
    for system, members in list(groups.items()) + [("All", rows)]:
        n = len(members)
        mappable = sum(r["mappable"] == "yes" for r in members)
        filled = "".join(f"{sum(r[i] == 'yes' for r in members) / n:>8.0%}" for i in ids)
        print(f"{system:<20}{n:>9}{mappable / n:>10.0%}{filled}")
    print(f"\nPer-case columns show the share of elements with data in that case's window.")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
