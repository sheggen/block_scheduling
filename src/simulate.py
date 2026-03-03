"""
Monte Carlo simulation of student schedules.

Assumptions:
- Students only attend classes between 7am and 6pm, Monday–Friday.
- Each student takes 3–5 classes, chosen randomly.
- Blocks overlapping 10am–2pm are weighted up to 3× more likely to be chosen.
- Blocks are chosen without conflict-checking; conflicting draws are counted
  separately and excluded from the gap analysis.
"""

from __future__ import annotations

import random
import statistics
from datetime import time
from typing import NamedTuple

from schedule import Schedule, TimeBlock, DAY_ORDER, DAY_NAMES

# Student availability window
STUDENT_DAY_START = time(7, 0)
STUDENT_DAY_END   = time(18, 0)

# Peak popularity window
PEAK_START = time(10, 0)
PEAK_END   = time(14, 0)
PEAK_WEIGHT_MULTIPLIER = 3.0   # fully-inside-peak blocks are 3× more likely


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mins(t: time) -> int:
    return t.hour * 60 + t.minute


def _eligible(block: TimeBlock) -> bool:
    """True if the block falls entirely within 7am–6pm on weekdays only."""
    weekdays = set(DAY_ORDER)
    if not all(d in weekdays for d in block.days):
        return False
    return block.start >= STUDENT_DAY_START and block.end <= STUDENT_DAY_END


def _block_weight(block: TimeBlock) -> float:
    """Weight based on overlap fraction with the 10am–2pm peak window."""
    overlap = max(
        0,
        min(_mins(block.end), _mins(PEAK_END)) - max(_mins(block.start), _mins(PEAK_START)),
    )
    if overlap == 0 or block.duration_minutes == 0:
        return 1.0
    ratio = overlap / block.duration_minutes
    return 1.0 + (PEAK_WEIGHT_MULTIPLIER - 1.0) * ratio


def _has_conflict(blocks: list[TimeBlock]) -> bool:
    """True if any two blocks share a day and their times overlap."""
    for i in range(len(blocks)):
        for j in range(i + 1, len(blocks)):
            a, b = blocks[i], blocks[j]
            if set(a.days) & set(b.days):
                if _mins(a.start) < _mins(b.end) and _mins(b.start) < _mins(a.end):
                    return True
    return False


def _pick_classes(pool: list[TimeBlock], weights: list[float], n: int) -> list[TimeBlock]:
    """Pick n blocks at random (with replacement disabled) using weights."""
    if len(pool) < n:
        return random.choices(pool, weights=weights, k=len(pool))
    indices = random.choices(range(len(pool)), weights=weights, k=n * 4)  # oversample to get unique
    seen: set[int] = set()
    chosen: list[TimeBlock] = []
    for idx in indices:
        if idx not in seen:
            seen.add(idx)
            chosen.append(pool[idx])
        if len(chosen) == n:
            break
    # Fall back if oversampling wasn't enough
    while len(chosen) < n:
        idx = random.choices(range(len(pool)), weights=weights, k=1)[0]
        if idx not in seen:
            seen.add(idx)
            chosen.append(pool[idx])
    return chosen


def _weekly_gap_minutes(student_blocks: list[TimeBlock]) -> dict[str, int]:
    """Total free-time minutes between consecutive classes per day."""
    result: dict[str, int] = {}
    for day in DAY_ORDER:
        day_blocks = sorted([b for b in student_blocks if day in b.days], key=lambda b: b.start)
        total = 0
        for i in range(1, len(day_blocks)):
            total += max(0, _mins(day_blocks[i].start) - _mins(day_blocks[i - 1].end))
        result[day] = total
    return result


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

class SimulationResult(NamedTuple):
    schedule_name: str
    n_attempts: int
    n_conflicts: int
    weekly_gaps: list[int]
    day_gaps: dict[str, list[int]]

    @property
    def n_valid(self) -> int:
        return self.n_attempts - self.n_conflicts

    @property
    def conflict_pct(self) -> float:
        return 100.0 * self.n_conflicts / self.n_attempts if self.n_attempts else 0.0


def run(schedule: Schedule, n: int = 10_000, seed: int | None = None) -> SimulationResult:
    if seed is not None:
        random.seed(seed)

    pool = [b for b in schedule.time_blocks if _eligible(b)]
    weights = [_block_weight(b) for b in pool]

    n_conflicts = 0
    weekly_gaps: list[int] = []
    day_gaps: dict[str, list[int]] = {day: [] for day in DAY_ORDER}

    for _ in range(n):
        n_classes = random.randint(3, 5)
        student = _pick_classes(pool, weights, n_classes)

        if _has_conflict(student):
            n_conflicts += 1
            continue  # excluded from gap analysis

        gaps = _weekly_gap_minutes(student)
        weekly_gaps.append(sum(gaps.values()))
        for day in DAY_ORDER:
            day_gaps[day].append(gaps[day])

    return SimulationResult(
        schedule_name=schedule.name,
        n_attempts=n,
        n_conflicts=n_conflicts,
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
    print(f"Simulation: {result.schedule_name}   n={result.n_attempts:,} attempts")
    print("=" * 70)

    print(f"\nEligible blocks : 7am–6pm, Mon–Fri only")
    print(f"Conflict check  : {result.n_conflicts:,} of {result.n_attempts:,} schedules had overlapping blocks "
          f"({result.conflict_pct:.1f}%) — excluded from analysis")
    print(f"Valid schedules : {result.n_valid:,}")

    if not wg:
        print("\n  No valid schedules to analyze.")
        print("=" * 70)
        return

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

    print(f"\nWeekly free time between classes  (valid schedules only)")
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
