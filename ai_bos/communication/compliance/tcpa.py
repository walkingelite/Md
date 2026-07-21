"""TCPA compliance — consent required before any outbound SMS. Enforced in code."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ai_bos.communication.compliance.can_spam import ComplianceResult


def check_tcpa(
    *,
    phone: str,
    consent_records: dict[str, Any],
    is_marketing: bool,
) -> tuple[ComplianceResult, str]:
    """
    TCPA requires prior express written consent for marketing SMS.
    Transactional SMS requires prior express consent.
    No consent = hard block — no exceptions.
    """
    sms_consent = consent_records.get("sms", {})

    if not sms_consent:
        return ComplianceResult.BLOCKED, "no_sms_consent_on_record"

    if is_marketing and sms_consent.get("type") != "marketing":
        return ComplianceResult.BLOCKED, "marketing_sms_requires_express_written_consent"

    # Check consent hasn't been revoked
    if sms_consent.get("revoked_at"):
        return ComplianceResult.BLOCKED, "sms_consent_revoked"

    return ComplianceResult.ALLOWED, "tcpa_compliant"
