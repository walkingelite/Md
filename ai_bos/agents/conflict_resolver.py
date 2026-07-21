"""Detect and resolve conflicts between concurrent agents.

Resource locks use Redis with TTL to prevent two agents acting on the same
resource simultaneously. Semantic conflict detection prevents duplicate
customer communications.
"""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager

import redis.asyncio as aioredis

from ai_bos.config import settings
from ai_bos.logging_config import log

LOCK_TTL_SECONDS = 60


class ConflictResolver:
    def __init__(self) -> None:
        self._redis = aioredis.from_url(str(settings.redis_url))

    def _lock_key(self, resource_type: str, resource_id: str, business_id: str) -> str:
        return f"lock:{business_id}:{resource_type}:{resource_id}"

    def _send_lock_key(self, customer_id: str, business_id: str) -> str:
        return f"send_lock:{business_id}:{customer_id}"

    @asynccontextmanager
    async def acquire_resource_lock(
        self,
        resource_type: str,
        resource_id: str,
        business_id: str,
        agent_id: str,
        timeout: float = 30.0,
    ):
        key = self._lock_key(resource_type, resource_id, business_id)
        acquired = await self._redis.set(key, agent_id, nx=True, ex=LOCK_TTL_SECONDS)
        if not acquired:
            holder = await self._redis.get(key)
            log.warning(
                "conflict_resolver.lock_failed",
                key=key,
                agent=agent_id,
                holder=holder,
            )
            raise ResourceConflictError(
                f"Resource {resource_type}:{resource_id} locked by {holder}"
            )
        try:
            yield
        finally:
            await self._redis.delete(key)

    async def acquire_send_lock(self, customer_id: str, business_id: str, agent_id: str) -> bool:
        """Prevent two agents from sending to the same customer within 60 seconds."""
        key = self._send_lock_key(customer_id, business_id)
        acquired = await self._redis.set(key, agent_id, nx=True, ex=LOCK_TTL_SECONDS)
        if not acquired:
            log.warning(
                "conflict_resolver.send_lock_failed",
                customer_id=customer_id,
                agent=agent_id,
            )
        return bool(acquired)

    async def release_send_lock(self, customer_id: str, business_id: str) -> None:
        key = self._send_lock_key(customer_id, business_id)
        await self._redis.delete(key)


class ResourceConflictError(Exception):
    pass
