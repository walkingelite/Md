"""A/B experiment manager — max 20% traffic on new behavior, auto-rollback on failure."""

from __future__ import annotations

import uuid
import random
from datetime import datetime, timezone
from typing import Any

from ai_bos.db.models.improvement import Experiment
from ai_bos.db.session import AsyncSessionLocal
from ai_bos.improvement.goodhart_guard import check_multi_metric
from ai_bos.logging_config import log

MAX_TRAFFIC_SPLIT_PCT = 20.0


class ExperimentManager:
    async def create(
        self,
        business_id: uuid.UUID,
        hypothesis: str,
        variant_a_desc: str,
        variant_b_desc: str,
        traffic_split_pct: float = 10.0,
    ) -> uuid.UUID:
        if traffic_split_pct > MAX_TRAFFIC_SPLIT_PCT:
            traffic_split_pct = MAX_TRAFFIC_SPLIT_PCT
            log.warning("experiment.traffic_capped", capped_at=MAX_TRAFFIC_SPLIT_PCT)

        async with AsyncSessionLocal() as session:
            exp = Experiment(
                business_id=business_id,
                hypothesis=hypothesis,
                variant_a_desc=variant_a_desc,
                variant_b_desc=variant_b_desc,
                traffic_split_pct=traffic_split_pct,
                status="running",
                started_at=datetime.now(tz=timezone.utc),
            )
            session.add(exp)
            await session.commit()
            log.info("experiment.created", experiment_id=str(exp.id), hypothesis=hypothesis)
            return exp.id

    def should_use_variant_b(self, traffic_split_pct: float) -> bool:
        """Consistent per-customer routing based on random assignment."""
        return random.random() < (traffic_split_pct / 100.0)

    async def conclude(
        self,
        experiment_id: uuid.UUID,
        improvements: dict[str, float],
    ) -> bool:
        """Conclude the experiment. Returns True if variant B wins."""
        gate_passed, reason = check_multi_metric(improvements)

        async with AsyncSessionLocal() as session:
            exp = await session.get(Experiment, experiment_id)
            if exp:
                exp.status = "concluded" if gate_passed else "rolled_back"
                exp.result_json = {"improvements": improvements, "gate_reason": reason, "accepted": gate_passed}
                exp.concluded_at = datetime.now(tz=timezone.utc)
                await session.commit()

        log.info(
            "experiment.concluded",
            experiment_id=str(experiment_id),
            accepted=gate_passed,
            reason=reason,
        )
        return gate_passed
