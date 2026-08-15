"""Deterministic virtual clock.

Compresses weeks of business time into seconds of wall time. Every run with the
same seed produces the same timeline, which is what makes simulation runs usable
as regression tests rather than one-off demos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


# A small clinic's working week. Arrival modelling keys off these.
DEFAULT_OPEN_HOUR = 8
DEFAULT_CLOSE_HOUR = 17
DEFAULT_WORKDAYS = frozenset({0, 1, 2, 3, 4})  # Monday..Friday


@dataclass
class SimClock:
    """Virtual time with business-hours awareness."""

    start: datetime
    now: datetime = field(init=False)
    open_hour: int = DEFAULT_OPEN_HOUR
    close_hour: int = DEFAULT_CLOSE_HOUR
    workdays: frozenset[int] = DEFAULT_WORKDAYS

    def __post_init__(self) -> None:
        if self.start.tzinfo is None:
            self.start = self.start.replace(tzinfo=timezone.utc)
        self.now = self.start

    def advance(self, seconds: float) -> datetime:
        self.now = self.now + timedelta(seconds=seconds)
        return self.now

    def advance_to(self, moment: datetime) -> datetime:
        if moment < self.now:
            raise ValueError("SimClock cannot move backwards")
        self.now = moment
        return self.now

    @property
    def elapsed(self) -> timedelta:
        return self.now - self.start

    def is_open(self, moment: datetime | None = None) -> bool:
        m = moment or self.now
        return m.weekday() in self.workdays and self.open_hour <= m.hour < self.close_hour

    def next_open(self, moment: datetime | None = None) -> datetime:
        """First business moment at or after `moment`."""
        m = moment or self.now
        # Walk forward at most two weeks; a schedule with no open days would hang.
        for _ in range(14 * 24):
            if self.is_open(m):
                return m
            if m.weekday() not in self.workdays or m.hour >= self.close_hour:
                m = (m + timedelta(days=1)).replace(
                    hour=self.open_hour, minute=0, second=0, microsecond=0
                )
            else:  # before opening on a workday
                m = m.replace(hour=self.open_hour, minute=0, second=0, microsecond=0)
        raise RuntimeError("No open business hours found within two weeks")
