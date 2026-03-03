"""
Analyze data/student_schedules_1500.json

Produces a side-by-side comparison of the existing and proposed schedules
across all 1,500 simulated student schedules.

Metrics
-------
  Conflict rate          — from generation (attempts vs valid)
  Weekly free time       — gaps between classes within the 8am–5pm window
                           on each day that has at least one class
  Per-day free time      — same, broken out by day
  Contact hours/week     — time actually in class
  Class-day spread       — how many distinct days/week a student has class
  Back-to-back pairs     — consecutive classes with zero gap between them
  Largest single gap     — longest unbroken free block mid-day
"""

from __future__ import annotations

import json
import statistics
import sys
from datetime import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from schedule import Schedule, TimeBlock, DAY_ORDER, DAY_NAMES

DATA_DIR   = Path(__file__).parent.parent / "data"
DAY_START  = time(8, 0)   # student day opens
DAY_END    = time(17, 0)  # student day closes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mins(t: time) -> int:
    return t.hour * 60 + t.minute

DAY_START_M = _mins(DAY_START)
DAY_END_M   = _mins(DAY_END)


def _free_time_day(blocks: list[TimeBlock]) -> tuple[int, int, int]:
    """Return (free_mins, contact_mins, n_back_to_back) for one day's blocks.

    free_mins      — total gap minutes within the 8am–5pm window
    contact_mins   — total class time that falls within the window
    n_back_to_back — number of consecutive class pairs with 0-min gap
    """
    sorted_b = sorted(blocks, key=lambda b: b.start)
    starts = [max(DAY_START_M, _mins(b.start)) for b in sorted_b]
    ends   = [min(DAY_END_M,   _mins(b.end))   for b in sorted_b]

    contact = sum(max(0, e - s) for s, e in zip(starts, ends))
    free    = 0
    btb     = 0
    cursor  = DAY_START_M
    for s, e in zip(starts, ends):
        if s > cursor:
            free += s - cursor
        elif s == cursor and cursor > DAY_START_M:
            btb += 1
        cursor = max(cursor, e)
    free += max(0, DAY_END_M - cursor)
    return free, contact, btb


def _largest_gap_day(blocks: list[TimeBlock]) -> int:
    """Largest single free block (minutes) within the 8am–5pm window."""
    sorted_b = sorted(blocks, key=lambda b: b.start)
    starts   = [max(DAY_START_M, _mins(b.start)) for b in sorted_b]
    ends     = [min(DAY_END_M,   _mins(b.end))   for b in sorted_b]

    gaps   = []
    cursor = DAY_START_M
    for s, e in zip(starts, ends):
        if s > cursor:
            gaps.append(s - cursor)
        cursor = max(cursor, e)
    gaps.append(max(0, DAY_END_M - cursor))
    return max(gaps) if gaps else 0


def _pct(data: list[float], p: float) -> float:
    sd = sorted(data)
    if not sd:
        return 0.0
    k  = (len(sd) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(sd) - 1)
    return sd[lo] + (k - lo) * (sd[hi] - sd[lo])


# ---------------------------------------------------------------------------
# Per-student metrics
# ---------------------------------------------------------------------------

def _student_metrics(
    courses: list[dict],
    block_by_name: dict[str, TimeBlock],
) -> dict:
    blocks = [block_by_name[c["block"]] for c in courses if c["block"] in block_by_name]

    weekly_free    = 0
    weekly_contact = 0
    weekly_btb     = 0
    day_free: dict[str, int]    = {}
    day_contact: dict[str, int] = {}
    largest_gaps: list[int]     = []
    class_days                  = 0

    for day in DAY_ORDER:
        day_blocks = [b for b in blocks if day in b.days]
        if not day_blocks:
            day_free[day]    = 0
            day_contact[day] = 0
            continue
        class_days += 1
        free, contact, btb = _free_time_day(day_blocks)
        day_free[day]    = free
        day_contact[day] = contact
        weekly_free      += free
        weekly_contact   += contact
        weekly_btb       += btb
        largest_gaps.append(_largest_gap_day(day_blocks))

    return {
        "weekly_free":    weekly_free,
        "weekly_contact": weekly_contact,
        "weekly_btb":     weekly_btb,
        "day_free":       day_free,
        "day_contact":    day_contact,
        "class_days":     class_days,
        "max_gap":        max(largest_gaps) if largest_gaps else 0,
    }


# ---------------------------------------------------------------------------
# Aggregate stats
# ---------------------------------------------------------------------------

def _aggregate(metrics: list[dict]) -> dict:
    def col(key):
        return [m[key] for m in metrics]

    wf = col("weekly_free")
    wc = col("weekly_contact")
    cd = col("class_days")
    mg = col("max_gap")
    btb = col("weekly_btb")

    return {
        "weekly_free":    wf,
        "weekly_contact": wc,
        "class_days":     cd,
        "max_gap":        mg,
        "weekly_btb":     btb,
        "day_free": {
            day: [m["day_free"][day] for m in metrics]
            for day in DAY_ORDER
        },
    }


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------

def _stat_row(label: str, a_vals: list[float], b_vals: list[float], unit: str = "min") -> None:
    def fmt(v: float) -> str:
        return f"{v:>7.1f}{unit}"
    ma, mb = statistics.mean(a_vals), statistics.mean(b_vals)
    delta  = mb - ma
    print(f"  {label:<28} {fmt(ma)}   {fmt(mb)}   {delta:>+8.1f}{unit}")


def _pct_row(label: str, a_vals: list[float], b_vals: list[float]) -> None:
    pa = 100 * sum(1 for v in a_vals if v > 0) / len(a_vals)
    pb = 100 * sum(1 for v in b_vals if v > 0) / len(b_vals)
    print(f"  {label:<28} {pa:>7.1f}%   {pb:>7.1f}%   {pb-pa:+.1f}%")


def _dist_row(label: str, a_vals: list, b_vals: list, val) -> None:
    pa = 100 * sum(1 for v in a_vals if v == val) / len(a_vals)
    pb = 100 * sum(1 for v in b_vals if v == val) / len(b_vals)
    print(f"  {label:<28} {pa:>7.1f}%   {pb:>7.1f}%   {pb-pa:+.1f}%")


def report(
    ex_raw: dict,
    pr_raw: dict,
    ex_agg: dict,
    pr_agg: dict,
) -> None:
    W = 72
    print("=" * W)
    print("Student Schedule Analysis — Existing vs Proposed  (n=1,500 each)")
    print("=" * W)
    print(f"  {'Metric':<28} {'Existing':>10}   {'Proposed':>10}   {'Delta':>8}")
    print(f"  {'-'*28} {'-'*10}   {'-'*10}   {'-'*8}")

    # --- Conflict / generation stats ----------------------------------------
    print(f"\n  GENERATION")
    print(f"  {'Attempts':<28} {ex_raw['n_attempts']:>9,}   {pr_raw['n_attempts']:>9,}"
          f"   {pr_raw['n_attempts']-ex_raw['n_attempts']:>+8,}")
    print(f"  {'Conflicts':<28} {ex_raw['n_conflicts']:>9,}   {pr_raw['n_conflicts']:>9,}"
          f"   {pr_raw['n_conflicts']-ex_raw['n_conflicts']:>+8,}")
    ecr, pcr = ex_raw['conflict_pct'], pr_raw['conflict_pct']
    print(f"  {'Conflict rate':<28} {ecr:>9.2f}%   {pcr:>9.2f}%   {pcr-ecr:>+7.2f}%")

    # --- Class load ---------------------------------------------------------
    print(f"\n  CLASS LOAD")
    ex_loads = [s["n_classes"] for s in ex_raw["schedules"]]
    pr_loads = [s["n_classes"] for s in pr_raw["schedules"]]
    for n in (3, 4, 5):
        pa = 100 * ex_loads.count(n) / len(ex_loads)
        pb = 100 * pr_loads.count(n) / len(pr_loads)
        print(f"  {'  '+str(n)+' classes':<28} {pa:>8.1f}%   {pb:>8.1f}%   {pb-pa:>+8.1f}%")

    # --- Contact hours ------------------------------------------------------
    print(f"\n  WEEKLY CONTACT TIME (hours in class)")
    wc_a = [v / 60 for v in ex_agg["weekly_contact"]]
    wc_b = [v / 60 for v in pr_agg["weekly_contact"]]
    for label, fn in [("Mean", statistics.mean), ("Median", statistics.median)]:
        va, vb = fn(wc_a), fn(wc_b)
        print(f"  {label:<28} {va:>7.1f}h   {vb:>7.1f}h   {vb-va:>+8.1f}h")
    for label, p in [("p25", 25), ("p75", 75)]:
        va, vb = _pct(wc_a, p), _pct(wc_b, p)
        print(f"  {label:<28} {va:>7.1f}h   {vb:>7.1f}h   {vb-va:>+8.1f}h")

    # --- Free time ----------------------------------------------------------
    print(f"\n  WEEKLY FREE TIME (gaps within 8am–5pm, days with class only)")
    wf_a = ex_agg["weekly_free"]
    wf_b = pr_agg["weekly_free"]
    for label, fn in [("Mean", statistics.mean), ("Median", statistics.median)]:
        va, vb = fn(wf_a), fn(wf_b)
        print(f"  {label:<28} {va:>7.1f}min   {vb:>7.1f}min   {vb-va:>+8.1f}min")
    for label, p in [("p25", 25), ("p75", 75)]:
        va, vb = _pct(wf_a, p), _pct(wf_b, p)
        print(f"  {label:<28} {va:>7.1f}min   {vb:>7.1f}min   {vb-va:>+8.1f}min")

    # --- Per-day free time --------------------------------------------------
    print(f"\n  MEAN FREE TIME PER CLASS-DAY (minutes, days with class only)")
    for day in DAY_ORDER:
        df_a = ex_agg["day_free"][day]
        df_b = pr_agg["day_free"][day]
        ma, mb = statistics.mean(df_a), statistics.mean(df_b)
        print(f"  {DAY_NAMES[day]:<28} {ma:>7.1f}min   {mb:>7.1f}min   {mb-ma:>+8.1f}min")

    # --- Back-to-back -------------------------------------------------------
    print(f"\n  BACK-TO-BACK CLASS PAIRS (zero gap between consecutive classes)")
    btb_a = ex_agg["weekly_btb"]
    btb_b = pr_agg["weekly_btb"]
    _stat_row("Mean per student", btb_a, btb_b, "")
    pa = 100 * sum(1 for v in btb_a if v > 0) / len(btb_a)
    pb = 100 * sum(1 for v in btb_b if v > 0) / len(btb_b)
    print(f"  {'Students with any B2B':<28} {pa:>7.1f}%   {pb:>7.1f}%   {pb-pa:>+8.1f}%")

    # --- Largest single gap -------------------------------------------------
    print(f"\n  LARGEST SINGLE FREE BLOCK (mid-day, on class days)")
    mg_a = ex_agg["max_gap"]
    mg_b = pr_agg["max_gap"]
    for label, fn in [("Mean", statistics.mean), ("Median", statistics.median)]:
        va, vb = fn(mg_a), fn(mg_b)
        print(f"  {label:<28} {va:>7.1f}min   {vb:>7.1f}min   {vb-va:>+8.1f}min")

    # --- Class-day spread ---------------------------------------------------
    print(f"\n  CLASS-DAY SPREAD (distinct days/week with at least one class)")
    cd_a = ex_agg["class_days"]
    cd_b = pr_agg["class_days"]
    _stat_row("Mean", cd_a, cd_b, "d")
    for d in (2, 3, 4, 5):
        pa = 100 * cd_a.count(d) / len(cd_a)
        pb = 100 * cd_b.count(d) / len(cd_b)
        print(f"  {'  '+str(d)+' days':<28} {pa:>7.1f}%   {pb:>7.1f}%   {pb-pa:>+8.1f}%")

    print("=" * W)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    existing_sched = Schedule.from_json(DATA_DIR / "existing_schedule.json")
    proposed_sched = Schedule.from_json(DATA_DIR / "proposed_schedule.json")

    ex_block = {b.name: b for b in existing_sched.time_blocks}
    pr_block = {b.name: b for b in proposed_sched.time_blocks}

    with open(DATA_DIR / "student_schedules_1500.json") as f:
        data = json.load(f)

    ex_raw = data["existing"]
    pr_raw = data["proposed"]

    ex_metrics = [_student_metrics(s["courses"], ex_block) for s in ex_raw["schedules"]]
    pr_metrics = [_student_metrics(s["courses"], pr_block) for s in pr_raw["schedules"]]

    ex_agg = _aggregate(ex_metrics)
    pr_agg = _aggregate(pr_metrics)

    report(ex_raw, pr_raw, ex_agg, pr_agg)


if __name__ == "__main__":
    main()
