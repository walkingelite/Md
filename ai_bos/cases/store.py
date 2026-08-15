"""Case records and storage.

Two implementations behind one protocol: in-memory for simulation and tests,
SQLAlchemy for production. The engine only ever sees the protocol, so a
simulated month and a production week exercise identical logic.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Protocol

from ai_bos.cases.states import CaseState, TERMINAL_STATES


@dataclass
class CaseEvent:
    """Append-only record of something that happened to a case."""

    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    case_id: uuid.UUID = field(default_factory=uuid.uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    kind: str = ""              # opened | transitioned | note | message_linked | timeout
    from_state: CaseState | None = None
    to_state: CaseState | None = None
    detail: str = ""
    actor: str = "system"       # system | owner | customer
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Case:
    case_id: uuid.UUID = field(default_factory=uuid.uuid4)
    business_id: uuid.UUID = field(default_factory=uuid.uuid4)
    customer_id: uuid.UUID | None = None

    case_type: str = "general_inquiry"
    state: CaseState = CaseState.OPEN
    summary: str = ""

    opened_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    state_entered_at: datetime = field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
    closed_at: datetime | None = None

    # When the engine must next look at this case. None means nothing scheduled.
    next_action_at: datetime | None = None

    priority: int = 5
    context: dict[str, Any] = field(default_factory=dict)

    # Message IDs that belong to this case. A message may appear in several.
    linked_message_ids: list[uuid.UUID] = field(default_factory=list)

    # Facts this case is waiting on. Populated when BLOCKED; drives the gap ledger.
    missing_facts: list[str] = field(default_factory=list)

    events: list[CaseEvent] = field(default_factory=list)

    @property
    def is_open(self) -> bool:
        return self.state not in TERMINAL_STATES

    def dwell_seconds(self, now: datetime) -> float:
        return (now - self.state_entered_at).total_seconds()

    def age_seconds(self, now: datetime) -> float:
        return (now - self.opened_at).total_seconds()

    def record(self, event: CaseEvent) -> None:
        event.case_id = self.case_id
        self.events.append(event)


class CaseStore(Protocol):
    async def add(self, case: Case) -> Case: ...
    async def get(self, case_id: uuid.UUID) -> Case | None: ...
    async def update(self, case: Case) -> Case: ...
    async def open_cases(self, business_id: uuid.UUID) -> list[Case]: ...
    async def due_cases(self, business_id: uuid.UUID, now: datetime) -> list[Case]: ...
    async def cases_for_customer(
        self, business_id: uuid.UUID, customer_id: uuid.UUID
    ) -> list[Case]: ...


class InMemoryCaseStore:
    """Used by the simulator and the test suite.

    Stores copies rather than references so a caller mutating a returned case
    cannot silently corrupt stored state — the same guarantee the SQL store
    gives for free.
    """

    def __init__(self) -> None:
        self._cases: dict[uuid.UUID, Case] = {}

    async def add(self, case: Case) -> Case:
        if case.case_id in self._cases:
            raise ValueError(f"Case already exists: {case.case_id}")
        self._cases[case.case_id] = _copy_case(case)
        return case

    async def get(self, case_id: uuid.UUID) -> Case | None:
        stored = self._cases.get(case_id)
        return _copy_case(stored) if stored else None

    async def update(self, case: Case) -> Case:
        if case.case_id not in self._cases:
            raise KeyError(f"No such case: {case.case_id}")
        self._cases[case.case_id] = _copy_case(case)
        return case

    async def open_cases(self, business_id: uuid.UUID) -> list[Case]:
        return [
            _copy_case(c)
            for c in self._cases.values()
            if c.business_id == business_id and c.is_open
        ]

    async def due_cases(self, business_id: uuid.UUID, now: datetime) -> list[Case]:
        due = [
            c
            for c in self._cases.values()
            if c.business_id == business_id
            and c.is_open
            and c.next_action_at is not None
            and c.next_action_at <= now
        ]
        # Priority first, then longest-waiting.
        due.sort(key=lambda c: (c.priority, c.next_action_at or now))
        return [_copy_case(c) for c in due]

    async def cases_for_customer(
        self, business_id: uuid.UUID, customer_id: uuid.UUID
    ) -> list[Case]:
        return [
            _copy_case(c)
            for c in self._cases.values()
            if c.business_id == business_id and c.customer_id == customer_id
        ]

    def __len__(self) -> int:
        return len(self._cases)


def _copy_case(case: Case) -> Case:
    """Shallow-copy the record, deep-copying the mutable containers."""
    return replace(
        case,
        context=dict(case.context),
        linked_message_ids=list(case.linked_message_ids),
        missing_facts=list(case.missing_facts),
        events=list(case.events),
    )
