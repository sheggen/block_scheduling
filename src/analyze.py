"""
Single-schedule gap analysis report.
"""

from __future__ import annotations

from schedule import Schedule, DAY_ORDER, DAY_NAMES


def analyze(schedule: Schedule) -> None:
    print("=" * 70)
    print(f"Gap Analysis: {schedule.name}")
    print("=" * 70)

    week_total = 0

    for day in DAY_ORDER:
        blocks = schedule.blocks_on_day(day)
        if not blocks:
            continue

        day_total = 0
        print(f"\n{DAY_NAMES[day]}")
        print(f"  {'Start':>6}  {'End':>6}  {'Gap after':>10}  Block")
        print(f"  {'-'*6}  {'-'*6}  {'-'*10}  {'-'*40}")

        for i, block in enumerate(blocks):
            if i < len(blocks) - 1:
                gap = _gap(block.end, blocks[i + 1].start)
                day_total += gap
                gap_str = f"{gap:>7} min" if gap > 0 else f"{'—':>10}"
            else:
                gap_str = f"{'—':>10}"

            print(
                f"  {block.start.strftime('%H:%M'):>6}  "
                f"{block.end.strftime('%H:%M'):>6}  "
                f"{gap_str:>10}  "
                f"{block.name}"
            )

        print(f"\n  Day total free time: {day_total} min  ({day_total // 60}h {day_total % 60}m)")
        week_total += day_total

    print("\n" + "=" * 70)
    print(f"Weekly total free time between classes: {week_total} min  ({week_total // 60}h {week_total % 60}m)")
    print("=" * 70)


def _gap(end, start) -> int:
    return max(0, (start.hour * 60 + start.minute) - (end.hour * 60 + end.minute))
