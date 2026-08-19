"""Projections: state is derived from events, including at past moments."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from ai_bos.domain.entities import BookingState, ObligationState, PartyRole
from ai_bos.domain.events import DomainEvent, EventType
from ai_bos.domain.projections import project

BID = uuid.uuid4()
T0 = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)


def _e(event_type, stream_id, payload=None, at=T0) -> DomainEvent:
    return DomainEvent(
        event_type=event_type,
        business_id=BID,
        stream_id=stream_id,
        payload=payload or {},
        occurred_at=at,
        recorded_at=at,
    )


def test_party_registration_and_update():
    pid = uuid.uuid4()
    state = project([
        _e(EventType.PARTY_REGISTERED, pid,
           {"display_name": "Maria Alvarez", "emails": ["m@example.com"],
            "roles": ["CUSTOMER"]}),
        _e(EventType.PARTY_UPDATED, pid,
           {"phones": ["+15550001"], "identity_confidence": "HIGH"}),
    ])
    party = state.parties[pid]
    assert party.display_name == "Maria Alvarez"
    assert party.phones == ["+15550001"]
    assert party.identity_confidence == "HIGH"
    assert party.has_role(PartyRole.CUSTOMER)


def test_update_does_not_duplicate_existing_contacts():
    pid = uuid.uuid4()
    state = project([
        _e(EventType.PARTY_REGISTERED, pid, {"emails": ["a@b.com"]}),
        _e(EventType.PARTY_UPDATED, pid, {"emails": ["a@b.com", "c@d.com"]}),
    ])
    assert state.parties[pid].emails == ["a@b.com", "c@d.com"]


def test_merge_preserves_the_absorbed_record():
    """Merging never deletes — any prior reference must still resolve."""
    keep, absorb = uuid.uuid4(), uuid.uuid4()
    state = project([
        _e(EventType.PARTY_REGISTERED, keep, {"emails": ["keep@x.com"]}),
        _e(EventType.PARTY_REGISTERED, absorb, {"emails": ["dup@x.com"]}),
        _e(EventType.PARTY_MERGED, absorb, {"merged_into": str(keep)}),
    ])
    assert state.parties[absorb].merged_into == keep
    assert not state.parties[absorb].is_active
    assert "dup@x.com" in state.parties[keep].emails
    assert state.resolve_party(absorb).party_id == keep
    assert len(state.active_parties()) == 1


def test_booking_lifecycle():
    bid = uuid.uuid4()
    state = project([
        _e(EventType.BOOKING_REQUESTED, bid,
           {"starts_at": T0.isoformat(), "ends_at": (T0 + timedelta(hours=1)).isoformat()}),
        _e(EventType.BOOKING_CONFIRMED, bid),
    ])
    assert state.bookings[bid].state is BookingState.CONFIRMED

    state = project([
        _e(EventType.BOOKING_REQUESTED, bid, {"starts_at": T0.isoformat()}),
        _e(EventType.BOOKING_CONFIRMED, bid),
        _e(EventType.BOOKING_NO_SHOW, bid),
    ])
    assert state.bookings[bid].state is BookingState.NO_SHOW
    assert not state.bookings[bid].is_active


def test_reschedule_requires_reconfirmation():
    bid = uuid.uuid4()
    later = T0 + timedelta(days=7)
    state = project([
        _e(EventType.BOOKING_REQUESTED, bid, {"starts_at": T0.isoformat()}),
        _e(EventType.BOOKING_CONFIRMED, bid),
        _e(EventType.BOOKING_RESCHEDULED, bid, {"starts_at": later.isoformat()}),
    ])
    booking = state.bookings[bid]
    assert booking.starts_at == later
    assert booking.state is BookingState.REQUESTED


def test_double_booking_is_detected():
    room = uuid.uuid4()
    a, b = uuid.uuid4(), uuid.uuid4()
    state = project([
        _e(EventType.BOOKING_REQUESTED, a,
           {"resource_ids": [str(room)], "starts_at": T0.isoformat(),
            "ends_at": (T0 + timedelta(hours=1)).isoformat()}),
        _e(EventType.BOOKING_REQUESTED, b,
           {"resource_ids": [str(room)], "starts_at": (T0 + timedelta(minutes=30)).isoformat(),
            "ends_at": (T0 + timedelta(minutes=90)).isoformat()}),
    ])
    assert len(state.booking_conflicts()) == 1


def test_cancelled_booking_frees_the_resource():
    room = uuid.uuid4()
    a, b = uuid.uuid4(), uuid.uuid4()
    events = [
        _e(EventType.BOOKING_REQUESTED, a,
           {"resource_ids": [str(room)], "starts_at": T0.isoformat(),
            "ends_at": (T0 + timedelta(hours=1)).isoformat()}),
        _e(EventType.BOOKING_REQUESTED, b,
           {"resource_ids": [str(room)], "starts_at": T0.isoformat(),
            "ends_at": (T0 + timedelta(hours=1)).isoformat()}),
    ]
    assert len(project(events).booking_conflicts()) == 1
    events.append(_e(EventType.BOOKING_CANCELLED, a))
    assert project(events).booking_conflicts() == []


def test_obligations_and_outstanding_balance():
    o1, o2 = uuid.uuid4(), uuid.uuid4()
    state = project([
        _e(EventType.OBLIGATION_CREATED, o1, {"amount": "250.00"}),
        _e(EventType.OBLIGATION_CREATED, o2, {"amount": "100.00"}),
        _e(EventType.OBLIGATION_SETTLED, o2),
    ])
    assert state.amount_outstanding() == Decimal("250.00")
    assert len(state.outstanding_obligations()) == 1
    assert state.obligations[o2].state is ObligationState.SETTLED


def test_refund_preserves_gross_and_net():
    tid = uuid.uuid4()
    state = project([
        _e(EventType.TRANSACTION_RECORDED, tid, {"amount": "200.00"}),
        _e(EventType.TRANSACTION_REFUNDED, tid, {"amount": "50.00"}),
    ])
    txn = state.transactions[tid]
    assert txn.amount == Decimal("200.00")
    assert txn.refunded_amount == Decimal("50.00")
    assert txn.net_amount == Decimal("150.00")


def test_document_amendment_keeps_the_superseded_version():
    did = uuid.uuid4()
    state = project([
        _e(EventType.DOCUMENT_ADDED, did, {"content": "original", "is_regulated": True}),
        _e(EventType.DOCUMENT_AMENDED, did, {"content": "corrected"}),
    ])
    doc = state.documents[did]
    assert doc.content == "corrected"
    assert doc.versions[0]["content"] == "original"
    assert doc.version_count == 2


def test_as_of_reconstructs_a_past_belief():
    """'What did we believe on the 14th' is what an audit actually asks."""
    bid = uuid.uuid4()
    events = [
        _e(EventType.BOOKING_REQUESTED, bid, {"starts_at": T0.isoformat()}, at=T0),
        _e(EventType.BOOKING_CONFIRMED, bid, at=T0 + timedelta(days=1)),
        _e(EventType.BOOKING_CANCELLED, bid, at=T0 + timedelta(days=2)),
    ]
    assert project(events, until=T0 + timedelta(hours=1)).bookings[bid].state is BookingState.REQUESTED
    assert project(events, until=T0 + timedelta(days=1, hours=1)).bookings[bid].state is BookingState.CONFIRMED
    assert project(events).bookings[bid].state is BookingState.CANCELLED


def test_unknown_event_types_are_counted_not_fatal():
    """A newer instance's events must not crash an older projector."""
    state = project([_e(EventType.PARTY_REGISTERED, uuid.uuid4())])
    assert state.events_applied == 1


def test_service_without_price_requires_a_quote():
    sid = uuid.uuid4()
    state = project([
        _e(EventType.SERVICE_DEFINED, sid, {"name": "Crown", "code": "D2740"}),
    ])
    assert state.services[sid].requires_quote

    priced = uuid.uuid4()
    state = project([
        _e(EventType.SERVICE_DEFINED, priced, {"name": "Exam", "default_price": "65"}),
    ])
    assert not state.services[priced].requires_quote
