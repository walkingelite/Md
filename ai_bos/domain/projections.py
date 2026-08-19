"""Rebuild business state by folding the event log.

Because state is derived rather than stored, `as_of` gives an exact answer to
"what did we believe on the 14th" — which is what an audit, a dispute or a
regulator actually asks for.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

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
from ai_bos.domain.events import DomainEvent, EventType


@dataclass
class BusinessState:
    business_id: uuid.UUID | None = None
    parties: dict[uuid.UUID, Party] = field(default_factory=dict)
    resources: dict[uuid.UUID, Resource] = field(default_factory=dict)
    services: dict[uuid.UUID, Service] = field(default_factory=dict)
    bookings: dict[uuid.UUID, Booking] = field(default_factory=dict)
    obligations: dict[uuid.UUID, Obligation] = field(default_factory=dict)
    transactions: dict[uuid.UUID, Transaction] = field(default_factory=dict)
    documents: dict[uuid.UUID, Document] = field(default_factory=dict)
    events_applied: int = 0

    # -------------------------------------------------------------- queries

    def active_parties(self) -> list[Party]:
        return [p for p in self.parties.values() if p.is_active]

    def customers(self) -> list[Party]:
        return [p for p in self.active_parties() if p.has_role(PartyRole.CUSTOMER)]

    def active_bookings(self) -> list[Booking]:
        return [b for b in self.bookings.values() if b.is_active]

    def outstanding_obligations(self) -> list[Obligation]:
        return [o for o in self.obligations.values() if o.is_outstanding]

    def amount_outstanding(self) -> Decimal:
        return sum(
            (o.amount for o in self.outstanding_obligations()), start=Decimal("0")
        )

    def booking_conflicts(self) -> list[tuple[Booking, Booking]]:
        """Every pair of active bookings competing for the same resource."""
        active = self.active_bookings()
        conflicts = []
        for i, a in enumerate(active):
            for b in active[i + 1:]:
                if a.conflicts_with(b):
                    conflicts.append((a, b))
        return conflicts

    def resolve_party(self, party_id: uuid.UUID) -> Party | None:
        """Follow merge pointers to the surviving record."""
        seen: set[uuid.UUID] = set()
        current = self.parties.get(party_id)
        while current and current.merged_into and current.merged_into not in seen:
            seen.add(current.party_id)
            current = self.parties.get(current.merged_into)
        return current


_HANDLERS = {}


def _handles(event_type: EventType):
    def decorator(fn):
        _HANDLERS[event_type] = fn
        return fn

    return decorator


# ------------------------------------------------------------------ parties

@_handles(EventType.PARTY_REGISTERED)
def _party_registered(state: BusinessState, e: DomainEvent) -> None:
    p = e.payload
    state.parties[e.stream_id] = Party(
        party_id=e.stream_id,
        roles={PartyRole(r) for r in p.get("roles", ["CUSTOMER"])},
        display_name=p.get("display_name", ""),
        emails=list(p.get("emails", [])),
        phones=list(p.get("phones", [])),
        identity_confidence=p.get("identity_confidence", "LOW"),
        consent=dict(p.get("consent", {})),
        attributes=dict(p.get("attributes", {})),
        created_at=e.occurred_at,
    )


@_handles(EventType.PARTY_UPDATED)
def _party_updated(state: BusinessState, e: DomainEvent) -> None:
    party = state.parties.get(e.stream_id)
    if party is None:
        return
    p = e.payload
    if "display_name" in p:
        party.display_name = p["display_name"]
    if "identity_confidence" in p:
        party.identity_confidence = p["identity_confidence"]
    for key in ("emails", "phones"):
        for value in p.get(key, []):
            existing = getattr(party, key)
            if value not in existing:
                existing.append(value)
    party.consent.update(p.get("consent", {}))
    party.attributes.update(p.get("attributes", {}))
    for role in p.get("roles", []):
        party.roles.add(PartyRole(role))


@_handles(EventType.PARTY_MERGED)
def _party_merged(state: BusinessState, e: DomainEvent) -> None:
    """Merging never deletes. The absorbed record stays, pointing at the
    survivor, so any prior reference still resolves."""
    absorbed = state.parties.get(e.stream_id)
    survivor_id = e.payload.get("merged_into")
    if absorbed is None or not survivor_id:
        return
    survivor = state.parties.get(uuid.UUID(str(survivor_id)))
    if survivor is None:
        return

    absorbed.merged_into = survivor.party_id
    for email in absorbed.emails:
        if email not in survivor.emails:
            survivor.emails.append(email)
    for phone in absorbed.phones:
        if phone not in survivor.phones:
            survivor.phones.append(phone)
    survivor.roles |= absorbed.roles


# --------------------------------------------------------- services/resources

@_handles(EventType.SERVICE_DEFINED)
def _service_defined(state: BusinessState, e: DomainEvent) -> None:
    p = e.payload
    price = p.get("default_price")
    state.services[e.stream_id] = Service(
        service_id=e.stream_id,
        name=p.get("name", ""),
        code=p.get("code", ""),
        code_system=p.get("code_system", ""),
        duration_minutes=int(p.get("duration_minutes", 30)),
        default_price=Decimal(str(price)) if price is not None else None,
        required_resource_types=list(p.get("required_resource_types", [])),
        attributes=dict(p.get("attributes", {})),
    )


@_handles(EventType.SERVICE_RETIRED)
def _service_retired(state: BusinessState, e: DomainEvent) -> None:
    service = state.services.get(e.stream_id)
    if service:
        service.retired = True


@_handles(EventType.RESOURCE_DEFINED)
def _resource_defined(state: BusinessState, e: DomainEvent) -> None:
    p = e.payload
    party_id = p.get("party_id")
    state.resources[e.stream_id] = Resource(
        resource_id=e.stream_id,
        name=p.get("name", ""),
        resource_type=p.get("resource_type", "generic"),
        party_id=uuid.UUID(str(party_id)) if party_id else None,
        capacity=int(p.get("capacity", 1)),
        attributes=dict(p.get("attributes", {})),
    )


@_handles(EventType.RESOURCE_UNAVAILABLE)
def _resource_unavailable(state: BusinessState, e: DomainEvent) -> None:
    resource = state.resources.get(e.stream_id)
    if resource:
        resource.active = False


# ----------------------------------------------------------------- bookings

def _parse_dt(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


@_handles(EventType.BOOKING_REQUESTED)
def _booking_requested(state: BusinessState, e: DomainEvent) -> None:
    p = e.payload
    party_id = p.get("party_id")
    state.bookings[e.stream_id] = Booking(
        booking_id=e.stream_id,
        party_id=uuid.UUID(str(party_id)) if party_id else None,
        service_ids=[uuid.UUID(str(s)) for s in p.get("service_ids", [])],
        resource_ids=[uuid.UUID(str(r)) for r in p.get("resource_ids", [])],
        starts_at=_parse_dt(p.get("starts_at")),
        ends_at=_parse_dt(p.get("ends_at")),
        state=BookingState.REQUESTED,
        notes=p.get("notes", ""),
        attributes=dict(p.get("attributes", {})),
    )


def _set_booking_state(state: BusinessState, e: DomainEvent, new: BookingState) -> None:
    booking = state.bookings.get(e.stream_id)
    if booking:
        booking.state = new


@_handles(EventType.BOOKING_CONFIRMED)
def _booking_confirmed(state: BusinessState, e: DomainEvent) -> None:
    _set_booking_state(state, e, BookingState.CONFIRMED)


@_handles(EventType.BOOKING_CANCELLED)
def _booking_cancelled(state: BusinessState, e: DomainEvent) -> None:
    _set_booking_state(state, e, BookingState.CANCELLED)


@_handles(EventType.BOOKING_COMPLETED)
def _booking_completed(state: BusinessState, e: DomainEvent) -> None:
    _set_booking_state(state, e, BookingState.COMPLETED)


@_handles(EventType.BOOKING_NO_SHOW)
def _booking_no_show(state: BusinessState, e: DomainEvent) -> None:
    _set_booking_state(state, e, BookingState.NO_SHOW)


@_handles(EventType.BOOKING_RESCHEDULED)
def _booking_rescheduled(state: BusinessState, e: DomainEvent) -> None:
    booking = state.bookings.get(e.stream_id)
    if booking is None:
        return
    p = e.payload
    booking.starts_at = _parse_dt(p.get("starts_at")) or booking.starts_at
    booking.ends_at = _parse_dt(p.get("ends_at")) or booking.ends_at
    if p.get("resource_ids"):
        booking.resource_ids = [uuid.UUID(str(r)) for r in p["resource_ids"]]
    # A reschedule re-opens the booking; it needs confirming again.
    booking.state = BookingState.REQUESTED


# -------------------------------------------------------------- obligations

@_handles(EventType.OBLIGATION_CREATED)
def _obligation_created(state: BusinessState, e: DomainEvent) -> None:
    p = e.payload
    state.obligations[e.stream_id] = Obligation(
        obligation_id=e.stream_id,
        obligation_type=p.get("obligation_type", "invoice"),
        owed_by=uuid.UUID(str(p["owed_by"])) if p.get("owed_by") else None,
        owed_to=uuid.UUID(str(p["owed_to"])) if p.get("owed_to") else None,
        amount=Decimal(str(p.get("amount", "0"))),
        currency=p.get("currency", "USD"),
        booking_id=uuid.UUID(str(p["booking_id"])) if p.get("booking_id") else None,
        due_at=_parse_dt(p.get("due_at")),
        attributes=dict(p.get("attributes", {})),
    )


def _set_obligation_state(
    state: BusinessState, e: DomainEvent, new: ObligationState
) -> None:
    obligation = state.obligations.get(e.stream_id)
    if obligation:
        obligation.state = new


@_handles(EventType.OBLIGATION_SUBMITTED)
def _obligation_submitted(state: BusinessState, e: DomainEvent) -> None:
    _set_obligation_state(state, e, ObligationState.SUBMITTED)


@_handles(EventType.OBLIGATION_SETTLED)
def _obligation_settled(state: BusinessState, e: DomainEvent) -> None:
    _set_obligation_state(state, e, ObligationState.SETTLED)


@_handles(EventType.OBLIGATION_REJECTED)
def _obligation_rejected(state: BusinessState, e: DomainEvent) -> None:
    _set_obligation_state(state, e, ObligationState.REJECTED)


@_handles(EventType.OBLIGATION_WRITTEN_OFF)
def _obligation_written_off(state: BusinessState, e: DomainEvent) -> None:
    _set_obligation_state(state, e, ObligationState.WRITTEN_OFF)


# ------------------------------------------------------------- transactions

@_handles(EventType.TRANSACTION_RECORDED)
def _transaction_recorded(state: BusinessState, e: DomainEvent) -> None:
    p = e.payload
    state.transactions[e.stream_id] = Transaction(
        transaction_id=e.stream_id,
        obligation_id=uuid.UUID(str(p["obligation_id"])) if p.get("obligation_id") else None,
        party_id=uuid.UUID(str(p["party_id"])) if p.get("party_id") else None,
        amount=Decimal(str(p.get("amount", "0"))),
        currency=p.get("currency", "USD"),
        direction=p.get("direction", "INBOUND"),
        method=p.get("method", ""),
        occurred_at=e.occurred_at,
        external_reference=p.get("external_reference", ""),
    )


@_handles(EventType.TRANSACTION_REFUNDED)
def _transaction_refunded(state: BusinessState, e: DomainEvent) -> None:
    """Refunds accumulate rather than replacing the original amount, so the
    gross and the net both stay recoverable."""
    txn = state.transactions.get(e.stream_id)
    if txn:
        txn.refunded_amount += Decimal(str(e.payload.get("amount", "0")))


# ---------------------------------------------------------------- documents

@_handles(EventType.DOCUMENT_ADDED)
def _document_added(state: BusinessState, e: DomainEvent) -> None:
    p = e.payload
    state.documents[e.stream_id] = Document(
        document_id=e.stream_id,
        party_id=uuid.UUID(str(p["party_id"])) if p.get("party_id") else None,
        booking_id=uuid.UUID(str(p["booking_id"])) if p.get("booking_id") else None,
        document_type=p.get("document_type", "note"),
        content=p.get("content", ""),
        is_regulated=bool(p.get("is_regulated", False)),
        created_at=e.occurred_at,
    )


@_handles(EventType.DOCUMENT_AMENDED)
def _document_amended(state: BusinessState, e: DomainEvent) -> None:
    """Amendment appends. Regulated records generally require the superseded
    version to remain recoverable."""
    doc = state.documents.get(e.stream_id)
    if doc is None:
        return
    doc.versions.append({"content": doc.content, "superseded_at": e.occurred_at})
    doc.content = e.payload.get("content", doc.content)


def project(
    events: list[DomainEvent], until: datetime | None = None
) -> BusinessState:
    """Fold events into state. `until` answers 'what did we believe then'."""
    state = BusinessState()
    for event in events:
        if until is not None and event.recorded_at > until:
            continue
        if state.business_id is None:
            state.business_id = event.business_id
        handler = _HANDLERS.get(event.event_type)
        if handler is not None:
            handler(state, event)
        state.events_applied += 1
    return state
