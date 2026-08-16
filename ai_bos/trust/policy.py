"""Per-capability promotion rules.

Promotion criteria are data, not judgement. A capability rises only by
accumulating consecutive clean approvals, and `ceiling` lets a capability be
pinned below full autonomy no matter how well it performs — which is how
anything touching money or regulated data stays supervised permanently.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ai_bos.trust.stages import TrustStage


@dataclass(frozen=True)
class CapabilityPolicy:
    capability: str
    description: str = ""

    # Consecutive clean approvals required to leave each stage.
    promotion_thresholds: dict[TrustStage, int] = field(default_factory=dict)

    # Highest stage this capability may ever reach.
    ceiling: TrustStage = TrustStage.AUTO

    # Stage a capability starts at when first seen.
    initial_stage: TrustStage = TrustStage.SHADOW

    # A single rejection drops the capability this many rungs.
    demotion_rungs: int = 1

    # Rejections within the window that force a demotion regardless of streak.
    rejection_tolerance: int = 2

    def threshold_for(self, stage: TrustStage) -> int | None:
        return self.promotion_thresholds.get(stage)


DEFAULT_THRESHOLDS = {
    TrustStage.SHADOW: 20,
    TrustStage.DRAFT: 50,
    TrustStage.AUTO_WITH_RECALL: 100,
}


DEFAULT_POLICIES: tuple[CapabilityPolicy, ...] = (
    CapabilityPolicy(
        capability="appointment_confirmation",
        description="Confirm a booking the customer already requested.",
        promotion_thresholds=DEFAULT_THRESHOLDS,
        ceiling=TrustStage.AUTO,
    ),
    CapabilityPolicy(
        capability="appointment_reminder",
        description="Remind a customer of an upcoming booking.",
        promotion_thresholds=DEFAULT_THRESHOLDS,
        ceiling=TrustStage.AUTO,
    ),
    CapabilityPolicy(
        capability="general_reply",
        description="Answer a question using facts already on record.",
        promotion_thresholds={
            TrustStage.SHADOW: 40,
            TrustStage.DRAFT: 120,
            TrustStage.AUTO_WITH_RECALL: 250,
        },
        ceiling=TrustStage.AUTO_WITH_RECALL,
    ),
    CapabilityPolicy(
        capability="send_invoice",
        description="Issue an invoice for an agreed amount.",
        promotion_thresholds={TrustStage.SHADOW: 100, TrustStage.DRAFT: 500},
        # Money never reaches unattended autonomy.
        ceiling=TrustStage.AUTO_WITH_RECALL,
        rejection_tolerance=1,
    ),
    CapabilityPolicy(
        capability="quote_price",
        description="State a price to a customer.",
        promotion_thresholds={TrustStage.SHADOW: 200},
        # A quote is a commitment; it stays owner-approved forever.
        ceiling=TrustStage.DRAFT,
        rejection_tolerance=1,
    ),
    CapabilityPolicy(
        capability="disclose_regulated_data",
        description="Send data subject to a regulatory regime.",
        promotion_thresholds={},
        # Never promoted by any amount of good behaviour.
        ceiling=TrustStage.SHADOW,
        rejection_tolerance=1,
    ),
)


class TrustPolicy:
    """The policy set for one business."""

    def __init__(self, policies: list[CapabilityPolicy] | None = None) -> None:
        self._by_capability: dict[str, CapabilityPolicy] = {}
        for p in policies or list(DEFAULT_POLICIES):
            self.register(p)

    def register(self, policy: CapabilityPolicy) -> None:
        if policy.capability in self._by_capability:
            raise ValueError(f"Policy already registered: {policy.capability}")
        self._by_capability[policy.capability] = policy

    def get(self, capability: str) -> CapabilityPolicy | None:
        return self._by_capability.get(capability)

    def require(self, capability: str) -> CapabilityPolicy:
        policy = self._by_capability.get(capability)
        if policy is None:
            # Unknown capabilities are not implicitly trusted.
            return CapabilityPolicy(
                capability=capability,
                description="unregistered capability",
                promotion_thresholds={},
                ceiling=TrustStage.SHADOW,
            )
        return policy

    def capabilities(self) -> list[str]:
        return sorted(self._by_capability)

    def __len__(self) -> int:
        return len(self._by_capability)

    def __contains__(self, capability: object) -> bool:
        return capability in self._by_capability
