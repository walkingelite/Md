"""The append-only event log that everything else is derived from."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventSource(str, Enum):
    """Where an event came from.

    Kept explicit because the three are not interchangeable. Imported history
    describes things that happened before the system existed and must never be
    treated as something the system did; simulated events must never leak into
    a real business's reasoning.
    """

    NATIVE = "NATIVE"        # this system caused it
    IMPORTED = "IMPORTED"    # migrated from a prior system
    EXTERNAL = "EXTERNAL"    # observed from an integration
    SIMULATED = "SIMULATED"  # produced by the simulation engine


class EventType(str, Enum):
    # Parties
    PARTY_REGISTERED = "party.registered"
    PARTY_UPDATED = "party.updated"
    PARTY_MERGED = "party.merged"

    # Bookings
    BOOKING_REQUESTED = "booking.requested"
    BOOKING_CONFIRMED = "booking.confirmed"
    BOOKING_RESCHEDULED = "booking.rescheduled"
    BOOKING_CANCELLED = "booking.cancelled"
    BOOKING_COMPLETED = "booking.completed"
    BOOKING_NO_SHOW = "booking.no_show"

    # Services and resources
    SERVICE_DEFINED = "service.defined"
    SERVICE_RETIRED = "service.retired"
    RESOURCE_DEFINED = "resource.defined"
    RESOURCE_UNAVAILABLE = "resource.unavailable"

    # Obligations (anything owed by either side)
    OBLIGATION_CREATED = "obligation.created"
    OBLIGATION_SUBMITTED = "obligation.submitted"
    OBLIGATION_SETTLED = "obligation.settled"
    OBLIGATION_REJECTED = "obligation.rejected"
    OBLIGATION_WRITTEN_OFF = "obligation.written_off"

    # Money
    TRANSACTION_RECORDED = "transaction.recorded"
    TRANSACTION_REFUNDED = "transaction.refunded"

    # Documents
    DOCUMENT_ADDED = "document.added"
    DOCUMENT_AMENDED = "document.amended"


@dataclass(frozen=True)
class DomainEvent:
    """One immutable fact. Never updated, never deleted."""

    event_type: EventType
    business_id: uuid.UUID
    stream_id: uuid.UUID                      # the entity this concerns
    payload: dict[str, Any] = field(default_factory=dict)

    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    sequence: int = 0                         # position within its stream
    source: EventSource = EventSource.NATIVE

    # When it happened in the world, versus when we learned of it. Imported
    # history has an occurred_at far earlier than its recorded_at, and
    # reporting that conflates the two is wrong in both directions.
    occurred_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    recorded_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    actor: str = "system"                     # system | owner | customer | import
    causation_id: uuid.UUID | None = None     # the event that caused this one
    correlation_id: uuid.UUID | None = None   # groups events from one intent

    def with_sequence(self, sequence: int) -> "DomainEvent":
        from dataclasses import replace

        return replace(self, sequence=sequence)


class ConcurrencyError(Exception):
    """Raised when two writers race on the same stream.

    Optimistic concurrency is the point: two agents booking the same slot must
    not both succeed, and the loser has to re-read and retry rather than
    silently overwrite.
    """

    def __init__(self, stream_id: uuid.UUID, expected: int, actual: int) -> None:
        super().__init__(
            f"Stream {stream_id} is at version {actual}, expected {expected}"
        )
        self.stream_id = stream_id
        self.expected = expected
        self.actual = actual
