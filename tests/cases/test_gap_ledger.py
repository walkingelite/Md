"""Gap ledger: blocked cases become a ranked owner interview script."""

import uuid
from datetime import datetime, timedelta, timezone

from ai_bos.cases.engine import CaseEngine
from ai_bos.cases.states import CaseState
from ai_bos.cases.store import InMemoryCaseStore
from ai_bos.cases.verticals.healthcare import dental_registry
from ai_bos.improvement.gap_ledger import GapLedger

T0 = datetime(2026, 5, 4, 9, 0, tzinfo=timezone.utc)


def _engine() -> CaseEngine:
    return CaseEngine(
        business_id=uuid.uuid4(),
        store=InMemoryCaseStore(),
        registry=dental_registry(),
    )


async def _block(engine: CaseEngine, case_type: str, summary: str, facts: list[str], at=T0):
    case = await engine.open_case(case_type=case_type, summary=summary, now=at)
    await engine.transition(case, CaseState.BLOCKED, at, missing_facts=facts)
    return case


async def test_no_blocked_cases_yields_no_questions():
    ledger = GapLedger(_engine())
    assert await ledger.collect(T0) == []
    assert "Nothing to ask" in await ledger.as_owner_script(T0)


async def test_blocked_case_becomes_a_question():
    engine = _engine()
    await _block(engine, "general_inquiry", "payment plans?", ["payment_plan_policy"])

    questions = await GapLedger(engine).collect(T0 + timedelta(hours=1))
    assert len(questions) == 1
    assert questions[0].fact_key == "payment_plan_policy"
    assert "payment plan policy" in questions[0].as_question()


async def test_same_fact_across_cases_is_deduplicated():
    engine = _engine()
    for i in range(4):
        await _block(engine, "general_inquiry", f"question {i}", ["fee_schedule"])

    questions = await GapLedger(engine).collect(T0 + timedelta(hours=1))
    assert len(questions) == 1
    assert len(questions[0].blocked_case_ids) == 4
    assert len(questions[0].example_summaries) <= 3


async def test_ranking_prefers_breadth_over_volume():
    """A fact blocking three kinds of work outranks one blocking ten cases of
    a single kind — volume in simulation reflects generator config, not demand."""
    engine = _engine()
    for i in range(10):
        await _block(engine, "general_inquiry", f"q{i}", ["narrow_fact"])
    for case_type in ("appointment_request", "payment_collection", "records_request"):
        await _block(engine, case_type, f"{case_type} blocked", ["broad_fact"])

    questions = await GapLedger(engine).collect(T0 + timedelta(hours=1))
    assert questions[0].fact_key == "broad_fact"
    assert questions[0].distinct_case_types == 3
    assert questions[1].fact_key == "narrow_fact"


async def test_older_blockage_ranks_higher_at_equal_breadth():
    engine = _engine()
    await _block(engine, "general_inquiry", "recent", ["recent_fact"], at=T0)
    await _block(
        engine, "general_inquiry", "ancient", ["ancient_fact"], at=T0 - timedelta(days=30)
    )

    questions = await GapLedger(engine).collect(T0 + timedelta(hours=1))
    assert questions[0].fact_key == "ancient_fact"


async def test_owner_script_is_readable():
    engine = _engine()
    await _block(engine, "general_inquiry", "do you offer payment plans?", ["payment_plan_policy"])
    script = await GapLedger(engine).as_owner_script(T0 + timedelta(hours=1))

    assert "payment plan policy" in script
    assert "blocking 1 case" in script
    assert "do you offer payment plans?" in script


async def test_resolved_blockage_leaves_the_ledger():
    engine = _engine()
    case = await _block(engine, "general_inquiry", "q", ["some_fact"])
    assert len(await GapLedger(engine).collect(T0)) == 1

    await engine.transition(case, CaseState.OPEN, T0 + timedelta(hours=2))
    assert await GapLedger(engine).collect(T0 + timedelta(hours=3)) == []
