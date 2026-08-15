"""Case lifecycle states and the transitions between them.

Transitions are validated rather than advisory. The failure this prevents is
the quiet one: a case moving to RESOLVED without the work being done, which
looks identical to success in every downstream report.
"""

from __future__ import annotations

from enum import Enum


class CaseState(str, Enum):
    OPEN = "OPEN"                          # needs work now
    WAITING_CUSTOMER = "WAITING_CUSTOMER"  # replied, awaiting their response
    WAITING_EXTERNAL = "WAITING_EXTERNAL"  # awaiting a third party
    WAITING_OWNER = "WAITING_OWNER"        # escalated, awaiting owner decision
    BLOCKED = "BLOCKED"                    # missing knowledge; feeds the gap ledger
    RESOLVED = "RESOLVED"
    ABANDONED = "ABANDONED"                # closed unresolved


WAITING_STATES = frozenset(
    {CaseState.WAITING_CUSTOMER, CaseState.WAITING_EXTERNAL, CaseState.WAITING_OWNER}
)

TERMINAL_STATES = frozenset({CaseState.RESOLVED, CaseState.ABANDONED})

ACTIVE_STATES = frozenset(CaseState) - TERMINAL_STATES


# A case may only move along these edges.
_ALLOWED: dict[CaseState, frozenset[CaseState]] = {
    CaseState.OPEN: frozenset(
        {
            CaseState.WAITING_CUSTOMER,
            CaseState.WAITING_EXTERNAL,
            CaseState.WAITING_OWNER,
            CaseState.BLOCKED,
            CaseState.RESOLVED,
            CaseState.ABANDONED,
        }
    ),
    # Whatever was awaited arrived (or timed out).
    CaseState.WAITING_CUSTOMER: frozenset(
        {CaseState.OPEN, CaseState.RESOLVED, CaseState.ABANDONED, CaseState.WAITING_OWNER}
    ),
    CaseState.WAITING_EXTERNAL: frozenset(
        {CaseState.OPEN, CaseState.RESOLVED, CaseState.ABANDONED, CaseState.WAITING_OWNER}
    ),
    CaseState.WAITING_OWNER: frozenset(
        {CaseState.OPEN, CaseState.RESOLVED, CaseState.ABANDONED, CaseState.BLOCKED}
    ),
    # Unblocked once the missing fact is supplied.
    CaseState.BLOCKED: frozenset(
        {CaseState.OPEN, CaseState.WAITING_OWNER, CaseState.ABANDONED}
    ),
    # Reopening is legitimate: customers follow up on things we considered done.
    CaseState.RESOLVED: frozenset({CaseState.OPEN}),
    CaseState.ABANDONED: frozenset({CaseState.OPEN}),
}


def can_transition(source: CaseState, target: CaseState) -> bool:
    if source is target:
        return False
    return target in _ALLOWED[source]


def allowed_targets(source: CaseState) -> frozenset[CaseState]:
    return _ALLOWED[source]


class InvalidTransition(Exception):
    def __init__(self, source: CaseState, target: CaseState) -> None:
        super().__init__(
            f"Cannot move a case from {source.value} to {target.value}. "
            f"Allowed: {sorted(t.value for t in allowed_targets(source))}"
        )
        self.source = source
        self.target = target
