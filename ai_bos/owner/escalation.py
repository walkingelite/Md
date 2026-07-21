"""Owner escalation — genuine judgment calls only.

Escalation triggers when ALL THREE are true:
1. System lacks sufficient information to decide
2. Decision cannot be deferred
3. Consequences of a wrong decision are significant

Auto-resolves after 4 hours using system's best recommendation.
Escalation rate is tracked — >3/day triggers root-cause analysis.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ai_bos.logging_config import log

AUTO_RESOLVE_HOURS = 4
DAILY_ESCALATION_THRESHOLD = 3


@dataclass
class EscalationItem:
    escalation_id: uuid.UUID = field(default_factory=uuid.uuid4)
    business_id: uuid.UUID = field(default_factory=uuid.uuid4)
    question: str = ""
    recommendation: str = ""
    context_summary: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    resolved_at: datetime | None = None
    owner_response: str | None = None
    auto_resolved: bool = False


class OwnerEscalation:
    def __init__(self) -> None:
        self._items: list[EscalationItem] = []
        self._daily_count: int = 0

    def escalate(
        self,
        business_id: uuid.UUID,
        question: str,
        recommendation: str,
        context_summary: str,
    ) -> EscalationItem:
        item = EscalationItem(
            business_id=business_id,
            question=question,
            recommendation=recommendation,
            context_summary=context_summary,
        )
        self._items.append(item)
        self._daily_count += 1

        if self._daily_count > DAILY_ESCALATION_THRESHOLD:
            log.warning(
                "escalation.high_rate",
                daily_count=self._daily_count,
                threshold=DAILY_ESCALATION_THRESHOLD,
            )

        log.info(
            "escalation.created",
            escalation_id=str(item.escalation_id),
            question=question[:100],
        )
        return item

    def resolve(self, escalation_id: uuid.UUID, owner_response: str) -> None:
        for item in self._items:
            if item.escalation_id == escalation_id:
                item.owner_response = owner_response
                item.resolved_at = datetime.now(tz=timezone.utc)
                log.info("escalation.resolved", escalation_id=str(escalation_id))
                return

    def auto_resolve_stale(self) -> list[EscalationItem]:
        """Auto-resolve escalations older than 4 hours using the recommendation."""
        now = datetime.now(tz=timezone.utc)
        resolved = []
        for item in self._items:
            if item.resolved_at:
                continue
            age_hours = (now - item.created_at).total_seconds() / 3600
            if age_hours >= AUTO_RESOLVE_HOURS:
                item.owner_response = item.recommendation
                item.resolved_at = now
                item.auto_resolved = True
                log.info(
                    "escalation.auto_resolved",
                    escalation_id=str(item.escalation_id),
                    recommendation=item.recommendation[:100],
                )
                resolved.append(item)
        return resolved
