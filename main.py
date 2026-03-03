"""
Entry point for the block schedule comparison tool.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from schedule import Schedule
from analyze import analyze
from compare import compare
from simulate import run, report as sim_report

EXISTING = Path("data/existing_schedule.json")
PROPOSED = Path("data/proposed_schedule.json")
SIM_N = 10_000
SIM_SEED = 42


def main() -> None:
    existing = Schedule.from_json(EXISTING)
    proposed = Schedule.from_json(PROPOSED)

    analyze(existing)
    print()
    sim_report(run(existing, n=SIM_N, seed=SIM_SEED))

    if proposed.time_blocks:
        print()
        analyze(proposed)
        print()
        sim_report(run(proposed, n=SIM_N, seed=SIM_SEED))
        print()
        compare(existing, proposed)


if __name__ == "__main__":
    main()
