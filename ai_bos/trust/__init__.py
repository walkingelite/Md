"""Trust ramp — how authority is transferred to the system, one capability at a time.

Autonomy is not a switch. Each capability climbs its own ladder, and promotion
is mechanical: a threshold of consecutive clean approvals, never a judgement
call and never a global setting. Money and regulated data can be pinned below
the top rung permanently, which is a feature rather than a limitation.
"""

from ai_bos.trust.stages import TrustStage, STAGE_ORDER, next_stage, previous_stage
from ai_bos.trust.policy import CapabilityPolicy, TrustPolicy, DEFAULT_POLICIES
from ai_bos.trust.ledger import ApprovalRecord, TrustLedger, PromotionDecision
from ai_bos.trust.gate import TrustGate, GateDecision, GateAction

__all__ = [
    "TrustStage",
    "STAGE_ORDER",
    "next_stage",
    "previous_stage",
    "CapabilityPolicy",
    "TrustPolicy",
    "DEFAULT_POLICIES",
    "ApprovalRecord",
    "TrustLedger",
    "PromotionDecision",
    "TrustGate",
    "GateDecision",
    "GateAction",
]
