"""Catalog integrity — a malformed scenario silently stops testing anything."""

from ai_bos.simulation.scenarios import (
    SCENARIO_CATALOG,
    Difficulty,
    ScenarioCategory,
    all_assertions,
    scenarios_by_category,
    scenarios_by_difficulty,
)


def test_catalog_is_not_empty():
    assert len(SCENARIO_CATALOG) >= 15


def test_scenario_ids_are_unique():
    ids = [s.scenario_id for s in SCENARIO_CATALOG]
    assert len(ids) == len(set(ids))


def test_every_scenario_has_templates_trap_and_assertions():
    for s in SCENARIO_CATALOG:
        assert s.templates, f"{s.scenario_id} has no templates"
        assert s.trap.strip(), f"{s.scenario_id} has no trap description"
        assert s.must_hold, f"{s.scenario_id} asserts nothing — it cannot fail"


def test_channels_are_valid():
    for s in SCENARIO_CATALOG:
        assert s.channel in {"EMAIL", "SMS", "VOICE"}


def test_compliance_scenarios_exist_for_each_regime():
    compliance = scenarios_by_category(ScenarioCategory.COMPLIANCE)
    tags = {t for s in compliance for t in s.tags}
    assert "hipaa" in tags
    assert "tcpa" in tags


def test_every_category_is_represented():
    for category in ScenarioCategory:
        assert scenarios_by_category(category), f"no scenarios for {category}"


def test_difficulty_spread():
    for d in Difficulty:
        assert scenarios_by_difficulty(d), f"no scenarios at difficulty {d}"


def test_hard_cases_dominate():
    """The catalog exists to find failures, so it should not be mostly easy."""
    baseline = len(scenarios_by_difficulty(Difficulty.BASELINE))
    assert baseline / len(SCENARIO_CATALOG) < 0.35


def test_assertions_are_deduplicated_across_catalog():
    assertions = all_assertions()
    assert len(assertions) >= 20
