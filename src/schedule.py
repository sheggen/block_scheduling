"""
Core data model and gap-analysis logic for block schedule comparison.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import time, timedelta
from pathlib import Path
from typing import Iterator

DAY_ORDER = ["M", "T", "W", "R", "F"]
DAY_NAMES = {"M": "Monday", "T": "Tuesday", "W": "Wednesday", "R": "Thursday", "F": "Friday"}


def _parse_time(t: str) -> time:
    """Parse 'HH:MM' (24-hour) into a time object."""
    h, m = t.split(":")
    return time(int(h), int(m))


def _gap_minutes(end: time, start: time) -> int:
    """Return the number of minutes between two times (start must be >= end)."""
    end_mins = end.hour * 60 + end.minute
    start_mins = start.hour * 60 + start.minute
    return max(0, start_mins - end_mins)


@dataclass
class TimeBlock:
    name: str
    days: list[str]
    start: time
    end: time

    @property
    def duration_minutes(self) -> int:
        return _gap_minutes(self.start, self.end)

    def __repr__(self) -> str:
        days_str = "/".join(self.days)
        return f"{self.name} ({days_str} {self.start.strftime('%H:%M')}-{self.end.strftime('%H:%M')})"


@dataclass
class Schedule:
    name: str
    time_blocks: list[TimeBlock] = field(default_factory=list)

    @classmethod
    def from_json(cls, path: str | Path) -> Schedule:
        data = json.loads(Path(path).read_text())
        blocks = [
            TimeBlock(
                name=b["name"],
                days=b["days"],
                start=_parse_time(b["start"]),
                end=_parse_time(b["end"]),
            )
            for b in data["time_blocks"]
        ]
        return cls(name=data["schedule_name"], time_blocks=blocks)

    def blocks_on_day(self, day: str) -> list[TimeBlock]:
        """Return all time blocks that meet on a given day, sorted by start time."""
        return sorted(
            [b for b in self.time_blocks if day in b.days],
            key=lambda b: b.start,
        )

    def gaps_on_day(self, day: str) -> list[int]:
        """
        Return a list of gap durations (in minutes) between consecutive blocks on a day.
        Overlapping blocks produce a gap of 0.
        """
        blocks = self.blocks_on_day(day)
        gaps = []
        for i in range(1, len(blocks)):
            gap = _gap_minutes(blocks[i - 1].end, blocks[i].start)
            gaps.append(gap)
        return gaps

    def all_gaps(self) -> dict[str, list[int]]:
        """Return gaps for every weekday keyed by day abbreviation."""
        return {day: self.gaps_on_day(day) for day in DAY_ORDER}

    def total_gap_minutes(self) -> int:
        """Sum of all gap minutes across the entire week."""
        return sum(g for gaps in self.all_gaps().values() for g in gaps)

    def weekly_gap_summary(self) -> Iterator[tuple[str, list[int], int]]:
        """Yield (day_name, gaps, total) for each weekday."""
        for day in DAY_ORDER:
            gaps = self.gaps_on_day(day)
            yield DAY_NAMES[day], gaps, sum(gaps)
