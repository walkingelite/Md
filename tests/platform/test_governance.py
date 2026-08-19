"""Platform governance: what an instance may change, and what it may never ask for."""

import uuid

from ai_bos.platform.federation import (
    CORROBORATION_THRESHOLD,
    FleetLearning,
    PatternSubmission,
    redact,
)
from ai_bos.platform.tiers import (
    ChangeKind,
    ChangeRequest,
    ChangeTier,
    classify,
    may_self_apply,
    submit,
)


def _request(kind: ChangeKind) -> ChangeRequest:
    return ChangeRequest(kind=kind, business_id=uuid.uuid4(), summary="test")


# ---------------------------------------------------------------------- tiers

def test_business_reality_is_instance_local():
    for kind in (
        ChangeKind.FACT,
        ChangeKind.POLICY_VALUE,
        ChangeKind.PARTY_DATA,
        ChangeKind.SERVICE_CATALOG,
        ChangeKind.TRUST_RECORD,
    ):
        assert may_self_apply(kind), f"{kind} should be local"


def test_new_kinds_of_work_need_review():
    for kind in (ChangeKind.CASE_TYPE, ChangeKind.SCENARIO, ChangeKind.VERTICAL_PACK):
        assert classify(kind) is ChangeTier.PROPOSED
        assert not may_self_apply(kind)


def test_safety_machinery_is_platform_only():
    for kind in (
        ChangeKind.COMPLIANCE_RULE,
        ChangeKind.SAFETY_BOUND,
        ChangeKind.TRUST_POLICY,
        ChangeKind.ENGINE_CODE,
        ChangeKind.TOOL_CODE,
    ):
        assert classify(kind) is ChangeTier.PLATFORM
        assert not may_self_apply(kind)


def test_every_change_kind_has_a_tier():
    for kind in ChangeKind:
        assert classify(kind) in ChangeTier


# ------------------------------------------------------------------- requests

def test_instance_cannot_request_its_own_safety_rules_change():
    """Inadmissible rather than merely denied: a confused or compromised
    instance must have no channel through which to ask."""
    for kind in (ChangeKind.COMPLIANCE_RULE, ChangeKind.SAFETY_BOUND, ChangeKind.TRUST_POLICY):
        request = submit(_request(kind))
        assert request.status == "rejected"
        assert not request.is_admissible
        assert "platform-tier" in request.resolution_note


def test_local_changes_are_applied_not_requested():
    request = submit(_request(ChangeKind.FACT))
    assert request.status == "rejected"
    assert "applied directly" in request.resolution_note


def test_proposed_changes_are_accepted_for_review():
    request = submit(_request(ChangeKind.CASE_TYPE))
    assert request.status == "open"
    assert request.is_admissible


# ------------------------------------------------------------------ redaction

def test_identifiers_are_stripped_on_the_way_out():
    text = "Contact maria@example.com or +1 555 010 2233 about 123-45-6789"
    clean = redact(text)
    assert "maria@example.com" not in clean
    assert "555" not in clean
    assert "123-45-6789" not in clean


def test_submission_is_redacted_regardless_of_what_the_instance_sends():
    """An instance cannot opt into sending records by mislabelling them."""
    fleet = FleetLearning()
    fleet.submit(
        PatternSubmission(
            kind=ChangeKind.SCENARIO,
            business_id=uuid.uuid4(),
            vertical="dental",
            signature="asks_about_payment_plans",
            description="James Chen at james@example.com asked",
            example_text="call me on +15550001",
        )
    )
    pattern = fleet.emerging()[0]
    assert "james@example.com" not in " ".join(pattern.descriptions)
    assert "example.com" not in " ".join(pattern.descriptions)


# ----------------------------------------------------------------- federation

def test_pattern_needs_independent_corroboration():
    """One business's quirk is not a fleet-wide truth."""
    fleet = FleetLearning()
    for _ in range(CORROBORATION_THRESHOLD - 1):
        fleet.submit(
            PatternSubmission(
                kind=ChangeKind.SCENARIO,
                business_id=uuid.uuid4(),
                vertical="dental",
                signature="asks_about_payment_plans",
            )
        )
    assert fleet.corroborated() == []

    fleet.submit(
        PatternSubmission(
            kind=ChangeKind.SCENARIO,
            business_id=uuid.uuid4(),
            vertical="dental",
            signature="asks_about_payment_plans",
        )
    )
    assert len(fleet.corroborated()) == 1


def test_one_business_reporting_repeatedly_does_not_corroborate_itself():
    fleet = FleetLearning()
    same = uuid.uuid4()
    for _ in range(50):
        fleet.submit(
            PatternSubmission(
                kind=ChangeKind.SCENARIO,
                business_id=same,
                vertical="dental",
                signature="quirk",
            )
        )
    assert fleet.corroborated() == []
    assert fleet.emerging()[0].corroboration == 1


def test_patterns_are_scoped_by_vertical():
    fleet = FleetLearning()
    for vertical in ("dental", "plumbing"):
        for _ in range(CORROBORATION_THRESHOLD):
            fleet.submit(
                PatternSubmission(
                    kind=ChangeKind.SCENARIO,
                    business_id=uuid.uuid4(),
                    vertical=vertical,
                    signature="after_hours_contact",
                )
            )
    assert len(fleet.corroborated("dental")) == 1
    assert len(fleet.corroborated("plumbing")) == 1
    assert len(fleet.corroborated()) == 2


def test_empty_signature_is_rejected():
    fleet = FleetLearning()
    assert fleet.submit(
        PatternSubmission(
            kind=ChangeKind.SCENARIO,
            business_id=uuid.uuid4(),
            vertical="dental",
            signature="   ",
        )
    ) is None
