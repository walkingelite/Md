"""The boundary between the platform and the business systems it creates.

Two systems exist: the creator, and the instances it creates. This module
decides what an instance may change by itself, what it may only propose, and
what only the creator can ship.

The split is not a preference. Two facts force it:

  Learning economics — if instances self-maintain, each learns only from its
  own experience. If discoveries flow up and improvements flow down, every
  instance carries the whole fleet's experience. The accumulated record of
  failures found and fixed is the durable advantage, and it only compounds
  when pooled. Patterns travel; records never do.

  Safety — a business system that can rewrite its own compliance gate has no
  compliance gate.

The tension between them is resolved by pushing as much as possible into data,
so an instance adapts broadly without ever modifying code.
"""

from ai_bos.platform.tiers import (
    ChangeTier,
    ChangeRequest,
    ChangeKind,
    classify,
    may_self_apply,
)
from ai_bos.platform.federation import FleetLearning, PatternSubmission

__all__ = [
    "ChangeTier",
    "ChangeKind",
    "ChangeRequest",
    "classify",
    "may_self_apply",
    "FleetLearning",
    "PatternSubmission",
]
