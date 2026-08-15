"""Store semantics — isolation and querying."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from ai_bos.cases.states import CaseState
from ai_bos.cases.store import Case, InMemoryCaseStore

T0 = datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc)


async def test_stored_case_is_isolated_from_caller_mutation():
    """A caller editing a returned case must not corrupt stored state."""
    store = InMemoryCaseStore()
    bid = uuid.uuid4()
    case = Case(business_id=bid, summary="original", opened_at=T0)
    await store.add(case)

    fetched = await store.get(case.case_id)
    fetched.summary = "mutated"
    fetched.context["injected"] = True
    fetched.missing_facts.append("nope")

    again = await store.get(case.case_id)
    assert again.summary == "original"
    assert "injected" not in again.context
    assert again.missing_facts == []


async def test_add_rejects_duplicate_ids():
    store = InMemoryCaseStore()
    case = Case(business_id=uuid.uuid4())
    await store.add(case)
    with pytest.raises(ValueError):
        await store.add(case)


async def test_update_requires_existing_case():
    store = InMemoryCaseStore()
    with pytest.raises(KeyError):
        await store.update(Case(business_id=uuid.uuid4()))


async def test_open_cases_excludes_terminal_and_other_businesses():
    store = InMemoryCaseStore()
    mine, theirs = uuid.uuid4(), uuid.uuid4()
    await store.add(Case(business_id=mine, state=CaseState.OPEN))
    await store.add(Case(business_id=mine, state=CaseState.RESOLVED))
    await store.add(Case(business_id=theirs, state=CaseState.OPEN))

    open_cases = await store.open_cases(mine)
    assert len(open_cases) == 1


async def test_due_cases_respects_schedule_and_priority():
    store = InMemoryCaseStore()
    bid = uuid.uuid4()
    await store.add(
        Case(business_id=bid, priority=9, next_action_at=T0 - timedelta(hours=1))
    )
    await store.add(
        Case(business_id=bid, priority=1, next_action_at=T0 - timedelta(hours=1))
    )
    await store.add(
        Case(business_id=bid, priority=1, next_action_at=T0 + timedelta(hours=1))
    )

    due = await store.due_cases(bid, T0)
    assert len(due) == 2
    assert due[0].priority == 1


async def test_cases_without_schedule_are_never_due():
    store = InMemoryCaseStore()
    bid = uuid.uuid4()
    await store.add(Case(business_id=bid, next_action_at=None))
    assert await store.due_cases(bid, T0) == []


async def test_cases_for_customer_filters_correctly():
    store = InMemoryCaseStore()
    bid, cid = uuid.uuid4(), uuid.uuid4()
    await store.add(Case(business_id=bid, customer_id=cid))
    await store.add(Case(business_id=bid, customer_id=uuid.uuid4()))
    assert len(await store.cases_for_customer(bid, cid)) == 1
