"""
Export all generated tables to data/tables.xlsx.

Sheets
------
  1. Simulation - Existing — per-day free-time stats + weekly summary + class-load stats
  2. Simulation - Proposed — same for proposed schedule
  3. Block Mapping         — existing → proposed nearest-block mapping with distances
  4. Course Distribution   — 500-course allocation for existing and proposed
  5. Student Analysis      — full existing vs proposed comparison (1,500 students each)
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from schedule import Schedule, DAY_ORDER, DAY_NAMES
from simulate import run, HISTORICAL_WEIGHTS, _pct as _sim_pct
from generate_schedules import _block_distance, _nearest, _allocate
from analyze_student_schedules import _student_metrics, _aggregate

DATA_DIR = Path(__file__).parent.parent / "data"
OUT      = DATA_DIR / "tables.xlsx"

SIM_N    = 10_000
SIM_SEED = 42


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mins(t) -> int:
    return t.hour * 60 + t.minute


def _pct(data: list, p: float) -> float:
    sd = sorted(data)
    if not sd:
        return 0.0
    k  = (len(sd) - 1) * p / 100
    lo = int(k)
    hi = min(lo + 1, len(sd) - 1)
    return sd[lo] + (k - lo) * (sd[hi] - sd[lo])


# ---------------------------------------------------------------------------
# Table builders
# ---------------------------------------------------------------------------

def _sim_day_df(sim) -> pd.DataFrame:
    rows = []
    for day in DAY_ORDER:
        dg = sim.day_gaps[day]
        rows.append({
            "Day":         DAY_NAMES[day],
            "Mean (min)":  round(statistics.mean(dg), 1),
            "Median (min)": round(statistics.median(dg), 1),
            "p25 (min)":   round(_sim_pct(dg, 25), 0),
            "p75 (min)":   round(_sim_pct(dg, 75), 0),
            "Max (min)":   max(dg),
        })
    return pd.DataFrame(rows)


def _sim_weekly_df(sim) -> pd.DataFrame:
    wg = sim.weekly_gaps
    rows = [
        {"Metric": "Attempts",                "Value": sim.n_attempts},
        {"Metric": "Conflicts",               "Value": sim.n_conflicts},
        {"Metric": "Conflict rate (%)",       "Value": round(sim.conflict_pct, 1)},
        {"Metric": "Valid schedules",         "Value": sim.n_valid},
        {"Metric": "Mean weekly free (min)",  "Value": round(statistics.mean(wg), 1)},
        {"Metric": "Median weekly free (min)","Value": round(statistics.median(wg), 1)},
        {"Metric": "Std dev (min)",           "Value": round(statistics.stdev(wg), 1)},
        {"Metric": "p25 (min)",               "Value": round(_sim_pct(wg, 25), 1)},
        {"Metric": "p75 (min)",               "Value": round(_sim_pct(wg, 75), 1)},
        {"Metric": "Min (min)",               "Value": min(wg)},
        {"Metric": "Max (min)",               "Value": max(wg)},
    ]
    return pd.DataFrame(rows)


def _sim_load_df(sim) -> pd.DataFrame:
    rows = []
    for n in (3, 4, 5):
        data = sim.class_mins_by_n[n]
        if data:
            rows.append({
                "Classes":      n,
                "Students":     len(data),
                "Mean (hrs)":   round(statistics.mean(data) / 60, 2),
                "Median (hrs)": round(statistics.median(data) / 60, 2),
                "Min (hrs)":    round(min(data) / 60, 2),
                "Max (hrs)":    round(max(data) / 60, 2),
            })
    return pd.DataFrame(rows)


def _block_mapping_df(existing: Schedule, proposed: Schedule) -> pd.DataFrame:
    existing_weights = {
        b.name: HISTORICAL_WEIGHTS.get(b.name, 0) for b in existing.time_blocks
    }
    existing_weights = {k: v for k, v in existing_weights.items() if v > 0}
    alloc = _allocate(existing_weights, 500)
    existing_by_name = {b.name: b for b in existing.time_blocks}

    rows = []
    for src_name, count in sorted(alloc.items(), key=lambda x: -x[1]):
        src     = existing_by_name[src_name]
        nearest = _nearest(src, proposed.time_blocks)
        dist    = _block_distance(src, nearest)
        rows.append({
            "Existing Block":    src_name,
            "Courses (of 500)": count,
            "→ Proposed Block":  nearest.name,
            "Distance":         round(dist, 1),
        })
    return pd.DataFrame(rows)


def _course_dist_df(ex_500: dict, pr_500: dict) -> pd.DataFrame:
    ex_alloc = ex_500["courses_by_block"]
    pr_alloc = pr_500["courses_by_block"]

    # Existing rows (sorted by count desc)
    ex_rows = [
        {
            "Existing Block":    b,
            "Existing Courses":  n,
            "Existing %":        round(100 * n / 500, 1),
        }
        for b, n in sorted(ex_alloc.items(), key=lambda x: -x[1])
    ]
    # Proposed rows (sorted by count desc)
    pr_rows = [
        {
            "Proposed Block":    b,
            "Proposed Courses":  n,
            "Proposed %":        round(100 * n / 500, 1),
        }
        for b, n in sorted(pr_alloc.items(), key=lambda x: -x[1])
    ]

    # Pad shorter list so they concat cleanly side by side
    n = max(len(ex_rows), len(pr_rows))
    blank_ex = {"Existing Block": "", "Existing Courses": None, "Existing %": None}
    blank_pr = {"Proposed Block": "", "Proposed Courses": None, "Proposed %": None}
    ex_rows += [blank_ex] * (n - len(ex_rows))
    pr_rows += [blank_pr] * (n - len(pr_rows))

    return pd.concat(
        [pd.DataFrame(ex_rows), pd.DataFrame(pr_rows)],
        axis=1,
    )


def _student_analysis_df(ex_raw, pr_raw, ex_agg, pr_agg) -> pd.DataFrame:
    def row(metric, ex_val, pr_val, fmt=".1f", unit=""):
        delta = pr_val - ex_val
        return {
            "Metric":   metric,
            "Existing": f"{ex_val:{fmt}}{unit}",
            "Proposed": f"{pr_val:{fmt}}{unit}",
            "Delta":    f"{delta:+{fmt}}{unit}",
        }

    def section(title):
        return {"Metric": title, "Existing": "", "Proposed": "", "Delta": ""}

    ex_loads = [s["n_classes"] for s in ex_raw["schedules"]]
    pr_loads = [s["n_classes"] for s in pr_raw["schedules"]]
    wc_a = [v / 60 for v in ex_agg["weekly_contact"]]
    wc_b = [v / 60 for v in pr_agg["weekly_contact"]]
    wf_a = ex_agg["weekly_free"]
    wf_b = pr_agg["weekly_free"]

    rows: list[dict] = []

    rows.append(section("GENERATION"))
    rows.append({"Metric": "Attempts",     "Existing": ex_raw["n_attempts"],  "Proposed": pr_raw["n_attempts"],  "Delta": pr_raw["n_attempts"]  - ex_raw["n_attempts"]})
    rows.append({"Metric": "Conflicts",    "Existing": ex_raw["n_conflicts"], "Proposed": pr_raw["n_conflicts"], "Delta": pr_raw["n_conflicts"] - ex_raw["n_conflicts"]})
    rows.append(row("Conflict rate", ex_raw["conflict_pct"], pr_raw["conflict_pct"], ".2f", "%"))

    rows.append(section("CLASS LOAD"))
    for n in (3, 4, 5):
        pa = 100 * ex_loads.count(n) / len(ex_loads)
        pb = 100 * pr_loads.count(n) / len(pr_loads)
        rows.append(row(f"  {n} classes", pa, pb, ".1f", "%"))

    rows.append(section("WEEKLY CONTACT TIME"))
    rows.append(row("Mean (hrs)",   statistics.mean(wc_a),   statistics.mean(wc_b),   ".2f", "h"))
    rows.append(row("Median (hrs)", statistics.median(wc_a), statistics.median(wc_b), ".2f", "h"))
    rows.append(row("p25 (hrs)",    _pct(wc_a, 25),          _pct(wc_b, 25),          ".2f", "h"))
    rows.append(row("p75 (hrs)",    _pct(wc_a, 75),          _pct(wc_b, 75),          ".2f", "h"))

    rows.append(section("WEEKLY FREE TIME (8am–5pm, class days only)"))
    rows.append(row("Mean (min)",   statistics.mean(wf_a),   statistics.mean(wf_b),   ".1f", "min"))
    rows.append(row("Median (min)", statistics.median(wf_a), statistics.median(wf_b), ".1f", "min"))
    rows.append(row("p25 (min)",    _pct(wf_a, 25),          _pct(wf_b, 25),          ".1f", "min"))
    rows.append(row("p75 (min)",    _pct(wf_a, 75),          _pct(wf_b, 75),          ".1f", "min"))

    rows.append(section("MEAN FREE TIME PER CLASS-DAY (min)"))
    for day in DAY_ORDER:
        ma = statistics.mean(ex_agg["day_free"][day])
        mb = statistics.mean(pr_agg["day_free"][day])
        rows.append(row(DAY_NAMES[day], ma, mb, ".1f", "min"))

    rows.append(section("LARGEST SINGLE FREE BLOCK (mid-day)"))
    rows.append(row("Mean (min)",   statistics.mean(ex_agg["max_gap"]),   statistics.mean(pr_agg["max_gap"]),   ".1f", "min"))
    rows.append(row("Median (min)", statistics.median(ex_agg["max_gap"]), statistics.median(pr_agg["max_gap"]), ".1f", "min"))

    rows.append(section("CLASS-DAY SPREAD"))
    cd_a, cd_b = ex_agg["class_days"], pr_agg["class_days"]
    rows.append(row("Mean days/week", statistics.mean(cd_a), statistics.mean(cd_b), ".1f", "d"))
    for d in (2, 3, 4, 5):
        pa = 100 * cd_a.count(d) / len(cd_a)
        pb = 100 * cd_b.count(d) / len(cd_b)
        rows.append(row(f"  {d} days", pa, pb, ".1f", "%"))

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Loading schedules…")
    existing = Schedule.from_json(DATA_DIR / "existing_schedule.json")
    proposed = Schedule.from_json(DATA_DIR / "proposed_schedule.json")

    print("Running simulations…")
    ex_sim = run(existing, n=SIM_N, seed=SIM_SEED)
    pr_sim = run(proposed,  n=SIM_N, seed=SIM_SEED)

    print("Loading student schedules…")
    with open(DATA_DIR / "student_schedules_1500.json") as f:
        student_data = json.load(f)
    ex_raw = student_data["existing"]
    pr_raw = student_data["proposed"]
    ex_block = {b.name: b for b in existing.time_blocks}
    pr_block = {b.name: b for b in proposed.time_blocks}
    ex_metrics = [_student_metrics(s["courses"], ex_block) for s in ex_raw["schedules"]]
    pr_metrics = [_student_metrics(s["courses"], pr_block) for s in pr_raw["schedules"]]
    ex_agg = _aggregate(ex_metrics)
    pr_agg = _aggregate(pr_metrics)

    print("Loading course distributions…")
    with open(DATA_DIR / "schedule_existing_500.json") as f:
        ex_500 = json.load(f)
    with open(DATA_DIR / "schedule_proposed_500.json") as f:
        pr_500 = json.load(f)

    print("Writing Excel…")
    with pd.ExcelWriter(OUT, engine="openpyxl") as writer:

        # 1 & 2. Simulation sheets
        for label, sim in [("Existing", ex_sim), ("Proposed", pr_sim)]:
            sheet = f"Simulation - {label}"
            df_day  = _sim_day_df(sim)
            df_wk   = _sim_weekly_df(sim)
            df_load = _sim_load_df(sim)
            r0 = 0
            df_day.to_excel(writer,  sheet_name=sheet, index=False, startrow=r0)
            r1 = r0 + len(df_day) + 2
            df_wk.to_excel(writer,   sheet_name=sheet, index=False, startrow=r1)
            r2 = r1 + len(df_wk) + 2
            df_load.to_excel(writer, sheet_name=sheet, index=False, startrow=r2)

        # 5. Block Mapping
        _block_mapping_df(existing, proposed).to_excel(
            writer, sheet_name="Block Mapping", index=False
        )

        # 6. Course Distribution
        _course_dist_df(ex_500, pr_500).to_excel(
            writer, sheet_name="Course Distribution", index=False
        )

        # 7. Student Analysis
        _student_analysis_df(ex_raw, pr_raw, ex_agg, pr_agg).to_excel(
            writer, sheet_name="Student Analysis", index=False
        )

    print(f"Saved → {OUT}")


if __name__ == "__main__":
    main()
