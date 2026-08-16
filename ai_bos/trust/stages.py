"""The four rungs of the trust ladder."""

from __future__ import annotations

from enum import Enum


class TrustStage(str, Enum):
    SHADOW = "SHADOW"                  # decides, sends nothing, logs what it would do
    DRAFT = "DRAFT"                    # drafts, owner approves before sending
    AUTO_WITH_RECALL = "AUTO_WITH_RECALL"  # sends, undo window, live feed
    AUTO = "AUTO"                      # sends, appears in the weekly digest


STAGE_ORDER: tuple[TrustStage, ...] = (
    TrustStage.SHADOW,
    TrustStage.DRAFT,
    TrustStage.AUTO_WITH_RECALL,
    TrustStage.AUTO,
)

_INDEX = {stage: i for i, stage in enumerate(STAGE_ORDER)}


def next_stage(stage: TrustStage) -> TrustStage | None:
    i = _INDEX[stage]
    return STAGE_ORDER[i + 1] if i + 1 < len(STAGE_ORDER) else None


def previous_stage(stage: TrustStage) -> TrustStage | None:
    i = _INDEX[stage]
    return STAGE_ORDER[i - 1] if i > 0 else None


def rank(stage: TrustStage) -> int:
    return _INDEX[stage]


def at_least(stage: TrustStage, minimum: TrustStage) -> bool:
    return rank(stage) >= rank(minimum)
