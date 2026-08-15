"""Simulation clock: determinism and business-hours arithmetic."""

from datetime import datetime, timedelta, timezone

import pytest

from ai_bos.simulation.clock import SimClock


def _clock() -> SimClock:
    # Wednesday 2026-01-07, 09:00 UTC
    return SimClock(start=datetime(2026, 1, 7, 9, 0, tzinfo=timezone.utc))


def test_starts_at_start():
    c = _clock()
    assert c.now == c.start
    assert c.elapsed == timedelta(0)


def test_advance_accumulates():
    c = _clock()
    c.advance(3600)
    c.advance(1800)
    assert c.elapsed == timedelta(seconds=5400)


def test_cannot_move_backwards():
    c = _clock()
    with pytest.raises(ValueError):
        c.advance_to(c.start - timedelta(hours=1))


def test_is_open_during_business_hours():
    c = _clock()
    assert c.is_open(datetime(2026, 1, 7, 10, 0, tzinfo=timezone.utc))     # Wed 10am
    assert not c.is_open(datetime(2026, 1, 7, 19, 0, tzinfo=timezone.utc))  # Wed 7pm
    assert not c.is_open(datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc))  # Saturday


def test_next_open_skips_weekend():
    c = _clock()
    friday_evening = datetime(2026, 1, 9, 20, 0, tzinfo=timezone.utc)
    nxt = c.next_open(friday_evening)
    assert nxt.weekday() == 0          # Monday
    assert nxt.hour == c.open_hour


def test_next_open_is_identity_when_already_open():
    c = _clock()
    during = datetime(2026, 1, 7, 11, 0, tzinfo=timezone.utc)
    assert c.next_open(during) == during


def test_naive_start_is_coerced_to_utc():
    c = SimClock(start=datetime(2026, 1, 7, 9, 0))
    assert c.start.tzinfo is timezone.utc
