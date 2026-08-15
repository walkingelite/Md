"""Case model — durable units of business work that span time.

A message is evidence; a case is the work. One inbound message can open several
cases, and one case can accumulate many messages over weeks. Without this
distinction the system can only react to whatever arrived last, and anything
awaiting a third party silently disappears.

The mechanics here are business-agnostic. What a case *means* — its types,
deadlines and allowed transitions — is supplied as data by a vertical pack.
"""

from ai_bos.cases.states import CaseState, TERMINAL_STATES, WAITING_STATES, can_transition
from ai_bos.cases.definitions import CaseTypeDefinition, CaseTypeRegistry
from ai_bos.cases.store import Case, CaseEvent, CaseStore, InMemoryCaseStore
from ai_bos.cases.engine import CaseEngine, AdvanceResult

__all__ = [
    "CaseState",
    "TERMINAL_STATES",
    "WAITING_STATES",
    "can_transition",
    "CaseTypeDefinition",
    "CaseTypeRegistry",
    "Case",
    "CaseEvent",
    "CaseStore",
    "InMemoryCaseStore",
    "CaseEngine",
    "AdvanceResult",
]
