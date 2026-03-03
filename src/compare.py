"""
Side-by-side comparison of two schedules.
"""

from __future__ import annotations

from datetime import time

from schedule import Schedule, DAY_ORDER, DAY_NAMES


def _mins(t: time) -> int:
    return t.hour * 60 + t.minute


def _day_gap_total(schedule: Schedule, day: str) -> int:
    blocks = sorted(
        [b for b in schedule.time_blocks if day in b.days],
        key=lambda b: (b.start, b.end),
    )
    total = 0
    for i in range(len(blocks) - 1):
        gap = max(0, _mins(blocks[i + 1].start) - _mins(blocks[i].end))
        total += gap
    return total


def compare(existing: Schedule, proposed: Schedule) -> None:
    print("=" * 70)
    print(f"Comparison: {existing.name}  vs.  {proposed.name}")
    print("=" * 70)

    print(f"\n{'Day':<12} {'Existing':>12} {'Proposed':>12} {'Delta':>10}")
    print(f"{'-'*12} {'-'*12} {'-'*12} {'-'*10}")

    weekly_existing = 0
    weekly_proposed = 0

    for day in DAY_ORDER:
        eg = _day_gap_total(existing, day)
        pg = _day_gap_total(proposed, day)
        delta = pg - eg
        sign = '+' if delta > 0 else ''
        print(f"{DAY_NAMES[day]:<12} {eg:>10} min {pg:>10} min {sign}{delta:>7} min")
        weekly_existing += eg
        weekly_proposed += pg

    delta = weekly_proposed - weekly_existing
    sign = '+' if delta > 0 else ''
    print(f"\n{'Weekly':<12} {weekly_existing:>10} min {weekly_proposed:>10} min {sign}{delta:>7} min")
    print("=" * 70)
