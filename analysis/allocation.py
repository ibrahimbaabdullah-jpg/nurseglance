"""Balanced allocation list for the proposed crossover study (docs/protocol.md).

Study mode builds each session from one seed (app/study.make_plan). A random seed
balances the design only on average, so the protocol uses a list prepared in
advance instead. Each seed fixes three things: which view comes first, which
standard case goes with NurseGlance, and which complex case goes with
NurseGlance. That gives 8 sequences. The list puts all 8 in each block of 8, in
random order, so any 8 consecutive nurses are fully balanced, and 40 nurses give
each sequence 5 times. Case order within a view stays random.

Run: python analysis/allocation.py [--n 40] [--master-seed 2027] [--out FILE]
A real list would be made by someone outside the session team, with a master
seed they keep private until enrollment ends.
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.study import make_plan  # noqa: E402


def sequence(seed: int) -> tuple[str, str, str]:
    plan = make_plan(seed)
    glance = next(b for b in plan if b["view"] == "glance")
    std = next(c for c in glance["cases"] if c.startswith("S"))
    cpx = next(c for c in glance["cases"] if c.startswith("C"))
    return plan[0]["view"], std, cpx


def seeds_by_sequence(max_seed: int = 9999) -> dict[tuple, list[int]]:
    out: dict[tuple, list[int]] = {}
    for seed in range(1, max_seed + 1):
        out.setdefault(sequence(seed), []).append(seed)
    return out


def allocation(n: int, master_seed: int) -> list[dict]:
    rng = random.Random(master_seed)
    pool = seeds_by_sequence()
    for seeds in pool.values():
        rng.shuffle(seeds)
    keys = sorted(pool)
    rows = []
    while len(rows) < n:
        block = keys[:]
        rng.shuffle(block)
        for key in block:
            if len(rows) == n:
                break
            seed = pool[key].pop()
            plan = make_plan(seed)
            rows.append({
                "participant": f"P{len(rows) + 1:02d}",
                "seed": seed,
                "first_view": key[0],
                "glance_cases": "+".join(next(b for b in plan if b["view"] == "glance")["cases"]),
                "tabbed_cases": "+".join(next(b for b in plan if b["view"] == "tabbed")["cases"]),
            })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--master-seed", type=int, default=2027)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    rows = allocation(args.n, args.master_seed)
    handle = open(args.out, "w", newline="", encoding="utf-8") if args.out else sys.stdout
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    if args.out:
        handle.close()


if __name__ == "__main__":
    main()
