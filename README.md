# block_scheduling

A Python toolkit for analyzing and comparing course block schedules at the college level. It provides three modes of analysis:

1. **Gap analysis** — for a given schedule, shows the free-time gaps between consecutive blocks on each day of the week.
2. **Monte Carlo simulation** — simulates 10,000 student schedules drawn from the block pool (weighted by historical enrollment data) and reports free-time distributions, conflict rates, and weekly contact hours.
3. **Schedule comparison** — places two schedules side by side and shows how gap time changes day-by-day and weekly.

An optional chart generator (`src/charts.py`) produces a multi-panel PNG summarizing the simulation results.

---

## Project structure

```
block_scheduling/
├── main.py                   # Entry point — runs all analyses
├── data/
│   ├── existing_schedule.json  # Current block schedule
│   └── proposed_schedule.json  # Proposed/alternative schedule (optional)
├── src/
│   ├── schedule.py           # Data model: Schedule and TimeBlock
│   ├── analyze.py            # Single-schedule gap analysis report
│   ├── simulate.py           # Monte Carlo simulation + text report
│   ├── compare.py            # Side-by-side schedule comparison
│   └── charts.py             # Matplotlib chart generator (optional)
└── .venv/                    # Python virtual environment
```

---

## Setup

**Requirements:** Python 3.11+

```bash
# Create and activate the virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies (only needed for charts.py)
pip install matplotlib
```

---

## Running

```bash
# Activate the virtual environment first
source .venv/bin/activate

# Run gap analysis + simulation (and comparison if proposed_schedule.json has blocks)
python main.py

# Generate charts (saves charts.png in the project root)
python src/charts.py
```

---

## What the output shows

### Gap analysis
A per-day table of block start/end times and the free-time gap after each block, plus a daily and weekly total.

### Monte Carlo simulation
Simulates 10,000 students each taking 3–5 courses, selected at random from the block pool. Block selection is **weighted by historical course counts** aggregated from Fall 2016–Fall 2020 (sourced from the CAS scheduling database).

- **Student workday window:** 8am–5pm, Mon–Fri. Evening blocks (ending after 5pm) are included in the pool with their historical weights (~6.4% of all courses).
- **Conflict detection:** schedules with overlapping blocks are counted and excluded from the free-time analysis.
- Reports mean/median/p25/p75 free time per day, weekly free-time distribution, and weekly contact hours broken down by 3-, 4-, and 5-course loads.

### Schedule comparison
A table showing free-time minutes for each day of the week under the existing and proposed schedules, with the delta highlighted.

---

## Schedule data format

Schedules are defined as JSON files in `data/`. Each file follows this structure:

```json
{
  "name": "Schedule Name",
  "time_blocks": [
    {
      "name": "MWF Standard A",
      "days": ["M", "W", "F"],
      "start": "08:00",
      "end": "09:10"
    }
  ]
}
```

- `days` uses single-letter codes: `M` Mon, `T` Tue, `W` Wed, `R` Thu, `F` Fri.
- `start` and `end` are 24-hour `HH:MM` strings.

To analyze a proposed schedule, populate `data/proposed_schedule.json` with the same format. If it contains no blocks, the comparison step is skipped.
