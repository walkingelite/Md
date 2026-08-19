"""Append-only event storage with optimistic concurrency."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime
from typing import Protocol

from ai_bos.domain.events import ConcurrencyError, DomainEvent, EventSource
from ai_bos.logging_config import log


class EventStore(Protocol):
    async def append(
        self, events: list[DomainEvent], expected_version: int | None = None
    ) -> list[DomainEvent]: ...
    async def read_stream(self, stream_id: uuid.UUID) -> list[DomainEvent]: ...
    async def read_all(
        self, business_id: uuid.UUID, until: datetime | None = None
    ) -> list[DomainEvent]: ...
    async def stream_version(self, stream_id: uuid.UUID) -> int: ...


class InMemoryEventStore:
    """Used by the simulator and the test suite.

    Ordering is by recorded_at rather than occurred_at, because imported
    history has occurred_at values decades in the past and replaying in
    world-time order would apply old facts after newer ones.
    """

    def __init__(self) -> None:
        self._streams: dict[uuid.UUID, list[DomainEvent]] = defaultdict(list)
        self._all: list[DomainEvent] = []

    async def append(
        self, events: list[DomainEvent], expected_version: int | None = None
    ) -> list[DomainEvent]:
        if not events:
            return []

        stream_id = events[0].stream_id
        if any(e.stream_id != stream_id for e in events):
            raise ValueError("A single append must target one stream")

        current = len(self._streams[stream_id])
        if expected_version is not None and expected_version != current:
            raise ConcurrencyError(stream_id, expected_version, current)

        stamped = []
        for offset, event in enumerate(events):
            placed = event.with_sequence(current + offset + 1)
            self._streams[stream_id].append(placed)
            self._all.append(placed)
            stamped.append(placed)

        log.debug(
            "event_store.appended",
            stream_id=str(stream_id),
            count=len(stamped),
            version=len(self._streams[stream_id]),
        )
        return stamped

    async def read_stream(self, stream_id: uuid.UUID) -> list[DomainEvent]:
        return list(self._streams[stream_id])

    async def read_all(
        self, business_id: uuid.UUID, until: datetime | None = None
    ) -> list[DomainEvent]:
        events = [e for e in self._all if e.business_id == business_id]
        if until is not None:
            events = [e for e in events if e.recorded_at <= until]
        return sorted(events, key=lambda e: (e.recorded_at, e.sequence))

    async def read_by_source(
        self, business_id: uuid.UUID, source: EventSource
    ) -> list[DomainEvent]:
        return [
            e for e in await self.read_all(business_id) if e.source is source
        ]

    async def stream_version(self, stream_id: uuid.UUID) -> int:
        return len(self._streams[stream_id])

    def __len__(self) -> int:
        """Total events held.

        Note that defining this makes an empty store falsy, so callers must
        write `store if store is not None else default()` rather than
        `store or default()` — the latter silently discards a live empty store.
        """
        return len(self._all)
