"""PostgreSQL-backed structured fact store with optimistic locking."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ai_bos.db.models.business import FactRecord
from ai_bos.db.session import AsyncSessionLocal
from ai_bos.memory.confidence import KnowledgeBasis, KnowledgeConfidence


class StructuredMemory:
    async def write(
        self,
        *,
        business_id: uuid.UUID,
        domain: str,
        key: str,
        value: dict,
        confidence: KnowledgeConfidence,
        basis: KnowledgeBasis,
        source_ids: list[str],
    ) -> uuid.UUID:
        async with AsyncSessionLocal() as session:
            # Upsert: if fact with same business/domain/key exists, update it
            existing = await session.scalar(
                select(FactRecord).where(
                    and_(
                        FactRecord.business_id == business_id,
                        FactRecord.domain == domain,
                        FactRecord.key == key,
                        FactRecord.deleted_at.is_(None),
                    )
                )
            )
            if existing:
                existing.value_json = value
                existing.confidence = confidence.value
                existing.basis = basis.value
                existing.source_ids = source_ids
                existing.last_verified_at = datetime.now(tz=timezone.utc).isoformat()
                fact_id = existing.id
            else:
                fact = FactRecord(
                    business_id=business_id,
                    domain=domain,
                    key=key,
                    value_json=value,
                    confidence=confidence.value,
                    basis=basis.value,
                    source_ids=source_ids,
                    last_verified_at=datetime.now(tz=timezone.utc).isoformat(),
                )
                session.add(fact)
                await session.flush()
                fact_id = fact.id
            await session.commit()
            return fact_id

    async def get_by_key(
        self, *, business_id: uuid.UUID, domain: str | None, key: str
    ) -> list[dict[str, Any]]:
        async with AsyncSessionLocal() as session:
            stmt = select(FactRecord).where(
                and_(
                    FactRecord.business_id == business_id,
                    FactRecord.key == key,
                    FactRecord.deleted_at.is_(None),
                )
            )
            if domain:
                stmt = stmt.where(FactRecord.domain == domain)
            rows = await session.scalars(stmt)
            return [self._to_dict(r) for r in rows]

    async def get_by_domain(
        self, *, business_id: uuid.UUID, domain: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        async with AsyncSessionLocal() as session:
            rows = await session.scalars(
                select(FactRecord)
                .where(
                    and_(
                        FactRecord.business_id == business_id,
                        FactRecord.domain == domain,
                        FactRecord.deleted_at.is_(None),
                    )
                )
                .limit(limit)
            )
            return [self._to_dict(r) for r in rows]

    async def get_by_ids(self, fact_ids: list[str]) -> list[dict[str, Any]]:
        uuids = [uuid.UUID(fid) for fid in fact_ids]
        async with AsyncSessionLocal() as session:
            rows = await session.scalars(
                select(FactRecord).where(FactRecord.id.in_(uuids))
            )
            return [self._to_dict(r) for r in rows]

    def _to_dict(self, r: FactRecord) -> dict[str, Any]:
        return {
            "id": str(r.id),
            "domain": r.domain,
            "key": r.key,
            "value_json": r.value_json,
            "confidence": r.confidence,
            "basis": r.basis,
            "source_ids": r.source_ids,
            "updated_at": r.updated_at,
        }
