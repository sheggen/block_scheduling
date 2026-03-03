"""
Comparison report between two schedules.
"""

from __future__ import annotations

from schedule import Schedule, DAY_ORDER, DAY_NAMES


def compare(existing: Schedule, proposed: Schedule) -> None:
    print("=" * 60)
    print(f"Schedule Comparison")
    print(f"  Existing : {existing.name}")
    print(f"  Proposed : {proposed.name}")
    print("=" * 60)

    for day in DAY_ORDER:
        day_name = DAY_NAMES[day]
        e_gaps = existing.gaps_on_day(day)
        p_gaps = proposed.gaps_on_day(day)
        e_total = sum(e_gaps)
        p_total = sum(p_gaps)

        print(f"\n{day_name}")
        print(f"  Existing  gaps (min): {e_gaps}  → total {e_total} min")
        print(f"  Proposed  gaps (min): {p_gaps}  → total {p_total} min")
        diff = p_total - e_total
        if diff > 0:
            print(f"  Proposed gives {diff} more minutes of free time")
        elif diff < 0:
            print(f"  Existing gives {-diff} more minutes of free time")
        else:
            print(f"  No difference")

    e_week = existing.total_gap_minutes()
    p_week = proposed.total_gap_minutes()
    diff = p_week - e_week

    print("\n" + "=" * 60)
    print(f"Weekly totals")
    print(f"  Existing : {e_week} minutes of free time between classes")
    print(f"  Proposed : {p_week} minutes of free time between classes")
    if diff > 0:
        print(f"\n  → Proposed schedule gives students {diff} more minutes per week.")
    elif diff < 0:
        print(f"\n  → Existing schedule gives students {-diff} more minutes per week.")
    else:
        print(f"\n  → Both schedules give students equal free time.")
    print("=" * 60)
