"""Layer 1: confidence gating is correctly enforced."""

from ai_bos.memory.confidence import KnowledgeConfidence
from ai_bos.business.confidence import can_act_on, is_blocked, requires_verification


def test_owner_stated_is_actionable():
    assert can_act_on(KnowledgeConfidence.OWNER_STATED)


def test_domain_certain_is_actionable():
    assert can_act_on(KnowledgeConfidence.DOMAIN_CERTAIN)


def test_assumed_is_blocked():
    assert is_blocked(KnowledgeConfidence.ASSUMED)


def test_unknown_is_blocked():
    assert is_blocked(KnowledgeConfidence.UNKNOWN)


def test_inferred_requires_verification():
    assert requires_verification(KnowledgeConfidence.INFERRED)
    assert not can_act_on(KnowledgeConfidence.INFERRED)
    assert not is_blocked(KnowledgeConfidence.INFERRED)
