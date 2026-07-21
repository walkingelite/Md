"""Weekly owner digest — the only proactive communication to the owner."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

import anthropic
from sqlalchemy import select, and_

from ai_bos.config import settings
from ai_bos.db.models.action import ActionLog
from ai_bos.db.models.improvement import Outcome
from ai_bos.db.session import AsyncSessionLocal
from ai_bos.logging_config import log

_client = anthropic.Anthropic(api_key=settings.anthropic_key)

DIGEST_PROMPT = """Generate a concise weekly business digest for a business owner.
The owner does not run software — the AI runs the business for them.
Focus on: key outcomes, decisions made, any issues encountered, metrics.

Data from the past week:
Actions taken: {action_count}
Successful outcomes: {success_count} / {total_outcomes}
Escalations sent to owner: {escalation_count}

Recent actions summary: {actions_summary}

Write a brief, clear summary (max 3 paragraphs). No jargon. No bullet overload."""


async def generate_digest(business_id: uuid.UUID) -> str:
    week_ago = datetime.now(tz=timezone.utc) - timedelta(days=7)

    async with AsyncSessionLocal() as session:
        action_count = await session.scalar(
            select(ActionLog).where(
                and_(
                    ActionLog.business_id == business_id,
                    ActionLog.created_at >= week_ago,
                )
            )
        ) or 0

        outcomes = list(await session.scalars(
            select(Outcome).where(
                and_(
                    Outcome.business_id == business_id,
                    Outcome.created_at >= week_ago,
                    Outcome.success.is_not(None),
                )
            ).limit(50)
        ))

    success_count = sum(1 for o in outcomes if o.success)
    total_outcomes = len(outcomes)

    response = _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": DIGEST_PROMPT.format(
                action_count=action_count,
                success_count=success_count,
                total_outcomes=total_outcomes,
                escalation_count=0,
                actions_summary="(detailed action log available on request)",
            ),
        }],
    )
    digest = response.content[0].text
    log.info("digest.generated", business_id=str(business_id), length=len(digest))
    return digest
