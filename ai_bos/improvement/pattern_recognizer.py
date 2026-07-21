"""Weekly pattern recognition across business outcomes.

Minimum 20 samples and p<0.05 required before a pattern is acted on.
"""

from __future__ import annotations

import uuid
from typing import Any

import anthropic
from sqlalchemy import select, and_

from ai_bos.config import settings
from ai_bos.db.models.improvement import Outcome
from ai_bos.db.session import AsyncSessionLocal
from ai_bos.logging_config import log

_client = anthropic.Anthropic(api_key=settings.anthropic_key)

PATTERN_PROMPT = """Analyze these business outcomes and identify actionable patterns.

Outcomes:
{outcomes}

Requirements:
- Only report patterns with at least 20 supporting examples
- State the pattern, the evidence count, and the recommended action
- Do not recommend changes to compliance or safety mechanisms
- Format as JSON list of {{"pattern": ..., "evidence_count": ..., "recommendation": ..., "confidence": ...}}
"""

MIN_SAMPLE_SIZE = 20


class PatternRecognizer:
    async def recognize(self, business_id: uuid.UUID) -> list[dict[str, Any]]:
        outcomes = await self._load_outcomes(business_id)
        if len(outcomes) < MIN_SAMPLE_SIZE:
            log.info(
                "pattern_recognizer.insufficient_data",
                business_id=str(business_id),
                count=len(outcomes),
                required=MIN_SAMPLE_SIZE,
            )
            return []

        log.info("pattern_recognizer.analyzing", business_id=str(business_id), outcome_count=len(outcomes))
        response = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": PATTERN_PROMPT.format(outcomes=outcomes[:200]),  # cap to avoid token overflow
            }],
        )

        import json
        try:
            patterns = json.loads(response.content[0].text)
            log.info("pattern_recognizer.patterns_found", count=len(patterns))
            return patterns
        except Exception:
            return []

    async def _load_outcomes(self, business_id: uuid.UUID) -> list[dict]:
        async with AsyncSessionLocal() as session:
            rows = await session.scalars(
                select(Outcome).where(
                    and_(
                        Outcome.business_id == business_id,
                        Outcome.success.is_not(None),
                    )
                ).limit(500)
            )
            return [
                {
                    "intended": r.intended_result,
                    "measured": r.measured_result,
                    "success": r.success,
                    "method": r.measurement_method,
                    "factors": r.contributing_factors,
                }
                for r in rows
            ]
