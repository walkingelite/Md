"""Import: idempotency, honest reporting, and history that projects correctly."""

import uuid
from datetime import datetime, timezone

from ai_bos.domain.events import EventSource, EventType
from ai_bos.domain.projections import project
from ai_bos.domain.store import InMemoryEventStore
from ai_bos.migration.importer import Importer
from ai_bos.migration.mappers import GENERIC_CSV_MAPPER

BID = uuid.uuid4()

PARTIES = [
    {"id": "1001", "name": "Maria Alvarez", "email": "maria@example.com",
     "phone": "+15550001", "created_at": "2009-04-12"},
    {"id": "1002", "name": "James Chen", "email": "james@example.com",
     "phone": "+15550002", "created_at": "2011-08-03"},
    {"id": "1003", "name": "", "email": "broken@example.com"},  # missing name
]

BOOKINGS = [
    {"id": "5001", "start_time": "2024-03-14 09:00:00", "end_time": "2024-03-14 10:00:00",
     "notes": "cleaning"},
    {"id": "5002", "start_time": "not a date", "notes": "malformed"},
]


def _importer(store=None) -> Importer:
    # `store or InMemoryEventStore()` would be wrong: the store defines
    # __len__, so an empty one is falsy and would be silently discarded.
    return Importer(
        BID, store if store is not None else InMemoryEventStore(), GENERIC_CSV_MAPPER
    )


async def test_import_creates_events():
    imp = _importer()
    report = await imp.run({"parties": PARTIES})
    assert report.events_created == 2
    assert report.rows_seen == 3
    assert report.rows_skipped == 1
    assert "missing required field" in report.skip_reasons


async def test_imported_events_are_marked_as_such():
    """Imported history must never read as something the system did."""
    store = InMemoryEventStore()
    await _importer(store).run({"parties": PARTIES})

    events = await store.read_all(BID)
    assert all(e.source is EventSource.IMPORTED for e in events)
    assert all(e.actor == "import" for e in events)


async def test_imported_history_keeps_its_original_dates():
    """Dating twenty-year-old records to today would destroy the history that
    is the entire reason for importing."""
    store = InMemoryEventStore()
    await _importer(store).run({"parties": PARTIES})

    events = await store.read_all(BID)
    occurred = sorted(e.occurred_at for e in events)
    assert occurred[0].year == 2009
    assert all(e.recorded_at.year >= 2024 for e in events)


async def test_import_is_idempotent():
    """Real migrations are run several times before cutover."""
    store = InMemoryEventStore()
    imp = _importer(store)

    first = await imp.run({"parties": PARTIES})
    second = await imp.run({"parties": PARTIES})

    assert first.events_created == 2
    assert second.events_created == 0
    assert second.skip_reasons.get("already imported") == 2
    assert len(store) == 2


async def test_reimport_in_a_fresh_process_maps_to_the_same_entities():
    """Ids are derived from the source id, not generated, so a re-run in a new
    process does not duplicate every record."""
    store = InMemoryEventStore()
    await _importer(store).run({"parties": PARTIES})
    ids_first = {e.stream_id for e in await store.read_all(BID)}

    store2 = InMemoryEventStore()
    await _importer(store2).run({"parties": PARTIES})
    ids_second = {e.stream_id for e in await store2.read_all(BID)}

    assert ids_first == ids_second


async def test_imported_records_project_into_usable_state():
    store = InMemoryEventStore()
    await _importer(store).run({"parties": PARTIES})

    state = project(await store.read_all(BID))
    names = {p.display_name for p in state.active_parties()}
    assert names == {"Maria Alvarez", "James Chen"}
    assert any("maria@example.com" in p.emails for p in state.active_parties())


async def test_malformed_rows_are_skipped_not_fatal():
    imp = _importer()
    report = await imp.run({"bookings": BOOKINGS})
    assert report.events_created == 1
    assert report.rows_skipped == 1


async def test_parties_import_before_dependent_records():
    store = InMemoryEventStore()
    imp = _importer(store)
    await imp.run({"bookings": BOOKINGS, "obligations": [], "parties": PARTIES})

    events = await store.read_all(BID)
    first_party = next(i for i, e in enumerate(events)
                       if e.event_type is EventType.PARTY_REGISTERED)
    first_booking = next(i for i, e in enumerate(events)
                         if e.event_type is EventType.BOOKING_REQUESTED)
    assert first_party < first_booking


async def test_unknown_source_is_ignored_not_fatal():
    imp = _importer()
    report = await imp.run({"martian_records": [{"id": "1"}]})
    assert report.events_created == 0


async def test_verify_reads_back_what_landed():
    """An import that reports success but leaves nothing queryable is the
    failure that destroys trust at cutover."""
    store = InMemoryEventStore()
    imp = _importer(store)
    await imp.run({"parties": PARTIES, "bookings": BOOKINGS})

    counts = await imp.verify()
    assert counts["parties"] == 2
    assert counts["bookings"] == 1


async def test_report_flags_partial_migration():
    imp = _importer()
    report = await imp.run({"parties": PARTIES})
    summary = report.summary()
    assert "did not import" in summary
    assert "success rate" in summary


async def test_external_ids_are_retained_for_lookup():
    """Support staff still search by the old system's number for years."""
    store = InMemoryEventStore()
    await _importer(store).run({"parties": PARTIES})
    events = await store.read_all(BID)
    assert {e.payload["external_id"] for e in events} == {"1001", "1002"}
