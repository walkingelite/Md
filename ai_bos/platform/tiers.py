"""What an instance may change, and on whose authority."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from ai_bos.logging_config import log


class ChangeTier(str, Enum):
    LOCAL = "LOCAL"        # instance applies it alone
    PROPOSED = "PROPOSED"  # instance drafts it, creator ships it
    PLATFORM = "PLATFORM"  # creator only; instance cannot even propose


class ChangeKind(str, Enum):
    # Tier 1 — the business's own reality
    FACT = "fact"                          # "we now accept this insurer"
    POLICY_VALUE = "policy_value"          # "deposits are refundable"
    PARTY_DATA = "party_data"
    BOOKING_DATA = "booking_data"
    TRUST_RECORD = "trust_record"          # earned locally, never transferable
    SERVICE_CATALOG = "service_catalog"    # what this business sells

    # Tier 2 — needs review before it binds anyone
    CASE_TYPE = "case_type"                # a new kind of work
    SCENARIO = "scenario"                  # a newly observed failure pattern
    CAPABILITY_REQUEST = "capability_request"
    VERTICAL_PACK = "vertical_pack"

    # Tier 3 — never an instance's decision
    ENGINE_CODE = "engine_code"
    TOOL_CODE = "tool_code"
    COMPLIANCE_RULE = "compliance_rule"
    TRUST_POLICY = "trust_policy"          # the promotion rules themselves
    SAFETY_BOUND = "safety_bound"


_TIERS: dict[ChangeKind, ChangeTier] = {
    ChangeKind.FACT: ChangeTier.LOCAL,
    ChangeKind.POLICY_VALUE: ChangeTier.LOCAL,
    ChangeKind.PARTY_DATA: ChangeTier.LOCAL,
    ChangeKind.BOOKING_DATA: ChangeTier.LOCAL,
    ChangeKind.TRUST_RECORD: ChangeTier.LOCAL,
    ChangeKind.SERVICE_CATALOG: ChangeTier.LOCAL,

    ChangeKind.CASE_TYPE: ChangeTier.PROPOSED,
    ChangeKind.SCENARIO: ChangeTier.PROPOSED,
    ChangeKind.CAPABILITY_REQUEST: ChangeTier.PROPOSED,
    ChangeKind.VERTICAL_PACK: ChangeTier.PROPOSED,

    ChangeKind.ENGINE_CODE: ChangeTier.PLATFORM,
    ChangeKind.TOOL_CODE: ChangeTier.PLATFORM,
    ChangeKind.COMPLIANCE_RULE: ChangeTier.PLATFORM,
    ChangeKind.TRUST_POLICY: ChangeTier.PLATFORM,
    ChangeKind.SAFETY_BOUND: ChangeTier.PLATFORM,
}


def classify(kind: ChangeKind) -> ChangeTier:
    return _TIERS[kind]


def may_self_apply(kind: ChangeKind) -> bool:
    """Whether an instance can make this change without anyone's approval."""
    return classify(kind) is ChangeTier.LOCAL


@dataclass
class ChangeRequest:
    """An instance asking for something it cannot do itself."""

    kind: ChangeKind
    business_id: uuid.UUID
    summary: str
    evidence: list[str] = field(default_factory=list)
    proposed_payload: dict = field(default_factory=dict)

    request_id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    status: str = "open"          # open | accepted | rejected | shipped
    resolution_note: str = ""

    @property
    def tier(self) -> ChangeTier:
        return classify(self.kind)

    @property
    def is_admissible(self) -> bool:
        """Platform-tier changes cannot be requested by an instance at all.

        Not merely denied — inadmissible, so a compromised or confused instance
        has no channel through which to ask for its own safety rules to change.
        """
        return self.tier is ChangeTier.PROPOSED


def submit(request: ChangeRequest) -> ChangeRequest:
    if request.tier is ChangeTier.LOCAL:
        request.status = "rejected"
        request.resolution_note = "local changes are applied directly, not requested"
        return request

    if not request.is_admissible:
        request.status = "rejected"
        request.resolution_note = (
            f"{request.kind.value} is platform-tier and cannot be requested by an instance"
        )
        log.warning(
            "platform.inadmissible_request",
            kind=request.kind.value,
            business_id=str(request.business_id),
        )
        return request

    log.info(
        "platform.change_requested",
        kind=request.kind.value,
        business_id=str(request.business_id),
        evidence_count=len(request.evidence),
    )
    return request
