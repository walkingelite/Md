"""Orchestrator wired to the case engine.

All tests bypass the classifier: classification is passed in directly, so no
model call happens and the case logic is what is actually under test.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from ai_bos.agents.orchestrator import BusinessEvent, EventType, Orchestrator
from ai_bos.cases.engine import CaseEngine
from ai_bos.cases.states import CaseState
from ai_bos.cases.store import InMemoryCaseStore
from ai_bos.cases.verticals.healthcare import dental_registry

T0 = datetime(2026, 4, 6, 9, 0, tzinfo=timezone.utc)


def _orchestrator(with_cases: bool = True) -> Orchestrator:
    business_id = uuid.uuid4()
    engine = (
        CaseEngine(
            business_id=business_id,
            store=InMemoryCaseStore(),
            registry=dental_registry(),
        )
        if with_cases
        else None
    )
    orch = Orchestrator(
        business_id=business_id,
        memory=MagicMock(),
        executor=MagicMock(),
        case_engine=engine,
    )
    return orch


def _event(orch: Orchestrator, customer_id: uuid.UUID | None = None) -> BusinessEvent:
    payload = {"channel": "EMAIL", "text": "hello"}
    if customer_id:
        payload["customer_id"] = str(customer_id)
    return BusinessEvent(
        event_id=uuid.uuid4(),
        business_id=orch.business_id,
        event_type=EventType.INBOUND_EMAIL,
        payload=payload,
    )


async def test_compound_request_opens_one_case_per_request():
    orch = _orchestrator()
    classification = {
        "agent": "communication",
        "requests": [
            {"case_type": "appointment_request", "summary": "move Thursday"},
            {"case_type": "insurance_verification", "summary": "carrier changed"},
            {"case_type": "records_request", "summary": "receipts"},
        ],
    }
    cases = await orch.ensure_cases(_event(orch), classification, T0)

    assert len(cases) == 3
    assert {c.case_type for c in cases} == {
        "appointment_request",
        "insurance_verification",
        "records_request",
    }
    assert await orch.case_engine.open_case_count() == 3


async def test_classification_without_requests_still_opens_one_case():
    """An event that opens no case is an event that can be lost."""
    orch = _orchestrator()
    cases = await orch.ensure_cases(
        _event(orch), {"agent": "communication", "summary": "vague question"}, T0
    )
    assert len(cases) == 1
    assert cases[0].case_type == "general_inquiry"
    assert cases[0].summary == "vague question"


async def test_unknown_case_type_falls_back_rather_than_raising():
    orch = _orchestrator()
    cases = await orch.ensure_cases(
        _event(orch),
        {"requests": [{"case_type": "not_a_real_type", "summary": "x"}]},
        T0,
    )
    assert len(cases) == 1
    assert cases[0].case_type == "general_inquiry"


async def test_customer_reply_resumes_waiting_case():
    """A reply is the awaited event. Left in WAITING_CUSTOMER the case would
    time out into ABANDONED despite the customer having answered."""
    orch = _orchestrator()
    customer_id = uuid.uuid4()

    case = await orch.case_engine.open_case(
        case_type="appointment_request",
        summary="proposed Thursday",
        now=T0,
        customer_id=customer_id,
    )
    await orch.case_engine.transition(case, CaseState.WAITING_CUSTOMER, T0)

    later = T0 + timedelta(hours=6)
    resumed = await orch.ensure_cases(
        _event(orch, customer_id), {"summary": "yes that works"}, later
    )

    assert any(c.case_id == case.case_id for c in resumed)
    stored = await orch.case_engine.store.get(case.case_id)
    assert stored.state is CaseState.OPEN
    assert stored.events[-1].actor == "customer"


async def test_reply_does_not_duplicate_when_no_new_work():
    orch = _orchestrator()
    customer_id = uuid.uuid4()
    case = await orch.case_engine.open_case(
        case_type="general_inquiry", summary="q", now=T0, customer_id=customer_id
    )
    await orch.case_engine.transition(case, CaseState.WAITING_CUSTOMER, T0)

    before = await orch.case_engine.open_case_count()
    await orch.ensure_cases(_event(orch, customer_id), {"summary": "thanks"}, T0)
    assert await orch.case_engine.open_case_count() == before


async def test_new_work_from_known_customer_opens_a_case():
    orch = _orchestrator()
    customer_id = uuid.uuid4()
    case = await orch.case_engine.open_case(
        case_type="general_inquiry", summary="old", now=T0, customer_id=customer_id
    )
    await orch.case_engine.transition(case, CaseState.WAITING_CUSTOMER, T0)

    cases = await orch.ensure_cases(
        _event(orch, customer_id),
        {"requests": [{"case_type": "appointment_request", "summary": "new booking"}]},
        T0 + timedelta(hours=1),
    )
    types = {c.case_type for c in cases}
    assert "appointment_request" in types
    assert await orch.case_engine.open_case_count() == 2


async def test_maintenance_cycle_advances_overdue_cases():
    """Idle time is when waiting cases get chased; without it the system is
    purely reactive.

    The case is opened ten minutes in the past so that its five-minute dwell
    limit has genuinely expired by the time the cycle runs — the cycle uses
    wall-clock now, so a case opened at 'now' is correctly not yet due.
    """
    orch = _orchestrator()
    opened_at = orch._now() - timedelta(minutes=10)
    case = await orch.case_engine.open_case(
        case_type="clinical_urgency", summary="swelling", now=opened_at
    )

    await orch._maintenance_cycle()

    stored = await orch.case_engine.store.get(case.case_id)
    assert stored.state is CaseState.WAITING_OWNER
    # Escalation is the only path for this type — it must never be abandoned.
    assert stored.state is not CaseState.ABANDONED


async def test_maintenance_cycle_leaves_cases_that_are_not_due():
    orch = _orchestrator()
    case = await orch.case_engine.open_case(
        case_type="clinical_urgency", summary="swelling", now=orch._now()
    )
    await orch._maintenance_cycle()

    stored = await orch.case_engine.store.get(case.case_id)
    assert stored.state is CaseState.OPEN


async def test_orchestrator_works_without_a_case_engine():
    """The case layer is optional; absent it, behaviour is the old stateless path."""
    orch = _orchestrator(with_cases=False)
    cases = await orch.ensure_cases(_event(orch), {"summary": "x"}, T0)
    assert cases == []
    await orch._maintenance_cycle()  # must not raise


async def test_malformed_customer_id_is_ignored_not_fatal():
    orch = _orchestrator()
    event = _event(orch)
    event.payload["customer_id"] = "not-a-uuid"
    cases = await orch.ensure_cases(event, {"summary": "x"}, T0)
    assert len(cases) == 1
    assert cases[0].customer_id is None


async def test_available_case_types_reflects_registry():
    orch = _orchestrator()
    types = orch._available_case_types()
    assert "insurance_verification" in types
    assert "general_inquiry" in types

    stateless = _orchestrator(with_cases=False)
    assert stateless._available_case_types() == ["general_inquiry"]
