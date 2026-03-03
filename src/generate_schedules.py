"""
Generate a 500-course mock schedule for the existing and proposed schedules.

Existing schedule: courses distributed by historical weights (F2016-F2020).
Proposed schedule: each existing block is mapped to the nearest proposed block
using a composite distance:
  - Day distance  : +50 per day that is present in one block but not the other
  - Time distance : absolute difference in block midpoints (minutes)
  - Duration distance: |normalized_duration_A - normalized_duration_B| * 0.5

Duration equivalences (treated as zero distance):
  - 50min (proposed) == 70min (existing)
  - 110min (existing) == 100min or 140min (proposed)
  - 120+min (existing) == 170min (proposed)
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from schedule import Schedule, TimeBlock
from simulate import HISTORICAL_WEIGHTS

TARGET      = 500
DATA_DIR    = Path(__file__).parent.parent / "data"
EXISTING_JSON  = DATA_DIR / "existing_schedule.json"
PROPOSED_JSON  = DATA_DIR / "proposed_schedule.json"
OUT_EXISTING   = DATA_DIR / "schedule_existing_500.json"
OUT_PROPOSED   = DATA_DIR / "schedule_proposed_500.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mins(t) -> int:
    return t.hour * 60 + t.minute


def _midpoint(b: TimeBlock) -> float:
    return (_mins(b.start) + _mins(b.end)) / 2.0


def _duration(b: TimeBlock) -> int:
    return _mins(b.end) - _mins(b.start)


def _dur_class(minutes: int) -> int:
    """Normalize duration into an equivalence class (in canonical minutes)."""
    if minutes in (50, 70):
        return 60       # 50min (proposed) == 70min (existing)
    if minutes in (100, 110, 140):
        return 120      # 110min (existing) == 100min or 140min (proposed)
    if minutes >= 120:
        return 170      # 120+min (existing) == 170min (proposed)
    return minutes


def _block_distance(a: TimeBlock, b: TimeBlock) -> float:
    """Lower is better."""
    day_set_a = set(a.days)
    day_set_b = set(b.days)
    day_dist  = len(day_set_a.symmetric_difference(day_set_b)) * 50
    time_dist = abs(_midpoint(a) - _midpoint(b))
    dur_dist  = abs(_dur_class(_duration(a)) - _dur_class(_duration(b))) * 0.5
    return day_dist + time_dist + dur_dist


def _nearest(block: TimeBlock, candidates: list[TimeBlock]) -> TimeBlock:
    return min(candidates, key=lambda c: _block_distance(block, c))


def _allocate(weights: dict[str, float], total: int) -> dict[str, int]:
    """Largest-remainder allocation to exactly hit `total`."""
    raw      = {k: total * v / sum(weights.values()) for k, v in weights.items()}
    floored  = {k: math.floor(v) for k, v in raw.items()}
    deficit  = total - sum(floored.values())
    fracs    = sorted(raw.items(), key=lambda x: -(x[1] - math.floor(x[1])))
    result   = dict(floored)
    for name, _ in fracs[:deficit]:
        result[name] += 1
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    existing = Schedule.from_json(EXISTING_JSON)
    proposed = Schedule.from_json(PROPOSED_JSON)

    # --- Existing schedule allocation (historical weights) -------------------
    # Only blocks that appear in historical data get weight; others get 0.
    existing_weights = {
        b.name: HISTORICAL_WEIGHTS.get(b.name, 0)
        for b in existing.time_blocks
    }
    # Drop blocks with 0 historical courses
    existing_weights = {k: v for k, v in existing_weights.items() if v > 0}
    existing_alloc = _allocate(existing_weights, TARGET)

    # --- Build nearest-block mapping -----------------------------------------
    existing_by_name = {b.name: b for b in existing.time_blocks}
    mapping: dict[str, str] = {}
    for name in existing_alloc:
        src = existing_by_name[name]
        nearest = _nearest(src, proposed.time_blocks)
        mapping[name] = nearest.name

    # --- Proposed schedule allocation (via mapping) --------------------------
    proposed_alloc: dict[str, int] = {}
    for src_name, count in existing_alloc.items():
        dest_name = mapping[src_name]
        proposed_alloc[dest_name] = proposed_alloc.get(dest_name, 0) + count

    # --- Print mapping table -------------------------------------------------
    print("=" * 90)
    print(f"Block mapping: existing → proposed  (distance = day_dist + time_dist + 0.5*dur_dist)")
    print("=" * 90)
    print(f"{'Existing block':<40} {'Courses':>7}  {'Proposed block':<35} {'Dist':>6}")
    print(f"{'-'*40} {'-'*7}  {'-'*35} {'-'*6}")
    for src_name, count in sorted(existing_alloc.items(), key=lambda x: -x[1]):
        dest_name = mapping[src_name]
        src  = existing_by_name[src_name]
        dest = next(b for b in proposed.time_blocks if b.name == dest_name)
        dist = _block_distance(src, dest)
        print(f"{src_name:<40} {count:>7}  {dest_name:<35} {dist:>6.1f}")

    # --- Print proposed distribution -----------------------------------------
    print()
    print("=" * 70)
    print(f"Proposed schedule — 500-course distribution")
    print("=" * 70)
    print(f"{'Proposed block':<35} {'Courses':>8}  {'% of total':>10}")
    print(f"{'-'*35} {'-'*8}  {'-'*10}")
    for name, count in sorted(proposed_alloc.items(), key=lambda x: -x[1]):
        print(f"{name:<35} {count:>8}  {100*count/TARGET:>9.1f}%")
    print(f"\n{'TOTAL':<35} {sum(proposed_alloc.values()):>8}")

    # --- Save JSON files -----------------------------------------------------
    def _save(path: Path, alloc: dict[str, int], label: str) -> None:
        data = {
            "total_courses": TARGET,
            "source": label,
            "courses_by_block": {
                k: v for k, v in sorted(alloc.items(), key=lambda x: -x[1])
            },
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\nSaved → {path}")

    _save(OUT_EXISTING, existing_alloc,
          "Historical weights F2016-F2020, scaled to 500")
    _save(OUT_PROPOSED, proposed_alloc,
          "Mapped from existing schedule via nearest-block distance")


if __name__ == "__main__":
    main()
