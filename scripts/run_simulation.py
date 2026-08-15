"""Run the simulation engine against a handler and print the report.

Default handler is deliberately naive — it does what an unguarded LLM agent
does: answer helpfully, always. The point is to show the failures the catalog
surfaces before any of the real system is wired in.

    python scripts/run_simulation.py [--days 20] [--seed 0]
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from datetime import datetime, timezone

from ai_bos.logging_config import configure_logging
from ai_bos.simulation.generator import GeneratedEvent
from ai_bos.simulation.harness import SimulationHarness


async def naive_handler(generated: GeneratedEvent) -> dict:
    """A helpful assistant with no guardrails.

    It answers whatever it is asked, which satisfies almost nothing the
    catalog demands. This is the baseline the real system has to beat.
    """
    text = generated.surface_text.lower()
    held: list[str] = []
    gap: str | None = None

    # It does manage the trivial case: a bare stop keyword looks like a command.
    if text.strip() in {"stop", "unsubscribe", "stop texting me"}:
        held += [
            "opt_out_honored_immediately",
            "no_further_marketing_sends",
            "no_conversational_reply_to_stop_keyword",
        ]

    # And it notices when a message is obviously about another industry.
    if any(w in text for w in ("tire", "prescription", "rotation")):
        held += ["recognizes_out_of_domain", "does_not_invent_matching_service"]

    # Everything else it answers confidently — including policy it does not know.
    if any(w in text for w in ("payment plan", "discount", "how much", "cost")):
        gap = "pricing_and_payment_policy_unknown"

    return {"assertions_held": held, "gap": gap, "escalated": False}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=20)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--events-per-day", type=int, default=12)
    args = parser.parse_args()

    configure_logging("WARNING")  # keep the report readable

    harness = SimulationHarness(
        business_id=uuid.uuid4(),
        start=datetime(2026, 1, 5, 8, 0, tzinfo=timezone.utc),
        seed=args.seed,
    )
    report = await harness.run(
        naive_handler, days=args.days, events_per_day=args.events_per_day
    )

    print()
    print(report.summary())

    if report.failures:
        print()
        print("Sample failures")
        print("-" * 46)
        seen: set[str] = set()
        for f in report.failures:
            if f.scenario_id in seen:
                continue
            seen.add(f.scenario_id)
            print(f"\n  {f.scenario_id}  [{f.assertion}]")
            print(f"    inbound : {f.surface_text[:88]}")
            print(f"    trap    : {f.trap[:88]}")
            if len(seen) >= 6:
                break

    if report.gaps:
        print()
        print("Gap ledger — questions for the owner")
        print("-" * 46)
        for g in report.ranked_gaps():
            print(f"  {g.situation}  (seen {g.times_seen}x)")
            for ex in g.example_texts[:2]:
                print(f"      e.g. {ex[:76]}")


if __name__ == "__main__":
    asyncio.run(main())
