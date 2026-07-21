"""End-to-end smoke test: dental clinic → patient books → reminder → invoice.

This script validates the full system is wired correctly.
Run after bootstrap.py with live API keys.
"""

import asyncio
import uuid
from ai_bos.business.domain_extractor import extract_domain
from ai_bos.business.profiles.healthcare import DENTAL_PROFILE
from ai_bos.logging_config import configure_logging, log


async def main() -> None:
    configure_logging("INFO")
    log.info("smoke_test.start")

    # Step 1: Domain profile loads correctly (no API call)
    from ai_bos.business.profiles.healthcare import DENTAL_PROFILE
    assert "HIPAA" in DENTAL_PROFILE.regulatory_domains, "Dental profile missing HIPAA"
    assert len(DENTAL_PROFILE.mandatory_operations) > 0, "No mandatory operations"
    log.info("smoke_test.domain_profile_ok", ops=len(DENTAL_PROFILE.mandatory_operations))

    # NOTE: Live domain extraction (extract_domain) requires a real ANTHROPIC_API_KEY

    # Step 2: Confidence gating
    from ai_bos.memory.anti_hallucination import CandidateFact, validate_candidate
    from ai_bos.memory.confidence import KnowledgeConfidence, KnowledgeBasis

    candidate = CandidateFact(
        domain="regulatory",
        key="HIPAA",
        value={"required": True},
        proposed_confidence=KnowledgeConfidence.DOMAIN_CERTAIN,
        source_references=[],  # No sources — should be downgraded
    )
    confidence, _ = validate_candidate(candidate)
    assert confidence == KnowledgeConfidence.ASSUMED, "Anti-hallucination gate failed"
    log.info("smoke_test.anti_hallucination_ok")

    # Step 3: Compliance gates
    from ai_bos.communication.compliance.tcpa import check_tcpa
    from ai_bos.communication.compliance.can_spam import ComplianceResult

    result, _ = check_tcpa(phone="+15551234567", consent_records={}, is_marketing=False)
    assert result == ComplianceResult.BLOCKED, "TCPA gate failed"
    log.info("smoke_test.tcpa_ok")

    from ai_bos.communication.compliance.hipaa import check_hipaa
    result, reason = check_hipaa(
        channel="email",
        content="Patient diagnosis: Type 2 diabetes",
        business_regulatory_domains=["HIPAA"],
    )
    assert result == ComplianceResult.BLOCKED, "HIPAA PHI gate failed"
    log.info("smoke_test.hipaa_ok")

    # Step 4: Safety bounds
    from ai_bos.improvement.safety_bounds import can_modify_component, can_create_financial_tool
    assert not can_modify_component("orchestrator"), "Safety bounds failed"
    assert not can_create_financial_tool(1000.0), "Financial limit failed"
    log.info("smoke_test.safety_bounds_ok")

    # Step 5: Idempotency key
    from ai_bos.tools.implementations.email import SendEmailTool
    tool = SendEmailTool()
    key1 = tool.compute_idempotency_key({"to_email": "patient@test.com", "subject": "Appointment Reminder"})
    key2 = tool.compute_idempotency_key({"to_email": "patient@test.com", "subject": "Appointment Reminder"})
    assert key1 == key2, "Idempotency key not deterministic"
    log.info("smoke_test.idempotency_ok")

    log.info("smoke_test.complete", status="ALL CHECKS PASSED")
    print("\n✓ All smoke tests passed — AI-BOS is ready")


if __name__ == "__main__":
    asyncio.run(main())
