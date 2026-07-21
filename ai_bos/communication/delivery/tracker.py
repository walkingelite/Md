"""Delivery verification — the system never assumes a message was delivered."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from ai_bos.db.models.communication import Message
from ai_bos.db.session import AsyncSessionLocal
from ai_bos.logging_config import log


async def mark_delivered(message_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        msg = await session.get(Message, message_id)
        if msg:
            msg.delivered_at = datetime.now(tz=timezone.utc)
            await session.commit()
            log.info("delivery.confirmed", message_id=str(message_id))


async def mark_failed(message_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        msg = await session.get(Message, message_id)
        if msg:
            msg.failed_at = datetime.now(tz=timezone.utc)
            await session.commit()
            log.warning("delivery.failed", message_id=str(message_id))


async def get_unverified_messages(business_id: uuid.UUID, limit: int = 50) -> list[Message]:
    """Find messages sent but not yet confirmed delivered or failed."""
    async with AsyncSessionLocal() as session:
        rows = await session.scalars(
            select(Message)
            .where(
                Message.business_id == business_id,
                Message.direction == "OUTBOUND",
                Message.sent_at.is_not(None),
                Message.delivered_at.is_(None),
                Message.failed_at.is_(None),
            )
            .limit(limit)
        )
        return list(rows)
