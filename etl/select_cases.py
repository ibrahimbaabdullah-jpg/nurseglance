#!/usr/bin/env python3
"""Suggest 2 standard and 2 complex ICU handoff cases from the MIMIC-IV demo (CSV).

    python etl/select_cases.py --csv-dir data/raw/physionet.org/files/mimic-iv-demo/2.2

Writes:
    docs/case_candidates.csv  every eligible stay with its best handoff time
    etl/cases.json            the 4 suggested cases (review, then edit freely)
    docs/cases_draft.md       a template for your own clinical summaries

Definitions (edit here or in etl/config.py):
    complex  = invasive ventilation AND a vasopressor in the 12 h before handoff
    standard = no invasive ventilation and no vasopressor during the whole ICU stay
    handoff  = 07:00 or 19:00, at least 24 h after ICU admission, with the
               patient still in the ICU at least 2 h later

The script only ranks stays. You choose the final cases with your clinical judgment.
"""
from __future__ import annotations

import argparse
import bisect
import json
import sys
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pandas as pd

if __package__ in (None, ""):  # allow "python etl/select_cases.py"
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from etl import config  # noqa: E402

MIN_LOS_HOURS = 48
MIN_HOURS_BEFORE_HANDOFF = 24
MIN_HOURS_AFTER_HANDOFF = 2
MIN_HR_ENTRIES_12H = 6   # at least this many heart-rate entries in the 12 h before handoff
MIN_LABS_24H = 3         # standard cases need some labs to ask about


# ---------------------------------------------------------------- loading

def read_table(csv_dir: Path, name: str, **kwargs) -> pd.DataFrame:
    """Read hosp/... or icu/... as .csv.gz or .csv."""
    for path in (csv_dir / f"{name}.csv.gz", csv_dir / f"{name}.csv"):
        if path.exists():
            return pd.read_csv(path, **kwargs)
    raise FileNotFoundError(f"Could not find {name}.csv(.gz) under {csv_dir}")


def to_dt(series: pd.Series) -> list:
    return [ts.to_pydatetime() if pd.notna(ts) else None for ts in pd.to_datetime(series)]


def intervals_by(df: pd.DataFrame, key: str) -> dict:
    """key -> list of (start, end) datetimes."""
    out = defaultdict(list)
    for k, s, e in zip(df[key], to_dt(df["starttime"]), to_dt(df["endtime"])):
        if s is not None:
            out[k].append((s, e or s))
    return out


def times_by(df: pd.DataFrame, key: str, col: str = "charttime") -> dict:
    """key -> sorted list of datetimes."""
    out = defaultdict(list)
    for k, t in zip(df[key], to_dt(df[col])):
        if t is not None:
            out[k].append(t)
    for v in out.values():
        v.sort()
    return out


# ---------------------------------------------------------------- windows

def candidate_handoffs(intime: datetime, outtime: datetime,
                       hours=config.SHIFT_CHANGE_HOURS,
                       min_before=MIN_HOURS_BEFORE_HANDOFF,
                       min_after=MIN_HOURS_AFTER_HANDOFF) -> list[datetime]:
    """Shift-change times inside the stay that leave a full lookback window."""
    first = intime + timedelta(hours=min_before)
    last = outtime - timedelta(hours=min_after)
    found = []
    day: date = first.date()
    while datetime.combine(day, time(0)) <= last:
        for hour in hours:
            moment = datetime.combine(day, time(hour))
            if first <= moment <= last:
                found.append(moment)
        day += timedelta(days=1)
    return found


def count_between(sorted_times: list[datetime], start: datetime, end: datetime) -> int:
    """Number of times t with start < t <= end."""
    return bisect.bisect_right(sorted_times, end) - bisect.bisect_right(sorted_times, start)


def overlaps(intervals: list[tuple], start: datetime, end: datetime) -> bool:
    return any(s < end and e > start for s, e in intervals)


def is_icu_unit(name: str) -> bool:
    return not any(word in str(name) for word in ("Stepdown", "Intermediate"))


# ---------------------------------------------------------------- main logic

def build_candidates(csv_dir: Path) -> pd.DataFrame:
    stays = read_table(csv_dir, "icu/icustays")
    stays = stays[(stays["los"] * 24 >= MIN_LOS_HOURS) & stays["first_careunit"].map(is_icu_unit)]
    stays = stays.reset_index(drop=True)
    stay_ids = set(stays["stay_id"])
    hadm_ids = set(stays["hadm_id"])

    proc = read_table(csv_dir, "icu/procedureevents",
                      usecols=["stay_id", "itemid", "starttime", "endtime"])
    vent = intervals_by(proc[(proc["itemid"] == config.INVASIVE_VENT) & proc["stay_id"].isin(stay_ids)], "stay_id")

    inputs = read_table(csv_dir, "icu/inputevents",
                        usecols=["stay_id", "itemid", "starttime", "endtime"])
    pressors = intervals_by(inputs[inputs["itemid"].isin(config.VASOPRESSORS) & inputs["stay_id"].isin(stay_ids)], "stay_id")

    labs = read_table(csv_dir, "hosp/labevents", usecols=["hadm_id", "charttime", "flag"])
    labs = labs[labs["hadm_id"].isin(hadm_ids)]
    lab_times = times_by(labs, "hadm_id")
    abnormal_times = times_by(labs[labs["flag"] == "abnormal"], "hadm_id")

    chart = read_table(csv_dir, "icu/chartevents", usecols=["stay_id", "itemid", "charttime"])
    hr_times = times_by(chart[(chart["itemid"] == config.HEART_RATE) & chart["stay_id"].isin(stay_ids)], "stay_id")

    # Clinical context for your review.
    patients = read_table(csv_dir, "hosp/patients")
    admissions = read_table(csv_dir, "hosp/admissions")
    diagnoses = read_table(csv_dir, "hosp/diagnoses_icd")
    titles = read_table(csv_dir, "hosp/d_icd_diagnoses")
    principal = (diagnoses[diagnoses["seq_num"] == 1]
                 .merge(titles, on=["icd_code", "icd_version"], how="left")
                 .set_index("hadm_id")["long_title"].to_dict())
    pat = patients.set_index("subject_id").to_dict("index")
    adm = admissions.set_index("hadm_id").to_dict("index")

    rows = []
    for stay in stays.itertuples(index=False):
        intime = pd.Timestamp(stay.intime).to_pydatetime()
        outtime = pd.Timestamp(stay.outtime).to_pydatetime()
        vent_iv = vent.get(stay.stay_id, [])
        press_iv = pressors.get(stay.stay_id, [])
        hr = hr_times.get(stay.stay_id, [])
        lab_t = lab_times.get(stay.hadm_id, [])
        abn_t = abnormal_times.get(stay.hadm_id, [])

        windows = []
        for t in candidate_handoffs(intime, outtime):
            start12, start24 = t - timedelta(hours=12), t - timedelta(hours=24)
            windows.append({
                "handoff_time": t,
                "hr_entries_12h": count_between(hr, start12, t),
                "labs_24h": count_between(lab_t, start24, t),
                "abnormal_labs_24h": count_between(abn_t, start24, t),
                "vent_12h": overlaps(vent_iv, start12, t),
                "pressor_12h": overlaps(press_iv, start12, t),
            })
        windows = [w for w in windows if w["hr_entries_12h"] >= MIN_HR_ENTRIES_12H]
        if not windows:
            continue

        p = pat.get(stay.subject_id, {})
        a = adm.get(stay.hadm_id, {})
        admit_year = pd.Timestamp(a.get("admittime", stay.intime)).year
        age = int(p.get("anchor_age", 0)) + (admit_year - int(p.get("anchor_year", admit_year)))
        context = {
            "subject_id": stay.subject_id,
            "hadm_id": stay.hadm_id,
            "stay_id": stay.stay_id,
            "careunit": stay.first_careunit,
            "icu_intime": intime,
            "icu_outtime": outtime,
            "icu_los_days": round(float(stay.los), 1),
            "age": ">89" if age > 89 else age,
            "gender": p.get("gender"),
            "admission_type": a.get("admission_type"),
            "principal_diagnosis": principal.get(stay.hadm_id),
            "died_in_hospital": bool(a.get("hospital_expire_flag", 0)),
            "vent_any": bool(vent_iv),
            "pressor_any": bool(press_iv),
        }

        complex_w = [w for w in windows if w["vent_12h"] and w["pressor_12h"]]
        if complex_w:
            best = max(complex_w, key=lambda w: (w["abnormal_labs_24h"], w["hr_entries_12h"], w["labs_24h"]))
            rows.append({**context, "complexity": "complex", **best})

        if not vent_iv and not press_iv:
            std_w = [w for w in windows if w["labs_24h"] >= MIN_LABS_24H]
            if std_w:
                best = max(std_w, key=lambda w: (w["hr_entries_12h"], w["labs_24h"], -w["abnormal_labs_24h"]))
                rows.append({**context, "complexity": "standard", **best})

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["icu_day"] = [(h.date() - i.date()).days + 1 for h, i in zip(df["handoff_time"], df["icu_intime"])]
    return df


def rank(df: pd.DataFrame) -> pd.DataFrame:
    """Order candidates: complex by abnormal labs then data density;
    standard by data density, preferring a few (1-8) abnormal labs."""
    cx = df[df["complexity"] == "complex"].sort_values(
        ["abnormal_labs_24h", "hr_entries_12h"], ascending=False)
    std = df[df["complexity"] == "standard"].copy()
    std["_dense"] = std["hr_entries_12h"] >= 10
    std["_some_abnormal"] = std["abnormal_labs_24h"].between(1, 8)
    std = std.sort_values(["_dense", "_some_abnormal", "hr_entries_12h", "abnormal_labs_24h"],
                          ascending=[False, False, False, True]).drop(columns=["_dense", "_some_abnormal"])
    ranked = pd.concat([cx, std], ignore_index=True)
    ranked["rank_in_group"] = ranked.groupby("complexity").cumcount() + 1
    return ranked


def pick_cases(ranked: pd.DataFrame, n_each: int = 2) -> list[dict]:
    """Top complex and standard stays, one stay per patient."""
    chosen, used = [], set()
    for group, prefix in (("complex", "C"), ("standard", "S")):
        n = 0
        for row in ranked[ranked["complexity"] == group].to_dict("records"):
            if row["subject_id"] in used:
                continue
            used.add(row["subject_id"])
            n += 1
            chosen.append({"case_id": f"{prefix}{n}", **row})
            if n == n_each:
                break
    order = {"S": 0, "C": 1}
    return sorted(chosen, key=lambda r: (order[r["case_id"][0]], r["case_id"]))  # S1, S2, C1, C2


def why(row: dict) -> str:
    parts = []
    if row["complexity"] == "complex":
        parts.append("invasive ventilation and a vasopressor in the 12 h before handoff")
    else:
        parts.append("no invasive ventilation or vasopressor during the ICU stay")
    parts.append(f"{row['abnormal_labs_24h']} abnormal of {row['labs_24h']} lab results in the prior 24 h")
    parts.append(f"{row['hr_entries_12h']} heart-rate entries in the prior 12 h")
    return "; ".join(parts)


def write_outputs(ranked: pd.DataFrame, picks: list[dict]) -> None:
    out = ranked.copy()
    for col in ("handoff_time", "icu_intime", "icu_outtime"):
        out[col] = [t.isoformat(timespec="seconds") for t in out[col]]
    cols = ["complexity", "rank_in_group", "subject_id", "hadm_id", "stay_id", "careunit",
            "handoff_time", "icu_day", "icu_intime", "icu_outtime", "icu_los_days", "age", "gender",
            "admission_type", "principal_diagnosis", "died_in_hospital", "vent_12h", "pressor_12h",
            "vent_any", "pressor_any", "abnormal_labs_24h", "labs_24h", "hr_entries_12h"]
    (config.REPO_ROOT / "docs").mkdir(exist_ok=True)
    out[cols].to_csv(config.REPO_ROOT / "docs/case_candidates.csv", index=False)

    cases = {
        "_note": ("Suggested by etl/select_cases.py. Review each case clinically and edit "
                  "freely (swap stays, move handoff times), then run etl/build_cases.py."),
        "lookback_hours": config.LOOKBACK_HOURS,
        "trend_hours": config.TREND_HOURS,
        "lab_lookback_hours": config.LAB_LOOKBACK_HOURS,
        "lookahead_hours": config.LOOKAHEAD_HOURS,
        "cases": [{
            "case_id": r["case_id"],
            "complexity": r["complexity"],
            "subject_id": int(r["subject_id"]),
            "hadm_id": int(r["hadm_id"]),
            "stay_id": int(r["stay_id"]),
            "careunit": r["careunit"],
            "handoff_time": r["handoff_time"].isoformat(timespec="seconds"),
            "why": why(r),
        } for r in picks],
    }
    config.CASES_FILE.write_text(json.dumps(cases, indent=2) + "\n", encoding="utf-8")

    lines = ["# NurseGlance cases (draft)", "",
             "Suggested by `etl/select_cases.py`. Replace each summary with your own clinical words.", ""]
    for r in picks:
        lines += [
            f"## {r['case_id']} — {r['complexity']}", "",
            f"- Stay {r['stay_id']} (subject {r['subject_id']}, admission {r['hadm_id']}), {r['careunit']}",
            f"- Handoff: {r['handoff_time']:%Y-%m-%d %H:%M}, ICU day {r['icu_day']}",
            f"- {r['age']} y, {r['gender']}; {r['admission_type']}; principal diagnosis: {r['principal_diagnosis']}",
            f"- Died later in this hospital stay: {'yes' if r['died_in_hospital'] else 'no'}",
            f"- Why {r['complexity']}: {why(r)}",
            "- Clinical summary (3 lines, your words): ...",
            "",
        ]
    (config.REPO_ROOT / "docs/cases_draft.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv-dir", type=Path, default=config.DEFAULT_CSV_DIR,
                        help="folder with hosp/ and icu/ from the MIMIC-IV demo v2.2")
    args = parser.parse_args(argv)
    if not (args.csv_dir / "icu").exists():
        parser.error(f"{args.csv_dir} has no icu/ folder. Run download_data.sh or pass --csv-dir.")

    candidates = build_candidates(args.csv_dir)
    if candidates.empty:
        print("No eligible stays found. Check --csv-dir.")
        return 1
    ranked = rank(candidates)
    picks = pick_cases(ranked)
    write_outputs(ranked, picks)

    n_cx = (ranked["complexity"] == "complex").sum()
    n_std = (ranked["complexity"] == "standard").sum()
    print(f"Eligible stays: {n_cx} complex, {n_std} standard (see docs/case_candidates.csv)\n")
    print("Suggested cases (etl/cases.json):")
    for r in picks:
        print(f"  {r['case_id']}  stay {r['stay_id']}  {r['handoff_time']:%Y-%m-%d %H:%M}  "
              f"{r['careunit']}  | {why(r)}")
    print("\nReview these clinically before building. Edit etl/cases.json to swap any case.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
