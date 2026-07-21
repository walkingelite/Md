"""Unified memory interface — the AI's single source of truth.

Every retrieval returns a MemoryResult with full provenance.
The AI never gets raw text back; it always knows how confident to be.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ai_bos.memory.confidence import KnowledgeBasis, KnowledgeConfidence
from ai_bos.logging_config import log


@dataclass
class MemoryResult:
    """A retrieved piece of knowledge with full provenance."""
    content: dict
    confidence: KnowledgeConfidence
    basis: KnowledgeBasis
    source_ids: list[str]
    retrieved_at: datetime
    age_seconds: float
    staleness_warning: bool
    domain: str
    key: str


@dataclass
class MemoryQuery:
    business_id: uuid.UUID
    domain: str | None = None
    key: str | None = None
    semantic_query: str | None = None   # For vector search
    min_confidence: KnowledgeConfidence = KnowledgeConfidence.ASSUMED
    limit: int = 10


class MemoryStore:
    """Hybrid memory: PostgreSQL for structured facts, ChromaDB for semantic search."""

    def __init__(self) -> None:
        self._structured: StructuredMemory | None = None
        self._vector: VectorMemory | None = None

    async def initialize(self) -> None:
        from ai_bos.memory.structured import StructuredMemory
        from ai_bos.memory.vector import VectorMemory
        self._structured = StructuredMemory()
        self._vector = VectorMemory()
        await self._vector.initialize()

    async def write_fact(
        self,
        business_id: uuid.UUID,
        domain: str,
        key: str,
        value: dict,
        confidence: KnowledgeConfidence,
        basis: KnowledgeBasis,
        source_ids: list[str] | None = None,
    ) -> uuid.UUID:
        """Write a fact to structured store and index it in vector store."""
        assert self._structured is not None
        assert self._vector is not None

        fact_id = await self._structured.write(
            business_id=business_id,
            domain=domain,
            key=key,
            value=value,
            confidence=confidence,
            basis=basis,
            source_ids=source_ids or [],
        )
        # Also index for semantic search
        await self._vector.index(
            fact_id=fact_id,
            business_id=business_id,
            text=f"{domain}/{key}: {value}",
            metadata={"domain": domain, "key": key, "confidence": confidence.value},
        )
        log.info("memory.fact_written", business_id=str(business_id), domain=domain, key=key, confidence=confidence.value)
        return fact_id

    async def retrieve(self, query: MemoryQuery) -> list[MemoryResult]:
        """Retrieve facts. Returns MemoryResult objects — never raw text."""
        assert self._structured is not None

        if query.key:
            results = await self._structured.get_by_key(
                business_id=query.business_id,
                domain=query.domain,
                key=query.key,
            )
        elif query.semantic_query:
            assert self._vector is not None
            fact_ids = await self._vector.search(
                query=query.semantic_query,
                business_id=query.business_id,
                limit=query.limit,
            )
            results = await self._structured.get_by_ids(fact_ids)
        else:
            results = await self._structured.get_by_domain(
                business_id=query.business_id,
                domain=query.domain or "",
                limit=query.limit,
            )

        now = datetime.now(tz=timezone.utc)
        memory_results = []
        for r in results:
            age = (now - r["updated_at"]).total_seconds()
            staleness_warning = self._is_stale(r["domain"], age)
            memory_results.append(
                MemoryResult(
                    content=r["value_json"],
                    confidence=KnowledgeConfidence(r["confidence"]),
                    basis=KnowledgeBasis(r["basis"]),
                    source_ids=r["source_ids"],
                    retrieved_at=now,
                    age_seconds=age,
                    staleness_warning=staleness_warning,
                    domain=r["domain"],
                    key=r["key"],
                )
            )
        return memory_results

    def _is_stale(self, domain: str, age_seconds: float) -> bool:
        from ai_bos.memory.staleness import STALENESS_THRESHOLDS
        threshold = STALENESS_THRESHOLDS.get(domain, STALENESS_THRESHOLDS["default"])
        return age_seconds > threshold
