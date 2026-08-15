"""Simulation engine — the world the business system operates on.

Three disciplines make this an honest development environment rather than a
hall of mirrors:

1. GROUNDED — scenarios are assembled from real components (published rates,
   real domain vocabulary, observed friction patterns), never improvised.
2. ADVERSARIAL — the generator's objective is to break the system, not to look
   realistic. Realism is unfalsifiable without a live business; breakage is not.
3. PROTOCOL-IDENTICAL — emits the same `BusinessEvent` the orchestrator consumes
   in production. No business-logic path may branch on whether input is
   simulated.
"""

from ai_bos.simulation.clock import SimClock
from ai_bos.simulation.personas import Persona, PersonaPool
from ai_bos.simulation.scenarios import SCENARIO_CATALOG, Scenario, ScenarioCategory
from ai_bos.simulation.generator import EventGenerator
from ai_bos.simulation.harness import SimulationHarness, SimulationReport

__all__ = [
    "SimClock",
    "Persona",
    "PersonaPool",
    "Scenario",
    "ScenarioCategory",
    "SCENARIO_CATALOG",
    "EventGenerator",
    "SimulationHarness",
    "SimulationReport",
]
