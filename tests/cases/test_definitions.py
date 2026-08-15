"""Case type registry and vertical packs."""

import pytest

from ai_bos.cases.definitions import (
    GENERIC_DEFINITIONS,
    CaseTypeDefinition,
    CaseTypeRegistry,
)
from ai_bos.cases.states import CaseState
from ai_bos.cases.verticals.healthcare import dental_registry


def test_registry_rejects_duplicate_types():
    reg = CaseTypeRegistry()
    d = CaseTypeDefinition(case_type="x", description="x")
    reg.register(d)
    with pytest.raises(ValueError):
        reg.register(d)


def test_require_raises_with_helpful_message():
    reg = CaseTypeRegistry(GENERIC_DEFINITIONS)
    with pytest.raises(KeyError) as exc:
        reg.require("does_not_exist")
    assert "general_inquiry" in str(exc.value)


def test_generic_definitions_are_industry_neutral():
    """Nothing in the generic set may assume an industry."""
    text = " ".join(
        d.case_type + d.description for d in GENERIC_DEFINITIONS
    ).lower()
    for word in ("dental", "patient", "insurance", "clinical", "tooth"):
        assert word not in text


def test_dental_registry_extends_generic():
    reg = dental_registry()
    for d in GENERIC_DEFINITIONS:
        assert d.case_type in reg
    assert "insurance_verification" in reg
    assert len(reg) > len(GENERIC_DEFINITIONS)


def test_clinical_urgency_never_auto_abandons():
    """An urgent clinical case must never time out into a closed state."""
    reg = dental_registry()
    urgent = reg.require("clinical_urgency")
    for state, target in urgent.on_timeout.items():
        assert target is not CaseState.ABANDONED


def test_clinical_urgency_has_top_priority():
    reg = dental_registry()
    urgent = reg.require("clinical_urgency")
    others = [
        reg.require(t).priority for t in reg.all_types() if t != "clinical_urgency"
    ]
    assert urgent.priority < min(others)


def test_dwell_limit_and_timeout_lookup():
    reg = dental_registry()
    d = reg.require("insurance_verification")
    assert d.dwell_limit(CaseState.WAITING_EXTERNAL) == 10 * 24 * 3600
    assert d.timeout_target(CaseState.WAITING_EXTERNAL) is CaseState.WAITING_OWNER
    assert d.dwell_limit(CaseState.RESOLVED) is None
