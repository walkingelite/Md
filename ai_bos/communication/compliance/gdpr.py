"""GDPR compliance check for outbound communications."""

from __future__ import annotations

from typing import Any

from ai_bos.communication.compliance.can_spam import ComplianceResult


def check_gdpr(
    *,
    recipient_country: str,
    consent_records: dict[str, Any],
    is_marketing: bool,
    channel: str,
) -> tuple[ComplianceResult, str]:
    """Basic GDPR check for EEA recipients."""
    EEA_COUNTRIES = {
        "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
        "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
        "PL", "PT", "RO", "SK", "SI", "ES", "SE", "GB", "NO", "IS", "LI",
    }

    if recipient_country.upper() not in EEA_COUNTRIES:
        return ComplianceResult.ALLOWED, "not_eea_recipient"

    email_consent = consent_records.get("email", {})
    if is_marketing and not email_consent.get("marketing_consent"):
        return ComplianceResult.REQUIRES_CONSENT, "gdpr_marketing_requires_explicit_consent"

    return ComplianceResult.ALLOWED, "gdpr_compliant"
