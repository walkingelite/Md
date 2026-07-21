"""Layer 5: compliance checks enforce hard rules — not prompt-dependent."""

from ai_bos.communication.compliance.tcpa import check_tcpa
from ai_bos.communication.compliance.hipaa import check_hipaa, contains_phi_patterns
from ai_bos.communication.compliance.can_spam import check_can_spam, OutboundEmailCheck
from ai_bos.communication.compliance.can_spam import ComplianceResult


def test_tcpa_blocks_sms_without_consent():
    result, reason = check_tcpa(
        phone="+15551234567",
        consent_records={},  # no consent
        is_marketing=False,
    )
    assert result == ComplianceResult.BLOCKED
    assert "consent" in reason


def test_tcpa_blocks_marketing_without_marketing_consent():
    result, reason = check_tcpa(
        phone="+15551234567",
        consent_records={"sms": {"type": "transactional"}},
        is_marketing=True,
    )
    assert result == ComplianceResult.BLOCKED


def test_tcpa_allows_with_correct_consent():
    result, reason = check_tcpa(
        phone="+15551234567",
        consent_records={"sms": {"type": "marketing"}},
        is_marketing=True,
    )
    assert result == ComplianceResult.ALLOWED


def test_hipaa_blocks_phi_on_plain_email():
    result, reason = check_hipaa(
        channel="email",
        content="Patient diagnosis: Type 2 diabetes",
        business_regulatory_domains=["HIPAA"],
        llm_phi_detected=False,
    )
    assert result == ComplianceResult.BLOCKED
    assert "PHI" in reason


def test_hipaa_allows_non_phi_on_email():
    result, reason = check_hipaa(
        channel="email",
        content="Your appointment is confirmed for tomorrow at 2pm.",
        business_regulatory_domains=["HIPAA"],
        llm_phi_detected=False,
    )
    assert result == ComplianceResult.ALLOWED


def test_hipaa_not_applied_to_non_covered_entity():
    result, reason = check_hipaa(
        channel="email",
        content="Patient diagnosis: anything",
        business_regulatory_domains=["PCI_DSS"],
        llm_phi_detected=False,
    )
    assert result == ComplianceResult.ALLOWED


def test_phi_pattern_detection():
    assert contains_phi_patterns("Patient diagnosis: diabetes")
    assert contains_phi_patterns("DOB: 01/01/1990")
    assert contains_phi_patterns("SSN: 123-45-6789")
    assert not contains_phi_patterns("Your appointment is at 2pm tomorrow")


def test_can_spam_requires_opt_out_for_marketing():
    msg = OutboundEmailCheck(
        to_email="c@c.com",
        subject="Summer sale!",
        body_text="Check out our deals",
        is_marketing=True,
        has_opt_out_link=False,
        from_email="biz@biz.com",
        from_name="BizName",
    )
    result, reason = check_can_spam(msg)
    assert result == ComplianceResult.REQUIRES_OPT_OUT_LINK


def test_can_spam_allows_transactional_without_opt_out():
    msg = OutboundEmailCheck(
        to_email="c@c.com",
        subject="Your receipt",
        body_text="Thanks for your purchase",
        is_marketing=False,
        has_opt_out_link=False,
        from_email="biz@biz.com",
        from_name="BizName",
    )
    result, _ = check_can_spam(msg)
    assert result == ComplianceResult.ALLOWED
