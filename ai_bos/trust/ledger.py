"""The approval record and the promotion arithmetic.

The ledger is the durable evidence that authority was earned. It is also the
thing a competitor cannot copy: a history showing a capability ran four
thousand times at 99.7% approval is not reproducible by writing the same code.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ai_bos.logging_config import log
from ai_bos.trust.policy import CapabilityPolicy, TrustPolicy
from ai_bos.trust.stages import TrustStage, next_stage, previous_stage, rank


@dataclass
class ApprovalRecord:
    record_id: uuid.UUID = field(default_factory=uuid.uuid4)
    capability: str = ""
    stage_at_time: TrustStage = TrustStage.SHADOW
    approved: bool = False
    edited: bool = False          # approved but the owner changed it first
    occurred_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    case_id: uuid.UUID | None = None
    note: str = ""

    @property
    def is_clean(self) -> bool:
        """Only untouched approvals count toward promotion.

        An approval the owner had to edit is evidence the system was wrong,
        even though the message went out.
        """
        return self.approved and not self.edited


@dataclass
class PromotionDecision:
    capability: str
    from_stage: TrustStage
    to_stage: TrustStage
    reason: str
    promoted: bool

    @property
    def demoted(self) -> bool:
        return rank(self.to_stage) < rank(self.from_stage)


class TrustLedger:
    def __init__(self, business_id: uuid.UUID, policy: TrustPolicy | None = None) -> None:
        self.business_id = business_id
        self.policy = policy or TrustPolicy()
        self._records: dict[str, list[ApprovalRecord]] = defaultdict(list)
        self._stages: dict[str, TrustStage] = {}

    # ------------------------------------------------------------------- stages

    def stage_for(self, capability: str) -> TrustStage:
        if capability not in self._stages:
            policy = self.policy.require(capability)
            start = policy.initial_stage
            # Never start above the ceiling.
            if rank(start) > rank(policy.ceiling):
                start = policy.ceiling
            self._stages[capability] = start
        return self._stages[capability]

    def set_stage(self, capability: str, stage: TrustStage, reason: str = "") -> None:
        policy = self.policy.require(capability)
        if rank(stage) > rank(policy.ceiling):
            raise ValueError(
                f"{capability} cannot exceed its ceiling {policy.ceiling.value}"
            )
        self._stages[capability] = stage
        log.info(
            "trust.stage_set",
            capability=capability,
            stage=stage.value,
            reason=reason,
        )

    # ------------------------------------------------------------------ recording

    def record(self, record: ApprovalRecord) -> PromotionDecision | None:
        record.stage_at_time = self.stage_for(record.capability)
        self._records[record.capability].append(record)
        log.info(
            "trust.approval_recorded",
            capability=record.capability,
            approved=record.approved,
            edited=record.edited,
            stage=record.stage_at_time.value,
        )
        return self.evaluate(record.capability)

    # ----------------------------------------------------------------- evaluation

    def clean_streak(self, capability: str) -> int:
        """Consecutive clean approvals since the last rejection or edit."""
        streak = 0
        for record in reversed(self._records[capability]):
            if record.is_clean:
                streak += 1
            else:
                break
        return streak

    def recent_rejections(self, capability: str, window: int = 20) -> int:
        recent = self._records[capability][-window:]
        return sum(1 for r in recent if not r.approved)

    def evaluate(self, capability: str) -> PromotionDecision | None:
        policy = self.policy.require(capability)
        current = self.stage_for(capability)

        demotion = self._check_demotion(capability, policy, current)
        if demotion:
            return demotion

        threshold = policy.threshold_for(current)
        if threshold is None:
            return None  # no promotion path defined from here

        target = next_stage(current)
        if target is None or rank(target) > rank(policy.ceiling):
            return None  # already at the ceiling

        if self.clean_streak(capability) >= threshold:
            self._stages[capability] = target
            decision = PromotionDecision(
                capability=capability,
                from_stage=current,
                to_stage=target,
                reason=f"{threshold} consecutive clean approvals",
                promoted=True,
            )
            log.info(
                "trust.promoted",
                capability=capability,
                **{"from": current.value},
                to=target.value,
                streak=threshold,
            )
            return decision
        return None

    def _check_demotion(
        self, capability: str, policy: CapabilityPolicy, current: TrustStage
    ) -> PromotionDecision | None:
        if self.recent_rejections(capability) < policy.rejection_tolerance:
            return None

        target = current
        for _ in range(policy.demotion_rungs):
            lower = previous_stage(target)
            if lower is None:
                break
            target = lower

        if target is current:
            return None

        self._stages[capability] = target
        log.warning(
            "trust.demoted",
            capability=capability,
            **{"from": current.value},
            to=target.value,
            rejections=self.recent_rejections(capability),
        )
        return PromotionDecision(
            capability=capability,
            from_stage=current,
            to_stage=target,
            reason=f"{self.recent_rejections(capability)} recent rejections",
            promoted=False,
        )

    # -------------------------------------------------------------------- report

    def approval_rate(self, capability: str) -> float | None:
        records = self._records[capability]
        if not records:
            return None
        return sum(1 for r in records if r.approved) / len(records)

    def summary(self) -> list[dict]:
        rows = []
        for capability in sorted(set(self._stages) | set(self._records)):
            policy = self.policy.require(capability)
            stage = self.stage_for(capability)
            threshold = policy.threshold_for(stage)
            rows.append(
                {
                    "capability": capability,
                    "stage": stage.value,
                    "ceiling": policy.ceiling.value,
                    "clean_streak": self.clean_streak(capability),
                    "needed": threshold,
                    "total": len(self._records[capability]),
                    "approval_rate": self.approval_rate(capability),
                    "at_ceiling": stage is policy.ceiling,
                }
            )
        return rows
