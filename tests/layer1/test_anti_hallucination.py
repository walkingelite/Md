"""Layer 1: facts without sources are downgraded — never accepted as CERTAIN."""

from ai_bos.memory.anti_hallucination import CandidateFact, validate_candidate
from ai_bos.memory.confidence import KnowledgeConfidence, KnowledgeBasis


def test_no_source_downgrades_to_assumed():
    candidate = CandidateFact(
        domain="regulatory",
        key="hipaa_required",
        value={"required": True},
        proposed_confidence=KnowledgeConfidence.DOMAIN_CERTAIN,
        source_references=[],
    )
    confidence, basis = validate_candidate(candidate)
    assert confidence == KnowledgeConfidence.ASSUMED
    assert basis == KnowledgeBasis.ASSUMED


def test_single_source_downgrades_domain_certain_to_inferred():
    candidate = CandidateFact(
        domain="regulatory",
        key="hipaa_required",
        value={"required": True},
        proposed_confidence=KnowledgeConfidence.DOMAIN_CERTAIN,
        source_references=["https://hhs.gov/hipaa"],
    )
    confidence, basis = validate_candidate(candidate)
    assert confidence == KnowledgeConfidence.INFERRED


def test_two_sources_allows_domain_certain():
    candidate = CandidateFact(
        domain="regulatory",
        key="hipaa_required",
        value={"required": True},
        proposed_confidence=KnowledgeConfidence.DOMAIN_CERTAIN,
        source_references=["https://hhs.gov/hipaa", "https://cms.gov/hipaa"],
    )
    confidence, basis = validate_candidate(candidate)
    assert confidence == KnowledgeConfidence.DOMAIN_CERTAIN


def test_owner_stated_never_downgraded():
    candidate = CandidateFact(
        domain="operational",
        key="business_hours",
        value={"hours": "9-5"},
        proposed_confidence=KnowledgeConfidence.OWNER_STATED,
        source_references=["owner_intake_session_1"],
    )
    confidence, _ = validate_candidate(candidate)
    assert confidence == KnowledgeConfidence.OWNER_STATED
