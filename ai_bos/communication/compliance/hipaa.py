"""HIPAA compliance — PHI detection and channel enforcement. Three independent gates."""

from __future__ import annotations

import re
from typing import Any

from ai_bos.communication.compliance.can_spam import ComplianceResult

# Common PHI patterns (defense in depth alongside LLM classifier)
PHI_PATTERNS = [
    re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),                        # SSN
    re.compile(r'\b(diagnosis|treatment|prescription|medical)\b', re.I),
    re.compile(r'\bDOB\b|\bdate of birth\b|\bborn on\b', re.I),
    re.compile(r'\binsurance (id|number|policy)\b', re.I),
    re.compile(r'\bpatient (id|number|record)\b', re.I),
]

HIPAA_COMPLIANT_CHANNELS = {"encrypted_email", "patient_portal", "secure_sms"}


def contains_phi_patterns(text: str) -> bool:
    """Pattern-based PHI detection (fast path, defense in depth)."""
    return any(p.search(text) for p in PHI_PATTERNS)


def check_hipaa(
    *,
    channel: str,
    content: str,
    business_regulatory_domains: list[str],
    llm_phi_detected: bool = False,
) -> tuple[ComplianceResult, str]:
    """
    Three-gate PHI check:
    1. Business must be subject to HIPAA
    2. Content must not contain PHI on non-compliant channels
    3. Channel must support HIPAA-compliant transmission
    """
    if "HIPAA" not in business_regulatory_domains:
        return ComplianceResult.ALLOWED, "not_hipaa_covered_entity"

    has_phi = contains_phi_patterns(content) or llm_phi_detected

    if has_phi and channel not in HIPAA_COMPLIANT_CHANNELS:
        return (
            ComplianceResult.BLOCKED,
            f"PHI detected but channel '{channel}' is not HIPAA-compliant",
        )

    return ComplianceResult.ALLOWED, "hipaa_compliant"
