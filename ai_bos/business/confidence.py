"""Business knowledge confidence classification and action gating."""

from __future__ import annotations

from ai_bos.memory.confidence import (
    ACTIONABLE_CONFIDENCE,
    BLOCKED_CONFIDENCE,
    VERIFY_BEFORE_ACTION,
    KnowledgeConfidence,
)


def can_act_on(confidence: KnowledgeConfidence) -> bool:
    """Returns True if the system may take autonomous action on this fact."""
    return confidence in ACTIONABLE_CONFIDENCE


def requires_verification(confidence: KnowledgeConfidence) -> bool:
    return confidence in VERIFY_BEFORE_ACTION


def is_blocked(confidence: KnowledgeConfidence) -> bool:
    return confidence in BLOCKED_CONFIDENCE


def classify_from_source(
    *,
    owner_stated: bool = False,
    domain_certain: bool = False,
    source_count: int = 0,
    is_regulatory: bool = False,
) -> KnowledgeConfidence:
    """Classify confidence based on how we know a fact."""
    if owner_stated:
        return KnowledgeConfidence.OWNER_STATED
    if domain_certain and source_count >= 1:
        return KnowledgeConfidence.DOMAIN_CERTAIN
    if domain_certain and source_count == 0:
        return KnowledgeConfidence.INFERRED
    if source_count >= 1:
        return KnowledgeConfidence.DOMAIN_TYPICAL
    return KnowledgeConfidence.ASSUMED
