"""Record outcomes for every significant action — including delayed measurements."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from ai_bos.db.models.improvement import Outcome
from ai_bos.db.session import AsyncSessionLocal
from ai_bos.logging_config import log


class OutcomeTracker:
    async def record(
        self,
        *,
        business_id: uuid.UUID,
        action_id: uuid.UUID | None,
        intended_result: str,
        measurement_method: str,
        contributing_factors: dict[str, Any] | None = None,
    ) -> uuid.UUID:
        async with AsyncSessionLocal() as session:
            outcome = Outcome(
                business_id=business_id,
                action_id=action_id,
                intended_result=intended_result,
                measurement_method=measurement_method,
                contributing_factors=contributing_factors or {},
                # success and measured_result filled in later
            )
            session.add(outcome)
            await session.commit()
            log.info("outcome.recorded", outcome_id=str(outcome.id), intended=intended_result)
            return outcome.id

    async def measure(
        self,
        outcome_id: uuid.UUID,
        *,
        success: bool,
        measured_result: str,
        confidence: float,
    ) -> None:
        async with AsyncSessionLocal() as session:
            outcome = await session.get(Outcome, outcome_id)
            if outcome:
                outcome.success = success
                outcome.measured_result = measured_result
                outcome.confidence = confidence
                outcome.measured_at = datetime.now(tz=timezone.utc)
                await session.commit()
                log.info(
                    "outcome.measured",
                    outcome_id=str(outcome_id),
                    success=success,
                    confidence=confidence,
                )
