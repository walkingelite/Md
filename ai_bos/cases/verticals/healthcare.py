"""Healthcare / dental case types.

Every entry here is data. The engine has no knowledge of dentistry; swapping
this module for a trades or hospitality pack changes what the business does
without touching a line of engine code.
"""

from __future__ import annotations

from ai_bos.cases.definitions import GENERIC_DEFINITIONS, CaseTypeDefinition, CaseTypeRegistry
from ai_bos.cases.states import CaseState

HOUR = 3600.0
DAY = 24 * HOUR

DENTAL_DEFINITIONS: list[CaseTypeDefinition] = [
    CaseTypeDefinition(
        case_type="new_patient_inquiry",
        description="Prospective patient asking about becoming a patient.",
        dwell_limits_seconds={
            CaseState.OPEN: 2 * HOUR,
            CaseState.WAITING_CUSTOMER: 5 * DAY,
        },
        on_timeout={CaseState.WAITING_CUSTOMER: CaseState.ABANDONED},
        priority=3,
    ),
    CaseTypeDefinition(
        case_type="appointment_request",
        description="Book, move or cancel an appointment.",
        dwell_limits_seconds={
            CaseState.OPEN: 2 * HOUR,
            CaseState.WAITING_CUSTOMER: 2 * DAY,
        },
        on_timeout={CaseState.WAITING_CUSTOMER: CaseState.ABANDONED},
        required_facts=("appointment_slot", "appointment_type"),
        priority=3,
    ),
    CaseTypeDefinition(
        case_type="insurance_verification",
        description="Confirm coverage and benefits with the carrier.",
        dwell_limits_seconds={
            CaseState.OPEN: 4 * HOUR,
            # Carriers are slow; ten days before anyone is chased.
            CaseState.WAITING_EXTERNAL: 10 * DAY,
        },
        on_timeout={CaseState.WAITING_EXTERNAL: CaseState.WAITING_OWNER},
        required_facts=("carrier", "member_id"),
        priority=4,
    ),
    CaseTypeDefinition(
        case_type="claim_submission",
        description="Submit and track a claim through to payment.",
        dwell_limits_seconds={
            CaseState.OPEN: 1 * DAY,
            CaseState.WAITING_EXTERNAL: 30 * DAY,
        },
        on_timeout={CaseState.WAITING_EXTERNAL: CaseState.WAITING_OWNER},
        required_facts=("procedure_codes", "carrier"),
        priority=4,
        requires_owner_signoff=True,
    ),
    CaseTypeDefinition(
        case_type="payment_collection",
        description="Collect an outstanding patient balance.",
        dwell_limits_seconds={
            CaseState.OPEN: 2 * DAY,
            CaseState.WAITING_CUSTOMER: 14 * DAY,
        },
        on_timeout={CaseState.WAITING_CUSTOMER: CaseState.WAITING_OWNER},
        priority=5,
        requires_owner_signoff=True,
    ),
    CaseTypeDefinition(
        case_type="recall_scheduling",
        description="Bring a patient back for preventive care when due.",
        dwell_limits_seconds={
            CaseState.OPEN: 7 * DAY,
            CaseState.WAITING_CUSTOMER: 30 * DAY,
        },
        on_timeout={CaseState.WAITING_CUSTOMER: CaseState.ABANDONED},
        priority=7,
    ),
    CaseTypeDefinition(
        case_type="records_request",
        description="Patient or authorised party requesting records.",
        dwell_limits_seconds={
            CaseState.OPEN: 4 * HOUR,
            CaseState.WAITING_OWNER: 8 * HOUR,
        },
        on_timeout={CaseState.WAITING_OWNER: CaseState.OPEN},
        required_facts=("requester_authorization",),
        priority=3,
        requires_owner_signoff=True,
    ),
    CaseTypeDefinition(
        case_type="clinical_urgency",
        description="Possible urgent clinical situation. Never auto-handled.",
        dwell_limits_seconds={
            CaseState.OPEN: 5 * 60,          # five minutes
            CaseState.WAITING_OWNER: 15 * 60,
        },
        # No timeout target: escalation is the only path, never abandonment.
        priority=1,
        requires_owner_signoff=True,
    ),
]


def dental_registry() -> CaseTypeRegistry:
    """Generic case types plus the dental-specific ones."""
    return CaseTypeRegistry(GENERIC_DEFINITIONS + DENTAL_DEFINITIONS)
