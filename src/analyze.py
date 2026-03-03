"""
Single-schedule gap analysis: prints a table of blocks per day and total
free time (gaps between consecutive block offerings).
"""

from __future__ import annotations

from datetime import time

from schedule import Schedule, TimeBlock, DAY_ORDER, DAY_NAMES


def _mins(t: time) -> int:
    return t.hour * 60 + t.minute


def _fmt_time(t: time) -> str:
    return t.strftime('%H:%M')


def _gap_minutes(end: time, start: time) -> int:
    return max(0, _mins(start) - _mins(end))


def analyze(schedule: Schedule) -> None:
    print("=" * 70)
    print(f"Gap Analysis: {schedule.name}")
    print("=" * 70)

    weekly_total = 0

    for day in DAY_ORDER:
        blocks = sorted(
            [b for b in schedule.time_blocks if day in b.days],
            key=lambda b: (b.start, b.end),
        )
        if not blocks:
            continue

        print(f"\n{DAY_NAMES[day]}")
        print(f"   {'Start':>5}   {'End':>5}   {'Gap after':>10}  Block")
        print(f"   {'------':>5}   {'------':>5}   {'----------':>10}  {'-'*40}")

        day_total = 0
        for i, blk in enumerate(blocks):
            if i + 1 < len(blocks):
                gap = _gap_minutes(blk.end, blocks[i + 1].start)
                gap_str = f"{gap:>6} min" if gap > 0 else f"{'—':>10}"
                if gap > 0:
                    day_total += gap
            else:
                gap_str = f"{'—':>10}"
            print(f"   {_fmt_time(blk.start):>5}   {_fmt_time(blk.end):>5}   {gap_str}  {blk.name}")

        print(f"\n  Day total free time: {day_total} min  ({day_total // 60}h {day_total % 60}m)")
        weekly_total += day_total

    print()
    print("=" * 70)
    print(f"Weekly total free time between classes: {weekly_total} min  ({weekly_total // 60}h {weekly_total % 60}m)")
    print("=" * 70)
