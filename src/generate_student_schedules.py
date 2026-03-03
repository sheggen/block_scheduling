"""
Generate 1,500 non-conflicting student schedules (4–6 classes each) from
the 500-course pool, for both the existing and proposed schedule.

Selection weights
-----------------
Each course is weighted by the historical course count of its time block
(HISTORICAL_WEIGHTS from simulate.py).  For the proposed schedule, courses
inherit the historical weight of the *source* block they were mapped from in
generate_schedules.py, so the sampling distribution stays anchored to real
observed demand.

Conflict rule
-------------
Two courses conflict when they share at least one calendar day AND their
time ranges overlap (start_A < end_B and start_B < end_A).  Two courses
assigned to the *same* time block always conflict.

Process
-------
Keep drawing random 3–5 course combinations until 1,500 conflict-free
student schedules are accumulated.  Every conflicting draw is counted but
discarded.

Outputs
-------
  console  — summary table comparing existing vs proposed
  data/student_schedules_1500.json  — full per-student course lists + stats
"""

from __future__ import annotations

import json
import math
import random
import sys
from dataclasses import dataclass
from datetime import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from schedule import Schedule, TimeBlock
from simulate import HISTORICAL_WEIGHTS

TARGET_VALID = 1_500
SEED = 42
DATA_DIR = Path(__file__).parent.parent / "data"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Course:
    course_id: int          # 1-based within the pool
    block_name: str
    time_block: TimeBlock
    weight: float           # sampling weight (historical block usage)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mins(t: time) -> int:
    return t.hour * 60 + t.minute


def _has_conflict(courses: list[Course]) -> bool:
    """True if any two courses share a day and their times overlap."""
    for i in range(len(courses)):
        for j in range(i + 1, len(courses)):
            a, b = courses[i].time_block, courses[j].time_block
            if set(a.days) & set(b.days):
                if _mins(a.start) < _mins(b.end) and _mins(b.start) < _mins(a.end):
                    return True
    return False


def _build_mapping(existing: Schedule, proposed: Schedule) -> dict[str, str]:
    """Replicate the nearest-block mapping from generate_schedules.py."""
    def midpoint(b: TimeBlock) -> float:
        return (_mins(b.start) + _mins(b.end)) / 2.0

    def duration(b: TimeBlock) -> int:
        return _mins(b.end) - _mins(b.start)

    def dur_class(minutes: int) -> int:
        if minutes in (50, 70):
            return 60
        if minutes in (100, 110, 140):
            return 120
        if minutes >= 120:
            return 170
        return minutes

    def distance(a: TimeBlock, b: TimeBlock) -> float:
        day_dist = len(set(a.days).symmetric_difference(set(b.days))) * 50
        time_dist = abs(midpoint(a) - midpoint(b))
        dur_dist = abs(dur_class(duration(a)) - dur_class(duration(b))) * 0.5
        return day_dist + time_dist + dur_dist

    existing_by_name = {b.name: b for b in existing.time_blocks}
    mapping: dict[str, str] = {}
    for src_name in HISTORICAL_WEIGHTS:
        if src_name in existing_by_name:
            src = existing_by_name[src_name]
            mapping[src_name] = min(proposed.time_blocks, key=lambda c: distance(src, c)).name
    return mapping


def build_existing_pool(schedule: Schedule, distribution: dict[str, int]) -> list[Course]:
    """500 Course objects for the existing schedule."""
    block_by_name = {b.name: b for b in schedule.time_blocks}
    courses: list[Course] = []
    cid = 1
    for block_name, count in distribution.items():
        if block_name not in block_by_name or count == 0:
            continue
        tb = block_by_name[block_name]
        w  = HISTORICAL_WEIGHTS.get(block_name, 1.0)
        for _ in range(count):
            courses.append(Course(cid, block_name, tb, w))
            cid += 1
    return courses


def build_proposed_pool(
    existing: Schedule,
    proposed: Schedule,
    existing_dist: dict[str, int],
    mapping: dict[str, str],
) -> list[Course]:
    """500 Course objects for the proposed schedule.

    Each proposed course inherits the historical weight of the *source* block
    it was mapped from, so the sampling distribution reflects real demand.
    """
    proposed_by_name = {b.name: b for b in proposed.time_blocks}
    courses: list[Course] = []
    cid = 1
    for src_name, count in existing_dist.items():
        if count == 0:
            continue
        dest_name = mapping.get(src_name)
        if dest_name is None or dest_name not in proposed_by_name:
            continue
        tb = proposed_by_name[dest_name]
        w  = HISTORICAL_WEIGHTS.get(src_name, 1.0)
        for _ in range(count):
            courses.append(Course(cid, dest_name, tb, w))
            cid += 1
    return courses


# ---------------------------------------------------------------------------
# Schedule generator
# ---------------------------------------------------------------------------

def generate(
    pool: list[Course],
    target: int = TARGET_VALID,
    seed: int = SEED,
) -> tuple[list[list[Course]], int]:
    """Return (valid_schedules, n_conflicts)."""
    rng = random.Random(seed)
    weights = [c.weight for c in pool]
    idx_range = range(len(pool))

    valid: list[list[Course]] = []
    n_conflicts = 0

    while len(valid) < target:
        n_classes = rng.randint(4, 6)

        # Draw unique indices via weighted sampling with oversampling
        seen: set[int] = set()
        chosen_idx: list[int] = []
        candidates = rng.choices(idx_range, weights=weights, k=n_classes * 6)
        for idx in candidates:
            if idx not in seen:
                seen.add(idx)
                chosen_idx.append(idx)
            if len(chosen_idx) == n_classes:
                break
        # Fallback if oversampling fell short (very rare)
        while len(chosen_idx) < n_classes:
            idx = rng.choices(idx_range, weights=weights, k=1)[0]
            if idx not in seen:
                seen.add(idx)
                chosen_idx.append(idx)

        chosen = [pool[i] for i in chosen_idx]
        if _has_conflict(chosen):
            n_conflicts += 1
        else:
            valid.append(chosen)

    return valid, n_conflicts


# ---------------------------------------------------------------------------
# Summary helpers
# ---------------------------------------------------------------------------

def _block_usage(schedules: list[list[Course]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for sched in schedules:
        for c in sched:
            counts[c.block_name] = counts.get(c.block_name, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


def _load_dist(schedules: list[list[Course]]) -> dict[int, int]:
    dist: dict[int, int] = {4: 0, 5: 0, 6: 0}
    for s in schedules:
        dist[len(s)] = dist.get(len(s), 0) + 1
    return dist


def _print_comparison(label_a: str, ra: dict, label_b: str, rb: dict) -> None:
    print("=" * 72)
    print(f"Student schedule generation  (target: {TARGET_VALID:,} valid per schedule)")
    print("=" * 72)
    print(f"{'Metric':<30} {label_a:>18} {label_b:>18}")
    print(f"{'-'*30} {'-'*18} {'-'*18}")

    def row(label, a, b, fmt="{:>18}"):
        print(f"{label:<30} {fmt.format(a)} {fmt.format(b)}")

    row("Attempts",      f"{ra['n_attempts']:,}",   f"{rb['n_attempts']:,}")
    row("Conflicts",     f"{ra['n_conflicts']:,}",  f"{rb['n_conflicts']:,}")
    row("Conflict rate", f"{ra['conflict_pct']:.2f}%", f"{rb['conflict_pct']:.2f}%")
    row("Valid",         f"{ra['n_valid']:,}",      f"{rb['n_valid']:,}")

    print()
    print(f"{'Class load':<30} {label_a:>18} {label_b:>18}")
    print(f"{'-'*30} {'-'*18} {'-'*18}")
    for n in (4, 5, 6):
        pct_a = 100 * ra['class_load'][str(n)] / TARGET_VALID
        pct_b = 100 * rb['class_load'][str(n)] / TARGET_VALID
        row(f"  {n} classes",
            f"{ra['class_load'][str(n)]:,} ({pct_a:.1f}%)",
            f"{rb['class_load'][str(n)]:,} ({pct_b:.1f}%)")

    print()
    print(f"Top-10 block usage (across all 1,500 valid student schedules)")
    print(f"{'Block':<35} {label_a:>15} {label_b:>15}")
    print(f"{'-'*35} {'-'*15} {'-'*15}")
    blocks_a = ra['block_usage']
    blocks_b = rb['block_usage']
    all_blocks = list(dict.fromkeys(list(blocks_a)[:10] + list(blocks_b)[:10]))[:14]
    for blk in all_blocks:
        cnt_a = blocks_a.get(blk, 0)
        cnt_b = blocks_b.get(blk, 0)
        print(f"  {blk:<33} {cnt_a:>7,} ({100*cnt_a/sum(blocks_a.values()):4.1f}%)"
              f"  {cnt_b:>7,} ({100*cnt_b/sum(blocks_b.values()):4.1f}%)")
    print("=" * 72)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    existing_sched = Schedule.from_json(DATA_DIR / "existing_schedule.json")
    proposed_sched = Schedule.from_json(DATA_DIR / "proposed_schedule.json")

    with open(DATA_DIR / "schedule_existing_500.json") as f:
        existing_dist: dict[str, int] = json.load(f)["courses_by_block"]
    with open(DATA_DIR / "schedule_proposed_500.json") as f:
        proposed_dist: dict[str, int] = json.load(f)["courses_by_block"]

    mapping = _build_mapping(existing_sched, proposed_sched)

    # Build course pools
    existing_pool = build_existing_pool(existing_sched, existing_dist)
    proposed_pool = build_proposed_pool(existing_sched, proposed_sched, existing_dist, mapping)

    assert len(existing_pool) == 500, f"Expected 500 existing courses, got {len(existing_pool)}"
    assert len(proposed_pool) == 500, f"Expected 500 proposed courses, got {len(proposed_pool)}"

    # Generate schedules
    print("Generating existing student schedules …")
    ex_schedules, ex_conflicts = generate(existing_pool, TARGET_VALID, seed=SEED)
    print("Generating proposed student schedules …")
    pr_schedules, pr_conflicts = generate(proposed_pool, TARGET_VALID, seed=SEED)

    def _summarize(schedules: list[list[Course]], n_conflicts: int) -> dict:
        n_attempts = TARGET_VALID + n_conflicts
        load = _load_dist(schedules)
        return {
            "n_attempts":   n_attempts,
            "n_conflicts":  n_conflicts,
            "conflict_pct": round(100.0 * n_conflicts / n_attempts, 4),
            "n_valid":      TARGET_VALID,
            "class_load":   {str(k): v for k, v in load.items()},
            "block_usage":  _block_usage(schedules),
            "schedules": [
                {
                    "student_id": i + 1,
                    "n_classes":  len(s),
                    "courses": [
                        {"course_id": c.course_id, "block": c.block_name}
                        for c in s
                    ],
                }
                for i, s in enumerate(schedules)
            ],
        }

    results = {
        "existing": _summarize(ex_schedules, ex_conflicts),
        "proposed": _summarize(pr_schedules, pr_conflicts),
    }

    # Console summary
    print()
    _print_comparison(
        "Existing", results["existing"],
        "Proposed", results["proposed"],
    )

    # Save
    out_path = DATA_DIR / "student_schedules_1500.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved → {out_path}")


if __name__ == "__main__":
    main()
