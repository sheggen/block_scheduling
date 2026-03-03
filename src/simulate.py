"""
Monte Carlo simulation of student schedules.

Each simulated student picks 3–5 classes from the schedule, with blocks
overlapping the 10am–2pm window weighted more heavily. Free time between
classes is measured for each student and aggregated across all simulations.
"""

from __future__ import annotations

import random
import statistics
from datetime import time
from typing import NamedTuple

from schedule import Schedule, TimeBlock, DAY_ORDER, DAY_NAMES

PEAK_START = time(10, 0)
PEAK_END   = time(14, 0)
PEAK_WEIGHT_MULTIPLIER = 3.0   # blocks fully inside peak window are 3× more likely


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mins(t: time) -> int:
    return t.hour * 60 + t.minute


def _block_weight(block: TimeBlock) -> float:
    """
    Return a selection weight for a block based on its overlap with 10am–2pm.
    Fully outside peak → 1.0.  Fully inside peak → PEAK_WEIGHT_MULTIPLIER.
    """
    overlap = max(0, min(_mins(block.end), _mins(PEAK_END)) - max(_mins(block.start), _mins(PEAK_START)))
    if overlap == 0 or block.duration_minutes == 0:
        return 1.0
    ratio = overlap / block.duration_minutes
    return 1.0 + (PEAK_WEIGHT_MULTIPLIER - 1.0) * ratio


def _conflict(a: TimeBlock, b: TimeBlock) -> bool:
    """True if two blocks share a day and their times overlap."""
    if not (set(a.days) & set(b.days)):
        return False
    return _mins(a.start) < _mins(b.end) and _mins(b.start) < _mins(a.end)


def _pick_classes(blocks: list[TimeBlock], n: int) -> list[TimeBlock]:
    """
    Greedily pick n non-conflicting blocks using weighted random selection.
    Returns fewer than n if the schedule doesn't have enough compatible slots.
    """
    weights = [_block_weight(b) for b in blocks]
    available = list(range(len(blocks)))
    chosen: list[TimeBlock] = []

    while len(chosen) < n and available:
        avail_w = [weights[i] for i in available]
        pick = random.choices(available, weights=avail_w, k=1)[0]
        chosen.append(blocks[pick])
        available = [i for i in available if i != pick and not _conflict(blocks[i], blocks[pick])]

    return chosen


def _weekly_gap_minutes(student_blocks: list[TimeBlock]) -> dict[str, int]:
    """Return total free-time minutes between classes for each weekday."""
    result: dict[str, int] = {}
    for day in DAY_ORDER:
        day_blocks = sorted([b for b in student_blocks if day in b.days], key=lambda b: b.start)
        total = 0
        for i in range(1, len(day_blocks)):
            gap = max(0, _mins(day_blocks[i].start) - _mins(day_blocks[i - 1].end))
            total += gap
        result[day] = total
    return result


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

class SimulationResult(NamedTuple):
    schedule_name: str
    n: int
    weekly_gaps: list[int]
    day_gaps: dict[str, list[int]]   # day → list of per-student totals


def run(schedule: Schedule, n: int = 10_000, seed: int | None = None) -> SimulationResult:
    if seed is not None:
        random.seed(seed)

    weekly_gaps: list[int] = []
    day_gaps: dict[str, list[int]] = {day: [] for day in DAY_ORDER}

    for _ in range(n):
        n_classes = random.randint(3, 5)
        student = _pick_classes(schedule.time_blocks, n_classes)
        gaps = _weekly_gap_minutes(student)
        weekly_gaps.append(sum(gaps.values()))
        for day in DAY_ORDER:
            day_gaps[day].append(gaps[day])

    return SimulationResult(
        schedule_name=schedule.name,
        n=n,
        weekly_gaps=weekly_gaps,
        day_gaps=day_gaps,
    )


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _pct(data: list[int], p: float) -> float:
    sd = sorted(data)
    k = (len(sd) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(sd) - 1)
    return sd[lo] + (k - lo) * (sd[hi] - sd[lo])


def _histogram(data: list[int], bins: int = 10, bar_width: int = 36) -> None:
    lo, hi = min(data), max(data)
    size = max(1, (hi - lo + 1) // bins)
    counts = [0] * bins
    for v in data:
        counts[min(bins - 1, (v - lo) // size)] += 1
    max_c = max(counts)
    for i, c in enumerate(counts):
        lo_label = lo + i * size
        hi_label = lo_label + size - 1
        bar = "█" * round(c / max_c * bar_width)
        pct_str = f"{100 * c / len(data):4.1f}%"
        print(f"  {lo_label:>4}–{hi_label:<4} {bar:<{bar_width}} {pct_str}  ({c:,})")


def report(result: SimulationResult) -> None:
    wg = result.weekly_gaps
    print("=" * 70)
    print(f"Simulation: {result.schedule_name}   n={result.n:,} students")
    print("=" * 70)

    print(f"\n{'Day':<12} {'Mean':>8} {'Median':>8} {'p25':>6} {'p75':>6} {'Max':>6}")
    print(f"{'-'*12} {'-'*8} {'-'*8} {'-'*6} {'-'*6} {'-'*6}")
    for day in DAY_ORDER:
        dg = result.day_gaps[day]
        print(
            f"{DAY_NAMES[day]:<12} "
            f"{statistics.mean(dg):>7.1f}m "
            f"{statistics.median(dg):>7.1f}m "
            f"{_pct(dg, 25):>5.0f}m "
            f"{_pct(dg, 75):>5.0f}m "
            f"{max(dg):>5}m"
        )

    print(f"\nWeekly free time between classes")
    print(f"  Mean      {statistics.mean(wg):>7.1f} min  ({statistics.mean(wg)/60:.1f}h)")
    print(f"  Median    {statistics.median(wg):>7.1f} min  ({statistics.median(wg)/60:.1f}h)")
    print(f"  Std dev   {statistics.stdev(wg):>7.1f} min")
    print(f"  p25       {_pct(wg, 25):>7.1f} min")
    print(f"  p75       {_pct(wg, 75):>7.1f} min")
    print(f"  Min       {min(wg):>7} min")
    print(f"  Max       {max(wg):>7} min")

    print(f"\nDistribution of weekly free time (minutes)")
    _histogram(wg)
    print("=" * 70)
