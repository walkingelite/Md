"""Layer 2: business confidence classification."""

from ai_bos.business.confidence import classify_from_source
from ai_bos.memory.confidence import KnowledgeConfidence


def test_owner_stated_wins():
    assert classify_from_source(owner_stated=True) == KnowledgeConfidence.OWNER_STATED


def test_domain_certain_needs_source():
    assert classify_from_source(domain_certain=True, source_count=1) == KnowledgeConfidence.DOMAIN_CERTAIN
    assert classify_from_source(domain_certain=True, source_count=0) == KnowledgeConfidence.INFERRED


def test_no_source_means_assumed():
    assert classify_from_source(source_count=0) == KnowledgeConfidence.ASSUMED
