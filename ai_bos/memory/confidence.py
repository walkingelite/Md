"""Confidence levels and basis types for all knowledge in the system."""

from enum import Enum


class KnowledgeConfidence(str, Enum):
    OWNER_STATED = "OWNER_STATED"       # Owner said it explicitly — act immediately
    DOMAIN_CERTAIN = "DOMAIN_CERTAIN"   # True for all businesses of this type
    DOMAIN_TYPICAL = "DOMAIN_TYPICAL"   # True for most — act but log as assumed
    INFERRED = "INFERRED"               # Reasonable inference — state assumption in outputs
    ASSUMED = "ASSUMED"                 # Default assumption — blocked from action
    UNKNOWN = "UNKNOWN"                 # System knows it doesn't know — hard block


class KnowledgeBasis(str, Enum):
    OBSERVED = "OBSERVED"               # Directly witnessed outcome
    INFERRED = "INFERRED"               # Derived from other facts
    EXTERNAL = "EXTERNAL"               # Fetched from external authoritative source
    ASSUMED = "ASSUMED"                 # Default, no source


# Confidence levels that permit autonomous action
ACTIONABLE_CONFIDENCE = {
    KnowledgeConfidence.OWNER_STATED,
    KnowledgeConfidence.DOMAIN_CERTAIN,
    KnowledgeConfidence.DOMAIN_TYPICAL,
}

# Confidence levels that require verification before action
VERIFY_BEFORE_ACTION = {KnowledgeConfidence.INFERRED}

# Confidence levels that hard-block action
BLOCKED_CONFIDENCE = {KnowledgeConfidence.ASSUMED, KnowledgeConfidence.UNKNOWN}
