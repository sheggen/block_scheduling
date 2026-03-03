"""
Core data model: Schedule and TimeBlock.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path

DAY_ORDER = ['M', 'T', 'W', 'R', 'F']
DAY_NAMES = {'M': 'Monday', 'T': 'Tuesday', 'W': 'Wednesday', 'R': 'Thursday', 'F': 'Friday'}


@dataclass
class TimeBlock:
    name: str
    days: list[str]
    start: time
    end: time

    @property
    def duration_minutes(self) -> int:
        return (self.end.hour * 60 + self.end.minute) - (self.start.hour * 60 + self.start.minute)

    @classmethod
    def from_dict(cls, d: dict) -> TimeBlock:
        return cls(
            name=d['name'],
            days=d['days'],
            start=time.fromisoformat(d['start']),
            end=time.fromisoformat(d['end']),
        )


@dataclass
class Schedule:
    name: str
    time_blocks: list[TimeBlock] = field(default_factory=list)

    @classmethod
    def from_json(cls, path: Path) -> Schedule:
        with open(path) as f:
            data = json.load(f)
        return cls(
            name=data['name'],
            time_blocks=[TimeBlock.from_dict(b) for b in data.get('time_blocks', [])],
        )
