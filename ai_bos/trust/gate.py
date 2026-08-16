"""The gate every outbound action passes through.

This is enforcement, not advice. An agent cannot reason its way past it,
because the agent never sees the decision — the executor does.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum

from ai_bos.logging_config import log
from ai_bos.trust.ledger import TrustLedger
from ai_bos.trust.stages import TrustStage


class GateAction(str, Enum):
    SEND = "SEND"                    # dispatch now
    SEND_WITH_RECALL = "SEND_WITH_RECALL"  # dispatch, undo window open
    QUEUE_FOR_APPROVAL = "QUEUE_FOR_APPROVAL"  # owner must approve first
    LOG_ONLY = "LOG_ONLY"            # shadow: record what would have happened


@dataclass
class GateDecision:
    action: GateAction
    capability: str
    stage: TrustStage
    reason: str
    recall_window_seconds: int = 0

    @property
    def will_reach_customer(self) -> bool:
        return self.action in (GateAction.SEND, GateAction.SEND_WITH_RECALL)


RECALL_WINDOW_SECONDS = 300  # five minutes


class TrustGate:
    def __init__(self, ledger: TrustLedger) -> None:
        self.ledger = ledger

    def decide(
        self,
        capability: str,
        *,
        case_id: uuid.UUID | None = None,
        force_supervision: bool = False,
    ) -> GateDecision:
        """
        `force_supervision` lets a caller demand approval regardless of stage —
        used when an upstream check is uncertain. It can tighten the decision,
        never loosen it.
        """
        stage = self.ledger.stage_for(capability)

        if force_supervision and stage is not TrustStage.SHADOW:
            decision = GateDecision(
                action=GateAction.QUEUE_FOR_APPROVAL,
                capability=capability,
                stage=stage,
                reason="supervision forced by caller",
            )
        elif stage is TrustStage.SHADOW:
            decision = GateDecision(
                action=GateAction.LOG_ONLY,
                capability=capability,
                stage=stage,
                reason="capability is in shadow",
            )
        elif stage is TrustStage.DRAFT:
            decision = GateDecision(
                action=GateAction.QUEUE_FOR_APPROVAL,
                capability=capability,
                stage=stage,
                reason="capability requires owner approval",
            )
        elif stage is TrustStage.AUTO_WITH_RECALL:
            decision = GateDecision(
                action=GateAction.SEND_WITH_RECALL,
                capability=capability,
                stage=stage,
                reason="autonomous with recall window",
                recall_window_seconds=RECALL_WINDOW_SECONDS,
            )
        else:
            decision = GateDecision(
                action=GateAction.SEND,
                capability=capability,
                stage=stage,
                reason="fully autonomous",
            )

        log.info(
            "trust.gate_decision",
            capability=capability,
            stage=stage.value,
            action=decision.action.value,
            case_id=str(case_id) if case_id else None,
        )
        return decision
