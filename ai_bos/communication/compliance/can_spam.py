"""CAN-SPAM compliance — enforced in code, not prompts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ComplianceResult(str, Enum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"
    REQUIRES_OPT_OUT_LINK = "REQUIRES_OPT_OUT_LINK"
    REQUIRES_CONSENT = "REQUIRES_CONSENT"


@dataclass
class OutboundEmailCheck:
    to_email: str
    subject: str
    body_text: str
    is_marketing: bool
    has_opt_out_link: bool
    from_email: str
    from_name: str


def check_can_spam(msg: OutboundEmailCheck) -> tuple[ComplianceResult, str]:
    """
    Verify CAN-SPAM compliance. Returns (result, reason).
    Marketing emails require opt-out link and honest subject.
    """
    if not msg.is_marketing:
        return ComplianceResult.ALLOWED, "transactional"

    if not msg.has_opt_out_link:
        return ComplianceResult.REQUIRES_OPT_OUT_LINK, "marketing email requires opt-out link"

    deceptive_subjects = ["re:", "fwd:", "fw:"]
    lower_subject = msg.subject.lower()
    if any(lower_subject.startswith(s) for s in deceptive_subjects) and "re:" not in msg.subject[:3].lower():
        return ComplianceResult.BLOCKED, "deceptive subject line"

    if not msg.from_name or not msg.from_email:
        return ComplianceResult.BLOCKED, "missing sender identification"

    return ComplianceResult.ALLOWED, "can_spam_compliant"
