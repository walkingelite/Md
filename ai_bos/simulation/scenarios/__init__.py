"""Scenario types and catalog assembly.

The catalog splits the way the case registry does: a universal core every
customer-facing business faces, plus vertical packs that add industry-specific
situations. Catalogs are instances rather than module globals so one process
can run a dental simulation and a trades simulation without interference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ScenarioCategory(str, Enum):
    IDENTITY = "identity"
    COMPLIANCE = "compliance"
    KNOWLEDGE_GAP = "knowledge_gap"
    TEMPORAL = "temporal"
    EMOTIONAL = "emotional"
    ROUTING = "routing"
    ADVERSARIAL_INPUT = "adversarial_input"


class Difficulty(str, Enum):
    BASELINE = "baseline"   # a competent system handles this
    HARD = "hard"           # naive implementations fail
    BRUTAL = "brutal"       # requires explicit design to survive


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    category: ScenarioCategory
    difficulty: Difficulty
    channel: str                      # EMAIL | SMS | VOICE
    templates: tuple[str, ...]        # {name} is filled at generation time
    trap: str                         # how a naive system fails this
    must_hold: tuple[str, ...]        # assertions the harness checks
    requires_prior_context: bool = False
    tags: tuple[str, ...] = field(default_factory=tuple)
    vertical: str = "core"            # provenance, for reporting


class ScenarioCatalog:
    """An assembled set of scenarios for one simulation run."""

    def __init__(self, scenarios: list[Scenario] | None = None) -> None:
        self._by_id: dict[str, Scenario] = {}
        for s in scenarios or []:
            self.register(s)

    def register(self, scenario: Scenario) -> None:
        if scenario.scenario_id in self._by_id:
            raise ValueError(f"Duplicate scenario id: {scenario.scenario_id}")
        self._by_id[scenario.scenario_id] = scenario

    def extend(self, scenarios: list[Scenario]) -> "ScenarioCatalog":
        for s in scenarios:
            self.register(s)
        return self

    def get(self, scenario_id: str) -> Scenario | None:
        return self._by_id.get(scenario_id)

    def all(self) -> tuple[Scenario, ...]:
        return tuple(self._by_id.values())

    def by_category(self, category: ScenarioCategory) -> tuple[Scenario, ...]:
        return tuple(s for s in self._by_id.values() if s.category is category)

    def by_difficulty(self, difficulty: Difficulty) -> tuple[Scenario, ...]:
        return tuple(s for s in self._by_id.values() if s.difficulty is difficulty)

    def by_vertical(self, vertical: str) -> tuple[Scenario, ...]:
        return tuple(s for s in self._by_id.values() if s.vertical == vertical)

    def all_assertions(self) -> frozenset[str]:
        """Every distinct property this catalog checks — the system's report card."""
        return frozenset(a for s in self._by_id.values() for a in s.must_hold)

    def __len__(self) -> int:
        return len(self._by_id)

    def __iter__(self):
        return iter(self._by_id.values())

    def __contains__(self, scenario_id: object) -> bool:
        return scenario_id in self._by_id


def core_catalog() -> ScenarioCatalog:
    """Universal scenarios only — valid for any customer-facing business."""
    from ai_bos.simulation.scenarios.core import CORE_SCENARIOS

    return ScenarioCatalog(list(CORE_SCENARIOS))


__all__ = [
    "Scenario",
    "ScenarioCategory",
    "Difficulty",
    "ScenarioCatalog",
    "core_catalog",
]
