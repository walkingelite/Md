"""Source-grounded fact validation: no source = no fact.

Every candidate fact from an LLM must have at least one source reference
before it is written to the memory store. Facts without sources are tagged
ASSUMED at MEDIUM confidence at best.
"""

from __future__ import annotations

from dataclasses import dataclass

from ai_bos.memory.confidence import KnowledgeBasis, KnowledgeConfidence
from ai_bos.logging_config import log


@dataclass
class CandidateFact:
    domain: str
    key: str
    value: dict
    proposed_confidence: KnowledgeConfidence
    source_references: list[str]  # episode IDs, URLs, document IDs


def validate_candidate(candidate: CandidateFact) -> tuple[KnowledgeConfidence, KnowledgeBasis]:
    """
    Returns the validated (possibly downgraded) confidence and basis.
    A fact with no sources is capped at ASSUMED / INFERRED.
    """
    if not candidate.source_references:
        log.warning(
            "anti_hallucination.no_source",
            domain=candidate.domain,
            key=candidate.key,
            proposed=candidate.proposed_confidence.value,
        )
        # Downgrade: no source means we can't trust it beyond ASSUMED
        return KnowledgeConfidence.ASSUMED, KnowledgeBasis.ASSUMED

    # LLM-generated facts from text are INFERRED until a second source confirms
    if candidate.proposed_confidence in (
        KnowledgeConfidence.DOMAIN_CERTAIN,
        KnowledgeConfidence.DOMAIN_TYPICAL,
    ):
        if len(candidate.source_references) < 2:
            log.info(
                "anti_hallucination.single_source_downgrade",
                domain=candidate.domain,
                key=candidate.key,
            )
            return KnowledgeConfidence.INFERRED, KnowledgeBasis.INFERRED

    return candidate.proposed_confidence, KnowledgeBasis.EXTERNAL
