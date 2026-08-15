"""Runs a generated stream past a handler and reports what broke.

The report is the product. Its two headline numbers are the failure count
(assertions the handler did not satisfy) and the coverage figure (how much of
the catalog the run actually exercised). A run that finds nothing is a warning
about the generator, not a clean bill of health for the system.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime

from ai_bos.logging_config import log
from ai_bos.simulation.clock import SimClock
from ai_bos.simulation.generator import EventGenerator, GeneratedEvent
from ai_bos.simulation.scenarios import SCENARIO_CATALOG, all_assertions

# A handler takes the event payload and returns whatever the system did:
#   {"assertions_held": [...], "response_text": ..., "escalated": bool, ...}
Handler = Callable[[GeneratedEvent], Awaitable[dict]]


@dataclass
class Failure:
    scenario_id: str
    assertion: str
    persona_id: uuid.UUID
    occurred_at: datetime
    surface_text: str
    trap: str


@dataclass
class GapEntry:
    """A situation the system could not resolve. Seeds the owner interview."""

    situation: str
    scenario_id: str
    times_seen: int = 0
    example_texts: list[str] = field(default_factory=list)


@dataclass
class SimulationReport:
    events_total: int = 0
    events_handled: int = 0
    handler_errors: int = 0
    failures: list[Failure] = field(default_factory=list)
    gaps: dict[str, GapEntry] = field(default_factory=dict)
    scenarios_seen: Counter = field(default_factory=Counter)
    escalations: int = 0

    @property
    def failure_count(self) -> int:
        return len(self.failures)

    @property
    def catalog_coverage(self) -> float:
        """Share of the catalog this run actually exercised."""
        return len(self.scenarios_seen) / len(SCENARIO_CATALOG) if SCENARIO_CATALOG else 0.0

    @property
    def assertion_coverage(self) -> float:
        exercised = {f.assertion for f in self.failures}
        checked = all_assertions()
        return len(exercised) / len(checked) if checked else 0.0

    def failures_by_scenario(self) -> dict[str, list[Failure]]:
        grouped: dict[str, list[Failure]] = defaultdict(list)
        for f in self.failures:
            grouped[f.scenario_id].append(f)
        return dict(grouped)

    def ranked_gaps(self) -> list[GapEntry]:
        """Distinct situation types, not raw counts.

        Simulated frequency reflects the generator's configuration, never real
        demand — ranking by count would be reading our own handwriting back.
        """
        return sorted(self.gaps.values(), key=lambda g: g.situation)

    def summary(self) -> str:
        lines = [
            "Simulation report",
            "=" * 46,
            f"events generated     {self.events_total}",
            f"events handled       {self.events_handled}",
            f"handler errors       {self.handler_errors}",
            f"escalations          {self.escalations}",
            f"failures found       {self.failure_count}",
            f"catalog coverage     {self.catalog_coverage:.0%}"
            f" ({len(self.scenarios_seen)}/{len(SCENARIO_CATALOG)} scenarios)",
            f"distinct gaps        {len(self.gaps)}",
        ]
        if self.failures:
            lines += ["", "Top failing scenarios:"]
            worst = Counter(f.scenario_id for f in self.failures).most_common(5)
            lines += [f"  {sid:<44} {n:>3}" for sid, n in worst]
        if self.catalog_coverage < 0.8:
            lines += [
                "",
                "! Coverage below 80% — extend the run or rebalance difficulty",
                "  weights before trusting the failure count.",
            ]
        return "\n".join(lines)


class SimulationHarness:
    def __init__(
        self,
        business_id: uuid.UUID,
        start: datetime,
        seed: int = 0,
    ) -> None:
        self.business_id = business_id
        self.clock = SimClock(start=start)
        self.seed = seed
        self.generator = EventGenerator(
            clock=self.clock, business_id=business_id, seed=seed
        )

    async def run(
        self,
        handler: Handler,
        days: int = 20,
        events_per_day: int = 12,
    ) -> SimulationReport:
        stream = self.generator.generate_days(days, events_per_day)
        report = SimulationReport(events_total=len(stream))

        log.info(
            "simulation.start",
            business_id=str(self.business_id),
            days=days,
            events=len(stream),
            seed=self.seed,
        )

        for generated in stream:
            self.clock.advance_to(generated.scheduled_at)
            report.scenarios_seen[generated.scenario.scenario_id] += 1

            try:
                result = await handler(generated)
            except Exception as exc:
                report.handler_errors += 1
                log.warning(
                    "simulation.handler_error",
                    scenario=generated.scenario.scenario_id,
                    error=str(exc),
                )
                continue

            report.events_handled += 1
            self._evaluate(generated, result, report)

        log.info(
            "simulation.complete",
            failures=report.failure_count,
            coverage=round(report.catalog_coverage, 3),
            gaps=len(report.gaps),
        )
        return report

    def _evaluate(
        self, generated: GeneratedEvent, result: dict, report: SimulationReport
    ) -> None:
        held = set(result.get("assertions_held") or [])

        for assertion in generated.scenario.must_hold:
            if assertion not in held:
                report.failures.append(
                    Failure(
                        scenario_id=generated.scenario.scenario_id,
                        assertion=assertion,
                        persona_id=generated.persona.persona_id,
                        occurred_at=generated.scheduled_at,
                        surface_text=generated.surface_text,
                        trap=generated.scenario.trap,
                    )
                )

        if result.get("escalated"):
            report.escalations += 1

        gap = result.get("gap")
        if gap:
            entry = report.gaps.get(gap)
            if entry is None:
                entry = GapEntry(situation=gap, scenario_id=generated.scenario.scenario_id)
                report.gaps[gap] = entry
            entry.times_seen += 1
            if (
                len(entry.example_texts) < 3
                and generated.surface_text not in entry.example_texts
            ):
                entry.example_texts.append(generated.surface_text)
