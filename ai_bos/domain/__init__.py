"""The business object graph and its event log.

This is the system of record. State is derived from an append-only event
stream rather than stored directly, which buys three things at once: complete
history for free, the ability to reconstruct state at any past moment, and a
migration path — another system's twenty years of records import as events and
are thereafter indistinguishable from natively produced ones.

The entities here are deliberately generic. A dental practice, a plumbing
company and a salon differ in vocabulary, not in structure: all of them have
parties, bookable resources, services, obligations and money. Vertical packs
supply the vocabulary.
"""

from ai_bos.domain.events import (
    DomainEvent,
    EventSource,
    EventType,
    ConcurrencyError,
)
from ai_bos.domain.entities import (
    Booking,
    BookingState,
    Document,
    Obligation,
    ObligationState,
    Party,
    PartyRole,
    Resource,
    Service,
    Transaction,
)
from ai_bos.domain.store import EventStore, InMemoryEventStore
from ai_bos.domain.projections import BusinessState, project

__all__ = [
    "DomainEvent",
    "EventSource",
    "EventType",
    "ConcurrencyError",
    "Party",
    "PartyRole",
    "Resource",
    "Service",
    "Booking",
    "BookingState",
    "Obligation",
    "ObligationState",
    "Transaction",
    "Document",
    "EventStore",
    "InMemoryEventStore",
    "BusinessState",
    "project",
]
