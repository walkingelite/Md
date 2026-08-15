"""Case type definitions — the vertical-specific data the generic engine runs on.

A definition says what a kind of work is called, how long it may sit in each
state before something must happen, and what counts as done. Nothing here is
specific to any industry; healthcare, trades and hospitality each supply their
own registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ai_bos.cases.states import CaseState


@dataclass(frozen=True)
class CaseTypeDefinition:
    case_type: str
    description: str

    # How long a case may dwell in a state before the engine must act.
    # Missing entry means no deadline for that state.
    dwell_limits_seconds: dict[CaseState, float] = field(default_factory=dict)

    # What the engine does when a dwell limit is exceeded.
    on_timeout: dict[CaseState, CaseState] = field(default_factory=dict)

    # Cases of this type may not be auto-resolved without these facts present.
    required_facts: tuple[str, ...] = ()

    # Higher runs first when many cases come due at once.
    priority: int = 5

    # Whether reaching a terminal state requires owner confirmation.
    requires_owner_signoff: bool = False

    def dwell_limit(self, state: CaseState) -> float | None:
        return self.dwell_limits_seconds.get(state)

    def timeout_target(self, state: CaseState) -> CaseState | None:
        return self.on_timeout.get(state)


class CaseTypeRegistry:
    """Holds the case types available to one business.

    Kept as an instance rather than a module global so a simulation run and a
    production business can use different verticals in the same process.
    """

    def __init__(self, definitions: list[CaseTypeDefinition] | None = None) -> None:
        self._by_type: dict[str, CaseTypeDefinition] = {}
        for d in definitions or []:
            self.register(d)

    def register(self, definition: CaseTypeDefinition) -> None:
        if definition.case_type in self._by_type:
            raise ValueError(f"Case type already registered: {definition.case_type}")
        self._by_type[definition.case_type] = definition

    def get(self, case_type: str) -> CaseTypeDefinition | None:
        return self._by_type.get(case_type)

    def require(self, case_type: str) -> CaseTypeDefinition:
        definition = self._by_type.get(case_type)
        if definition is None:
            raise KeyError(
                f"Unknown case type '{case_type}'. "
                f"Registered: {sorted(self._by_type)}"
            )
        return definition

    def all_types(self) -> list[str]:
        return sorted(self._by_type)

    def __len__(self) -> int:
        return len(self._by_type)

    def __contains__(self, case_type: object) -> bool:
        return case_type in self._by_type


# Case types every customer-facing business has, regardless of industry.
GENERIC_DEFINITIONS: list[CaseTypeDefinition] = [
    CaseTypeDefinition(
        case_type="general_inquiry",
        description="A question that does not fit a more specific type.",
        dwell_limits_seconds={
            CaseState.OPEN: 4 * 3600,
            CaseState.WAITING_CUSTOMER: 7 * 24 * 3600,
            CaseState.WAITING_OWNER: 4 * 3600,
        },
        on_timeout={
            CaseState.WAITING_CUSTOMER: CaseState.ABANDONED,
            CaseState.WAITING_OWNER: CaseState.OPEN,
        },
        priority=5,
    ),
    CaseTypeDefinition(
        case_type="complaint",
        description="Customer is dissatisfied and expects resolution.",
        dwell_limits_seconds={
            CaseState.OPEN: 1 * 3600,
            CaseState.WAITING_OWNER: 2 * 3600,
            CaseState.WAITING_CUSTOMER: 3 * 24 * 3600,
        },
        on_timeout={
            CaseState.WAITING_OWNER: CaseState.OPEN,
            CaseState.WAITING_CUSTOMER: CaseState.RESOLVED,
        },
        priority=2,
        requires_owner_signoff=True,
    ),
    CaseTypeDefinition(
        case_type="consent_capture",
        description="Obtain and record consent before using a channel.",
        dwell_limits_seconds={
            CaseState.OPEN: 24 * 3600,
            CaseState.WAITING_CUSTOMER: 14 * 24 * 3600,
        },
        on_timeout={CaseState.WAITING_CUSTOMER: CaseState.ABANDONED},
        required_facts=("consent_channel", "consent_scope"),
        priority=4,
    ),
    CaseTypeDefinition(
        case_type="identity_resolution",
        description="Confirm which customer a contact belongs to.",
        dwell_limits_seconds={
            CaseState.OPEN: 2 * 3600,
            CaseState.WAITING_CUSTOMER: 3 * 24 * 3600,
        },
        on_timeout={CaseState.WAITING_CUSTOMER: CaseState.ABANDONED},
        priority=3,
    ),
]
