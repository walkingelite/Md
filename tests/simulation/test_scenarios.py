"""Catalog integrity and the core/vertical split.

A malformed scenario silently stops testing anything, and a core catalog that
leaks industry vocabulary silently stops being reusable.
"""

import pytest

from ai_bos.simulation.scenarios import (
    Difficulty,
    Scenario,
    ScenarioCatalog,
    ScenarioCategory,
    core_catalog,
)
from ai_bos.simulation.scenarios.verticals.healthcare import (
    HEALTHCARE_SCENARIOS,
    dental_catalog,
)


# ------------------------------------------------------------------- integrity

def test_core_catalog_is_substantial():
    assert len(core_catalog()) >= 12


def test_scenario_ids_are_unique():
    ids = [s.scenario_id for s in dental_catalog()]
    assert len(ids) == len(set(ids))


def test_catalog_rejects_duplicates():
    catalog = core_catalog()
    existing = catalog.all()[0]
    with pytest.raises(ValueError):
        catalog.register(existing)


def test_every_scenario_has_templates_trap_and_assertions():
    for s in dental_catalog():
        assert s.templates, f"{s.scenario_id} has no templates"
        assert s.trap.strip(), f"{s.scenario_id} has no trap description"
        assert s.must_hold, f"{s.scenario_id} asserts nothing — it cannot fail"


def test_channels_are_valid():
    for s in dental_catalog():
        assert s.channel in {"EMAIL", "SMS", "VOICE"}


def test_hard_cases_dominate():
    """The catalog exists to find failures, so it should not be mostly easy."""
    catalog = dental_catalog()
    baseline = len(catalog.by_difficulty(Difficulty.BASELINE))
    assert baseline / len(catalog) < 0.35


# ------------------------------------------------------------ core/vertical split

def test_core_catalog_contains_no_industry_vocabulary():
    """The whole point of the split. If dental words leak into core, the
    catalog silently stops being reusable for other verticals."""
    banned = (
        "patient", "dental", "dentist", "clinical", "diagnosis", "x-ray",
        "hipaa", "insurance", "tooth", "crown", "cleaning", "prescription",
    )
    for s in core_catalog():
        haystack = " ".join(
            (s.scenario_id, s.trap, *s.templates, *s.must_hold, *s.tags)
        ).lower()
        for word in banned:
            # "prescription" appears legitimately in routing.misdirected, where
            # the point is that the message belongs to a different business.
            if word == "prescription" and s.scenario_id == "routing.misdirected":
                continue
            assert word not in haystack, f"{s.scenario_id} leaks '{word}' into core"


def test_every_core_scenario_is_tagged_core():
    assert {s.vertical for s in core_catalog()} == {"core"}


def test_healthcare_pack_is_tagged_and_specific():
    assert all(s.vertical == "healthcare" for s in HEALTHCARE_SCENARIOS)
    tags = {t for s in HEALTHCARE_SCENARIOS for t in s.tags}
    assert "hipaa" in tags


def test_dental_catalog_is_core_plus_pack():
    core, dental = core_catalog(), dental_catalog()
    assert len(dental) == len(core) + len(HEALTHCARE_SCENARIOS)
    for s in core:
        assert s.scenario_id in dental
    assert len(dental.by_vertical("healthcare")) == len(HEALTHCARE_SCENARIOS)


def test_core_catalog_still_covers_universal_risks():
    """A business with no vertical pack must still be tested for the things
    that endanger any business."""
    core = core_catalog()
    for required in (
        "adversarial.prompt_injection",
        "compliance.opt_out",
        "knowledge.policy_not_on_record",
        "routing.compound_request",
    ):
        assert required in core


def test_catalogs_are_independent_instances():
    """Mutating one catalog must not affect another in the same process."""
    a, b = core_catalog(), core_catalog()
    a.register(
        Scenario(
            scenario_id="test.only_in_a",
            category=ScenarioCategory.ROUTING,
            difficulty=Difficulty.BASELINE,
            channel="EMAIL",
            templates=("x",),
            trap="x",
            must_hold=("x",),
        )
    )
    assert "test.only_in_a" in a
    assert "test.only_in_a" not in b


# ------------------------------------------------------------------- queries

def test_by_category_and_difficulty():
    catalog = dental_catalog()
    for category in ScenarioCategory:
        for s in catalog.by_category(category):
            assert s.category is category
    for difficulty in Difficulty:
        for s in catalog.by_difficulty(difficulty):
            assert s.difficulty is difficulty


def test_every_category_is_represented_in_dental():
    catalog = dental_catalog()
    for category in ScenarioCategory:
        assert catalog.by_category(category), f"no scenarios for {category}"


def test_all_assertions_is_deduplicated():
    assertions = dental_catalog().all_assertions()
    assert len(assertions) >= 20
    assert len(assertions) == len(set(assertions))


def test_empty_catalog_is_usable():
    empty = ScenarioCatalog()
    assert len(empty) == 0
    assert empty.all() == ()
    assert empty.all_assertions() == frozenset()
