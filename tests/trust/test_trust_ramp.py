"""Trust ramp: promotion arithmetic, ceilings, demotion, and the gate."""

import uuid

import pytest

from ai_bos.trust.gate import GateAction, TrustGate
from ai_bos.trust.ledger import ApprovalRecord, TrustLedger
from ai_bos.trust.policy import CapabilityPolicy, TrustPolicy
from ai_bos.trust.stages import STAGE_ORDER, TrustStage, next_stage, previous_stage


def _ledger() -> TrustLedger:
    return TrustLedger(business_id=uuid.uuid4())


def _approve(ledger: TrustLedger, capability: str, n: int, edited: bool = False):
    last = None
    for _ in range(n):
        last = ledger.record(
            ApprovalRecord(capability=capability, approved=True, edited=edited)
        )
    return last


# ------------------------------------------------------------------------ stages

def test_stage_order_is_monotonic():
    for i, stage in enumerate(STAGE_ORDER):
        if i + 1 < len(STAGE_ORDER):
            assert next_stage(stage) is STAGE_ORDER[i + 1]
        else:
            assert next_stage(stage) is None
    assert previous_stage(TrustStage.SHADOW) is None


def test_everything_starts_in_shadow():
    ledger = _ledger()
    assert ledger.stage_for("appointment_reminder") is TrustStage.SHADOW


def test_unregistered_capability_is_pinned_to_shadow():
    """An unknown capability is not implicitly trusted."""
    ledger = _ledger()
    assert ledger.stage_for("something_nobody_declared") is TrustStage.SHADOW
    _approve(ledger, "something_nobody_declared", 500)
    assert ledger.stage_for("something_nobody_declared") is TrustStage.SHADOW


# --------------------------------------------------------------------- promotion

def test_promotion_requires_the_full_threshold():
    ledger = _ledger()
    _approve(ledger, "appointment_reminder", 19)
    assert ledger.stage_for("appointment_reminder") is TrustStage.SHADOW

    decision = _approve(ledger, "appointment_reminder", 1)
    assert decision is not None and decision.promoted
    assert ledger.stage_for("appointment_reminder") is TrustStage.DRAFT


def test_edited_approvals_do_not_count():
    """An approval the owner had to edit is evidence the system was wrong."""
    ledger = _ledger()
    _approve(ledger, "appointment_reminder", 30, edited=True)
    assert ledger.stage_for("appointment_reminder") is TrustStage.SHADOW
    assert ledger.clean_streak("appointment_reminder") == 0


def test_full_climb_to_auto():
    ledger = _ledger()
    cap = "appointment_confirmation"
    _approve(ledger, cap, 20)
    assert ledger.stage_for(cap) is TrustStage.DRAFT
    _approve(ledger, cap, 50)
    assert ledger.stage_for(cap) is TrustStage.AUTO_WITH_RECALL
    _approve(ledger, cap, 100)
    assert ledger.stage_for(cap) is TrustStage.AUTO


# ----------------------------------------------------------------------- ceilings

def test_ceiling_is_never_exceeded_by_good_behaviour():
    ledger = _ledger()
    _approve(ledger, "general_reply", 40 + 120 + 250 + 500)
    assert ledger.stage_for("general_reply") is TrustStage.AUTO_WITH_RECALL


def test_money_never_reaches_unattended_autonomy():
    ledger = _ledger()
    _approve(ledger, "send_invoice", 100 + 500 + 1000)
    assert ledger.stage_for("send_invoice") is TrustStage.AUTO_WITH_RECALL


def test_price_quotes_stay_owner_approved_forever():
    ledger = _ledger()
    _approve(ledger, "quote_price", 5000)
    assert ledger.stage_for("quote_price") is TrustStage.DRAFT


def test_regulated_disclosure_never_leaves_shadow():
    ledger = _ledger()
    _approve(ledger, "disclose_regulated_data", 10_000)
    assert ledger.stage_for("disclose_regulated_data") is TrustStage.SHADOW


def test_set_stage_rejects_exceeding_ceiling():
    ledger = _ledger()
    with pytest.raises(ValueError):
        ledger.set_stage("quote_price", TrustStage.AUTO)


# ---------------------------------------------------------------------- demotion

def test_rejections_demote():
    ledger = _ledger()
    cap = "appointment_confirmation"
    _approve(ledger, cap, 20)
    assert ledger.stage_for(cap) is TrustStage.DRAFT

    for _ in range(2):
        ledger.record(ApprovalRecord(capability=cap, approved=False))
    assert ledger.stage_for(cap) is TrustStage.SHADOW


def test_single_rejection_demotes_low_tolerance_capability():
    ledger = _ledger()
    _approve(ledger, "send_invoice", 100)
    assert ledger.stage_for("send_invoice") is TrustStage.DRAFT
    ledger.record(ApprovalRecord(capability="send_invoice", approved=False))
    assert ledger.stage_for("send_invoice") is TrustStage.SHADOW


def test_rejection_resets_the_streak():
    ledger = _ledger()
    cap = "appointment_reminder"
    _approve(ledger, cap, 15)
    ledger.record(ApprovalRecord(capability=cap, approved=False))
    assert ledger.clean_streak(cap) == 0


# -------------------------------------------------------------------------- gate

def test_gate_maps_each_stage_to_an_action():
    ledger = _ledger()
    gate = TrustGate(ledger)
    cap = "appointment_confirmation"

    assert gate.decide(cap).action is GateAction.LOG_ONLY
    _approve(ledger, cap, 20)
    assert gate.decide(cap).action is GateAction.QUEUE_FOR_APPROVAL
    _approve(ledger, cap, 50)
    d = gate.decide(cap)
    assert d.action is GateAction.SEND_WITH_RECALL
    assert d.recall_window_seconds > 0
    _approve(ledger, cap, 100)
    assert gate.decide(cap).action is GateAction.SEND


def test_shadow_never_reaches_the_customer():
    gate = TrustGate(_ledger())
    assert not gate.decide("appointment_reminder").will_reach_customer


def test_force_supervision_can_tighten_but_not_loosen():
    ledger = _ledger()
    gate = TrustGate(ledger)
    cap = "appointment_confirmation"
    _approve(ledger, cap, 20 + 50 + 100)
    assert gate.decide(cap).action is GateAction.SEND

    forced = gate.decide(cap, force_supervision=True)
    assert forced.action is GateAction.QUEUE_FOR_APPROVAL
    assert not forced.will_reach_customer

    # Forcing supervision on a shadow capability must not promote it to a draft.
    shadow = gate.decide("disclose_regulated_data", force_supervision=True)
    assert shadow.action is GateAction.LOG_ONLY


# ----------------------------------------------------------------------- reporting

def test_summary_reports_progress_per_capability():
    ledger = _ledger()
    _approve(ledger, "appointment_reminder", 5)
    row = next(
        r for r in ledger.summary() if r["capability"] == "appointment_reminder"
    )
    assert row["stage"] == "SHADOW"
    assert row["clean_streak"] == 5
    assert row["needed"] == 20
    assert row["approval_rate"] == 1.0


def test_approval_rate_is_none_before_any_record():
    assert _ledger().approval_rate("appointment_reminder") is None


def test_custom_policy_overrides_defaults():
    policy = TrustPolicy(
        [
            CapabilityPolicy(
                capability="fast_track",
                promotion_thresholds={TrustStage.SHADOW: 2},
                ceiling=TrustStage.DRAFT,
            )
        ]
    )
    ledger = TrustLedger(business_id=uuid.uuid4(), policy=policy)
    _approve(ledger, "fast_track", 2)
    assert ledger.stage_for("fast_track") is TrustStage.DRAFT
