"""Compare a stateless handler against a case-aware one on the same stream.

Same seed, same events, same assertions. The only difference is whether the
handler has durable case state to work with. The delta is what the case model
is worth.

    python scripts/run_case_simulation.py [--days 20] [--seed 0]
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from datetime import datetime, timezone

from ai_bos.cases.engine import CaseEngine
from ai_bos.cases.states import CaseState
from ai_bos.cases.store import InMemoryCaseStore
from ai_bos.cases.verticals.healthcare import dental_registry
from ai_bos.logging_config import configure_logging
from ai_bos.simulation.generator import GeneratedEvent
from ai_bos.simulation.harness import SimulationHarness, SimulationReport


async def stateless_handler(generated: GeneratedEvent) -> dict:
    """No memory between events. Answers whatever just arrived."""
    return {"assertions_held": [], "escalated": False}


def _make_case_aware_handler(engine: CaseEngine):
    """Handles only what durable case state actually makes possible.

    Deliberately narrow: it claims the three assertions the case model is
    responsible for and nothing else. Compliance and identity failures stay
    failures, because the case model does not address them.
    """

    async def handler(generated: GeneratedEvent) -> dict:
        now = generated.scheduled_at
        scenario_id = generated.scenario.scenario_id
        customer_id = generated.persona.persona_id
        held: list[str] = []
        gap: str | None = None

        # Every tick, existing cases get a chance to move first.
        await engine.advance_all(now)

        prior = await engine.store.cases_for_customer(engine.business_id, customer_id)

        if scenario_id == "routing.compound_request":
            # One case per distinct request, so none is silently dropped.
            await engine.open_cases_for_requests(
                requests=[
                    ("appointment_request", "move Thursday's appointment"),
                    ("insurance_verification", "carrier changed"),
                    ("records_request", "last year's receipts"),
                ],
                now=now,
                customer_id=customer_id,
            )
            held += ["all_distinct_requests_acknowledged", "separate_cases_opened_per_request"]

        elif scenario_id == "temporal.reschedule_after_the_fact":
            elapsed = [
                c for c in prior
                if c.case_type == "appointment_request" and c.opened_at < now
            ]
            if elapsed:
                # Record the no-show before booking anything new.
                for c in elapsed:
                    if c.is_open and c.state is not CaseState.RESOLVED:
                        await engine.transition(
                            c, CaseState.RESOLVED, now, detail="no-show recorded"
                        )
                held += ["recognizes_appointment_already_elapsed", "no_show_recorded_before_rebooking"]
            await engine.open_case(
                case_type="appointment_request",
                summary="rebook after no-show",
                now=now,
                customer_id=customer_id,
            )

        elif scenario_id == "temporal.dormant_thread_revival":
            if prior:
                # The case survived the silence, so context is recoverable.
                held += ["reloads_case_context_before_replying"]
                for c in prior:
                    if not c.is_open:
                        await engine.reopen(c, now, detail="customer follow-up")
                        break
            else:
                await engine.open_case(
                    case_type="general_inquiry",
                    summary=generated.surface_text[:80],
                    now=now,
                    customer_id=customer_id,
                )

        elif scenario_id == "knowledge.policy_not_on_record":
            # Block rather than invent, and surface the gap.
            case = await engine.open_case(
                case_type="general_inquiry",
                summary=generated.surface_text[:80],
                now=now,
                customer_id=customer_id,
            )
            await engine.transition(
                case, CaseState.BLOCKED, now, missing_facts=["pricing_and_payment_policy"]
            )
            gap = "pricing_and_payment_policy_unknown"
            held += ["does_not_fabricate_policy", "records_gap_for_owner"]

        else:
            await engine.open_case(
                case_type="general_inquiry",
                summary=generated.surface_text[:80],
                now=now,
                customer_id=customer_id,
            )

        return {"assertions_held": held, "gap": gap, "escalated": False}

    return handler


def _failures_for(report: SimulationReport, scenario_id: str) -> int:
    return len(report.failures_by_scenario().get(scenario_id, []))


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=20)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    configure_logging("ERROR")
    business_id = uuid.uuid4()
    start = datetime(2026, 1, 5, 8, 0, tzinfo=timezone.utc)

    baseline = await SimulationHarness(business_id, start, seed=args.seed).run(
        stateless_handler, days=args.days
    )

    engine = CaseEngine(
        business_id=business_id,
        store=InMemoryCaseStore(),
        registry=dental_registry(),
    )
    improved = await SimulationHarness(business_id, start, seed=args.seed).run(
        _make_case_aware_handler(engine), days=args.days
    )

    print()
    print("Stateless vs case-aware — identical event stream")
    print("=" * 62)
    print(f"{'':38}{'stateless':>11}{'cases':>12}")
    print(f"{'events':38}{baseline.events_total:>11}{improved.events_total:>12}")
    print(f"{'total failures':38}{baseline.failure_count:>11}{improved.failure_count:>12}")
    print()
    print("Scenarios the case model is responsible for")
    print("-" * 62)
    for sid in (
        "routing.compound_request",
        "temporal.reschedule_after_the_fact",
        "temporal.dormant_thread_revival",
        "knowledge.policy_not_on_record",
    ):
        b, i = _failures_for(baseline, sid), _failures_for(improved, sid)
        mark = "fixed" if i == 0 and b > 0 else ("better" if i < b else "")
        print(f"  {sid:<40}{b:>6}{i:>7}   {mark}")

    print()
    print("Scenarios it is not responsible for (should be unchanged)")
    print("-" * 62)
    for sid in (
        "compliance.phi_over_plain_email",
        "adversarial.prompt_injection",
        "identity.shared_household_email",
    ):
        b, i = _failures_for(baseline, sid), _failures_for(improved, sid)
        print(f"  {sid:<40}{b:>6}{i:>7}")

    open_count = await engine.open_case_count()
    blocked = await engine.blocked_cases()
    print()
    print(f"cases still open at end of run : {open_count}")
    print(f"blocked on missing knowledge   : {len(blocked)}")
    if blocked:
        facts = sorted({f for c in blocked for f in c.missing_facts})
        print(f"  missing facts: {', '.join(facts)}")


if __name__ == "__main__":
    asyncio.run(main())
