"""Case engine: opening, transitions, and the advance cycle."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from ai_bos.cases.engine import CaseEngine
from ai_bos.cases.states import CaseState, InvalidTransition
from ai_bos.cases.store import InMemoryCaseStore
from ai_bos.cases.verticals.healthcare import dental_registry

T0 = datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc)


def _engine() -> CaseEngine:
    return CaseEngine(
        business_id=uuid.uuid4(),
        store=InMemoryCaseStore(),
        registry=dental_registry(),
    )


async def test_open_case_schedules_next_action():
    eng = _engine()
    case = await eng.open_case(
        case_type="appointment_request", summary="wants Thursday", now=T0
    )
    assert case.state is CaseState.OPEN
    assert case.next_action_at is not None
    assert case.next_action_at > T0
    assert case.events[0].kind == "opened"


async def test_open_unknown_case_type_raises():
    eng = _engine()
    with pytest.raises(KeyError):
        await eng.open_case(case_type="nonsense", summary="x", now=T0)


async def test_compound_request_opens_one_case_each():
    """The failure this prevents: answering the first ask and dropping the rest."""
    eng = _engine()
    cases = await eng.open_cases_for_requests(
        requests=[
            ("appointment_request", "move Thursday"),
            ("insurance_verification", "carrier changed"),
            ("records_request", "last year's receipts"),
        ],
        now=T0,
        customer_id=uuid.uuid4(),
    )
    assert len(cases) == 3
    assert {c.case_type for c in cases} == {
        "appointment_request",
        "insurance_verification",
        "records_request",
    }
    assert await eng.open_case_count() == 3


async def test_invalid_transition_is_rejected():
    eng = _engine()
    case = await eng.open_case(case_type="general_inquiry", summary="q", now=T0)
    await eng.transition(case, CaseState.BLOCKED, T0, missing_facts=["pricing"])
    with pytest.raises(InvalidTransition):
        await eng.transition(case, CaseState.RESOLVED, T0)


async def test_terminal_transition_clears_schedule():
    eng = _engine()
    case = await eng.open_case(case_type="general_inquiry", summary="q", now=T0)
    case = await eng.transition(case, CaseState.RESOLVED, T0)
    assert case.next_action_at is None
    assert case.closed_at == T0
    assert not case.is_open


async def test_blocked_records_and_clears_missing_facts():
    eng = _engine()
    case = await eng.open_case(case_type="general_inquiry", summary="q", now=T0)
    case = await eng.transition(
        case, CaseState.BLOCKED, T0, missing_facts=["payment_plan_policy"]
    )
    assert case.missing_facts == ["payment_plan_policy"]

    case = await eng.transition(case, CaseState.OPEN, T0 + timedelta(hours=1))
    assert case.missing_facts == []


async def test_waiting_case_is_not_advanced_before_its_limit():
    """A case awaiting an insurer must sit quietly, not be chased daily."""
    eng = _engine()
    case = await eng.open_case(
        case_type="insurance_verification", summary="verify", now=T0
    )
    await eng.transition(case, CaseState.WAITING_EXTERNAL, T0)

    result = await eng.advance_all(T0 + timedelta(days=4))
    assert result.timed_out == 0
    stored = await eng.store.get(case.case_id)
    assert stored.state is CaseState.WAITING_EXTERNAL


async def test_waiting_case_escalates_after_its_limit():
    """Day 11 on a ten-day limit: the owner hears about it."""
    eng = _engine()
    case = await eng.open_case(
        case_type="insurance_verification", summary="verify", now=T0
    )
    await eng.transition(case, CaseState.WAITING_EXTERNAL, T0)

    result = await eng.advance_all(T0 + timedelta(days=11))
    assert result.timed_out == 1
    assert result.escalated == 1
    stored = await eng.store.get(case.case_id)
    assert stored.state is CaseState.WAITING_OWNER


async def test_dormant_case_survives_long_silence():
    """Months of nothing must not lose the case — the revival scenario."""
    eng = _engine()
    case = await eng.open_case(
        case_type="records_request", summary="records", now=T0
    )
    await eng.transition(case, CaseState.WAITING_OWNER, T0)

    await eng.advance_all(T0 + timedelta(days=90))
    stored = await eng.store.get(case.case_id)
    assert stored is not None
    assert stored.is_open
    assert len(stored.events) >= 2


async def test_reopen_after_resolution():
    eng = _engine()
    case = await eng.open_case(case_type="general_inquiry", summary="q", now=T0)
    case = await eng.transition(case, CaseState.RESOLVED, T0)

    assert case.closed_at == T0

    later = T0 + timedelta(days=40)
    case = await eng.reopen(case, later, detail="customer followed up")
    assert case.state is CaseState.OPEN
    assert case.is_open
    # A reopened case that still carries a close stamp reads as both open and
    # closed, and corrupts every "resolved this month" figure downstream.
    assert case.closed_at is None
    assert case.next_action_at is not None


async def test_advance_orders_by_priority():
    """Urgent clinical work is examined before routine recalls."""
    eng = _engine()
    await eng.open_case(case_type="recall_scheduling", summary="recall", now=T0)
    urgent = await eng.open_case(
        case_type="clinical_urgency", summary="swelling", now=T0
    )
    result = await eng.advance_all(T0 + timedelta(days=8))
    assert result.examined >= 2
    assert result.touched_case_ids[0] == urgent.case_id


async def test_clinical_urgency_escalates_rather_than_closing():
    eng = _engine()
    case = await eng.open_case(
        case_type="clinical_urgency", summary="swelling", now=T0
    )
    result = await eng.advance_all(T0 + timedelta(minutes=10))
    assert result.escalated == 1
    stored = await eng.store.get(case.case_id)
    assert stored.state is CaseState.WAITING_OWNER
    assert stored.state is not CaseState.ABANDONED


async def test_blocked_cases_are_queryable_for_the_gap_ledger():
    eng = _engine()
    c1 = await eng.open_case(case_type="general_inquiry", summary="pricing?", now=T0)
    await eng.transition(c1, CaseState.BLOCKED, T0, missing_facts=["fee_schedule"])
    c2 = await eng.open_case(case_type="general_inquiry", summary="hours?", now=T0)

    blocked = await eng.blocked_cases()
    assert len(blocked) == 1
    assert blocked[0].missing_facts == ["fee_schedule"]


async def test_events_form_an_audit_trail():
    eng = _engine()
    case = await eng.open_case(case_type="appointment_request", summary="book", now=T0)
    case = await eng.transition(case, CaseState.WAITING_CUSTOMER, T0 + timedelta(minutes=5))
    case = await eng.transition(case, CaseState.OPEN, T0 + timedelta(hours=3))
    case = await eng.transition(case, CaseState.RESOLVED, T0 + timedelta(hours=4))

    kinds = [e.kind for e in case.events]
    assert kinds[0] == "opened"
    assert kinds.count("transitioned") == 3
    assert case.events[-1].to_state is CaseState.RESOLVED
    times = [e.occurred_at for e in case.events]
    assert times == sorted(times)
