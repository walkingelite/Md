"""Event log: append-only semantics and optimistic concurrency."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from ai_bos.domain.events import ConcurrencyError, DomainEvent, EventSource, EventType
from ai_bos.domain.store import InMemoryEventStore

BID = uuid.uuid4()


def _event(stream_id: uuid.UUID, source=EventSource.NATIVE, **kw) -> DomainEvent:
    return DomainEvent(
        event_type=EventType.PARTY_REGISTERED,
        business_id=BID,
        stream_id=stream_id,
        payload={"display_name": "Test"},
        source=source,
        **kw,
    )


async def test_append_assigns_sequential_versions():
    store = InMemoryEventStore()
    stream = uuid.uuid4()
    a = await store.append([_event(stream)])
    b = await store.append([_event(stream)])
    assert a[0].sequence == 1
    assert b[0].sequence == 2
    assert await store.stream_version(stream) == 2


async def test_concurrent_write_is_rejected():
    """Two agents booking the same slot must not both succeed."""
    store = InMemoryEventStore()
    stream = uuid.uuid4()
    await store.append([_event(stream)], expected_version=0)

    with pytest.raises(ConcurrencyError) as exc:
        await store.append([_event(stream)], expected_version=0)
    assert exc.value.actual == 1


async def test_correct_expected_version_succeeds():
    store = InMemoryEventStore()
    stream = uuid.uuid4()
    await store.append([_event(stream)], expected_version=0)
    await store.append([_event(stream)], expected_version=1)
    assert await store.stream_version(stream) == 2


async def test_append_must_target_a_single_stream():
    store = InMemoryEventStore()
    with pytest.raises(ValueError):
        await store.append([_event(uuid.uuid4()), _event(uuid.uuid4())])


async def test_events_are_never_mutated():
    store = InMemoryEventStore()
    stream = uuid.uuid4()
    original = _event(stream)
    stored = (await store.append([original]))[0]
    # with_sequence returns a copy; the caller's event is untouched.
    assert original.sequence == 0
    assert stored.sequence == 1


async def test_read_all_is_scoped_to_one_business():
    store = InMemoryEventStore()
    other = uuid.uuid4()
    await store.append([_event(uuid.uuid4())])
    await store.append([
        DomainEvent(
            event_type=EventType.PARTY_REGISTERED,
            business_id=other,
            stream_id=uuid.uuid4(),
        )
    ])
    assert len(await store.read_all(BID)) == 1
    assert len(await store.read_all(other)) == 1


async def test_read_by_source_separates_imported_from_native():
    """Imported history must stay distinguishable from what the system did."""
    store = InMemoryEventStore()
    await store.append([_event(uuid.uuid4(), source=EventSource.NATIVE)])
    await store.append([_event(uuid.uuid4(), source=EventSource.IMPORTED)])
    await store.append([_event(uuid.uuid4(), source=EventSource.SIMULATED)])

    assert len(await store.read_by_source(BID, EventSource.NATIVE)) == 1
    assert len(await store.read_by_source(BID, EventSource.IMPORTED)) == 1
    assert len(await store.read_by_source(BID, EventSource.SIMULATED)) == 1


async def test_read_all_orders_by_record_time_not_world_time():
    """Imported history has occurred_at decades in the past; replaying in
    world-time order would apply old facts after newer ones."""
    store = InMemoryEventStore()
    now = datetime.now(tz=timezone.utc)

    await store.append([_event(uuid.uuid4(), occurred_at=now - timedelta(days=3650),
                               recorded_at=now)])
    await store.append([_event(uuid.uuid4(), occurred_at=now,
                               recorded_at=now + timedelta(seconds=1))])

    events = await store.read_all(BID)
    assert events[0].occurred_at < events[1].occurred_at
    assert events[0].recorded_at < events[1].recorded_at
