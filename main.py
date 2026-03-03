"""
Entry point for the block schedule comparison tool.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from schedule import Schedule
from analyze import analyze
from compare import compare

EXISTING = Path("data/existing_schedule.json")
PROPOSED = Path("data/proposed_schedule.json")


def main() -> None:
    existing = Schedule.from_json(EXISTING)
    proposed = Schedule.from_json(PROPOSED)

    analyze(existing)

    if proposed.time_blocks:
        print()
        analyze(proposed)
        print()
        compare(existing, proposed)


if __name__ == "__main__":
    main()
