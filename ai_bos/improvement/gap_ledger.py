"""Turns blocked work into a ranked interview script for the owner.

Every case that stalls on a missing fact is a question worth asking. Collected
and deduplicated, they become a prioritised list grounded in situations that
actually happened — which is a far better prompt than "tell me about your
business", because each entry can be answered in seconds by pointing at the
case that produced it.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field

from ai_bos.cases.engine import CaseEngine
from ai_bos.logging_config import log


@dataclass
class GapQuestion:
    fact_key: str
    blocked_case_ids: list[uuid.UUID] = field(default_factory=list)
    example_summaries: list[str] = field(default_factory=list)
    case_types: set[str] = field(default_factory=set)
    oldest_blocked_seconds: float = 0.0

    @property
    def distinct_case_types(self) -> int:
        return len(self.case_types)

    def as_question(self) -> str:
        readable = self.fact_key.replace("_", " ")
        return f"What is the business's {readable}?"


class GapLedger:
    """Reads BLOCKED cases and produces owner questions."""

    def __init__(self, case_engine: CaseEngine) -> None:
        self.case_engine = case_engine

    async def collect(self, now) -> list[GapQuestion]:
        blocked = await self.case_engine.blocked_cases()
        by_fact: dict[str, GapQuestion] = defaultdict(lambda: GapQuestion(fact_key=""))

        for case in blocked:
            for fact in case.missing_facts or ["unspecified"]:
                entry = by_fact[fact]
                entry.fact_key = fact
                entry.blocked_case_ids.append(case.case_id)
                entry.case_types.add(case.case_type)
                if len(entry.example_summaries) < 3 and case.summary:
                    if case.summary not in entry.example_summaries:
                        entry.example_summaries.append(case.summary)
                entry.oldest_blocked_seconds = max(
                    entry.oldest_blocked_seconds, case.dwell_seconds(now)
                )

        questions = list(by_fact.values())
        log.info("gap_ledger.collected", questions=len(questions), blocked_cases=len(blocked))
        return self.rank(questions)

    @staticmethod
    def rank(questions: list[GapQuestion]) -> list[GapQuestion]:
        """Rank by breadth of impact, then by how long work has been stuck.

        Deliberately not by raw count. In simulation, frequency reflects the
        generator's configuration rather than real demand; in production, one
        noisy customer would otherwise dominate the list. How many *kinds* of
        work a missing fact blocks is the honest signal.
        """
        return sorted(
            questions,
            key=lambda q: (-q.distinct_case_types, -q.oldest_blocked_seconds, q.fact_key),
        )

    async def as_owner_script(self, now) -> str:
        questions = await self.collect(now)
        if not questions:
            return "No blocked work. Nothing to ask about."

        lines = ["Questions blocking work, most impactful first:", ""]
        for i, q in enumerate(questions, 1):
            blocked = len(q.blocked_case_ids)
            lines.append(f"{i}. {q.as_question()}")
            lines.append(
                f"   blocking {blocked} case(s) across "
                f"{q.distinct_case_types} type(s) of work"
            )
            for example in q.example_summaries[:2]:
                lines.append(f"   e.g. {example[:80]}")
            lines.append("")
        return "\n".join(lines)
