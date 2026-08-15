"""The advance-every-open-case cycle.

Each tick the engine finds every case whose next_action_at has arrived and
gives it a chance to move. Cases that exceed a dwell limit are transitioned or
escalated according to their definition, so nothing sits forgotten in a waiting
state — which is the failure the whole case model exists to prevent.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from ai_bos.cases.definitions import CaseTypeRegistry
from ai_bos.cases.states import (
    TERMINAL_STATES,
    CaseState,
    InvalidTransition,
    can_transition,
)
from ai_bos.cases.store import Case, CaseEvent, CaseStore
from ai_bos.logging_config import log

# Applied when a definition sets no dwell limit for the current state, so that
# an open case always has some scheduled reconsideration.
DEFAULT_REVISIT_SECONDS = 24 * 3600


@dataclass
class AdvanceResult:
    """What one tick did. Returned rather than logged only, so the simulator
    can assert on it."""

    examined: int = 0
    transitioned: int = 0
    timed_out: int = 0
    escalated: int = 0
    blocked: int = 0
    unchanged: int = 0
    touched_case_ids: list[uuid.UUID] = field(default_factory=list)

    @property
    def changed(self) -> int:
        return self.transitioned + self.timed_out


class CaseEngine:
    def __init__(
        self,
        business_id: uuid.UUID,
        store: CaseStore,
        registry: CaseTypeRegistry,
    ) -> None:
        self.business_id = business_id
        self.store = store
        self.registry = registry

    # ------------------------------------------------------------------ opening

    async def open_case(
        self,
        *,
        case_type: str,
        summary: str,
        now: datetime,
        customer_id: uuid.UUID | None = None,
        context: dict | None = None,
        message_id: uuid.UUID | None = None,
    ) -> Case:
        definition = self.registry.require(case_type)

        case = Case(
            business_id=self.business_id,
            customer_id=customer_id,
            case_type=case_type,
            state=CaseState.OPEN,
            summary=summary,
            opened_at=now,
            state_entered_at=now,
            priority=definition.priority,
            context=dict(context or {}),
        )
        if message_id:
            case.linked_message_ids.append(message_id)

        case.next_action_at = self._next_action_for(case, now)
        case.record(
            CaseEvent(
                occurred_at=now,
                kind="opened",
                to_state=CaseState.OPEN,
                detail=summary,
            )
        )
        await self.store.add(case)
        log.info(
            "case.opened",
            case_id=str(case.case_id),
            case_type=case_type,
            business_id=str(self.business_id),
        )
        return case

    async def open_cases_for_requests(
        self,
        *,
        requests: list[tuple[str, str]],
        now: datetime,
        customer_id: uuid.UUID | None = None,
        message_id: uuid.UUID | None = None,
    ) -> list[Case]:
        """Open one case per distinct request in a single message.

        This is what stops a compound message ("move my appointment, my
        insurance changed, and send me last year's receipts") from being
        answered once and silently dropped twice.
        """
        opened = []
        for case_type, summary in requests:
            opened.append(
                await self.open_case(
                    case_type=case_type,
                    summary=summary,
                    now=now,
                    customer_id=customer_id,
                    message_id=message_id,
                )
            )
        return opened

    # -------------------------------------------------------------- transitions

    async def transition(
        self,
        case: Case,
        target: CaseState,
        now: datetime,
        *,
        detail: str = "",
        actor: str = "system",
        missing_facts: list[str] | None = None,
    ) -> Case:
        if not can_transition(case.state, target):
            raise InvalidTransition(case.state, target)

        source = case.state
        case.state = target
        case.state_entered_at = now

        if target is CaseState.BLOCKED:
            case.missing_facts = list(missing_facts or case.missing_facts)
        elif source is CaseState.BLOCKED:
            case.missing_facts = []

        if target in TERMINAL_STATES:
            case.closed_at = now
            case.next_action_at = None
        else:
            # Reopening must clear the close stamp, or the case reads as both
            # open and closed and every "closed this month" figure is wrong.
            case.closed_at = None
            case.next_action_at = self._next_action_for(case, now)

        case.record(
            CaseEvent(
                occurred_at=now,
                kind="transitioned",
                from_state=source,
                to_state=target,
                detail=detail,
                actor=actor,
            )
        )
        await self.store.update(case)
        log.info(
            "case.transitioned",
            case_id=str(case.case_id),
            **{"from": source.value},
            to=target.value,
            actor=actor,
        )
        return case

    async def link_message(
        self, case: Case, message_id: uuid.UUID, now: datetime
    ) -> Case:
        if message_id not in case.linked_message_ids:
            case.linked_message_ids.append(message_id)
        case.record(
            CaseEvent(occurred_at=now, kind="message_linked", metadata={"message_id": str(message_id)})
        )
        await self.store.update(case)
        return case

    async def reopen(self, case: Case, now: datetime, detail: str = "") -> Case:
        """Bring a closed case back. Customers follow up on things we called done."""
        return await self.transition(
            case, CaseState.OPEN, now, detail=detail or "reopened by follow-up"
        )

    # -------------------------------------------------------------------- cycle

    async def advance_all(self, now: datetime) -> AdvanceResult:
        """One tick: consider every case whose next_action_at has arrived."""
        result = AdvanceResult()
        due = await self.store.due_cases(self.business_id, now)

        for case in due:
            result.examined += 1
            result.touched_case_ids.append(case.case_id)

            definition = self.registry.get(case.case_type)
            if definition is None:
                # Unknown type: reschedule rather than drop it.
                case.next_action_at = now + timedelta(seconds=DEFAULT_REVISIT_SECONDS)
                await self.store.update(case)
                result.unchanged += 1
                continue

            limit = definition.dwell_limit(case.state)
            if limit is None or case.dwell_seconds(now) < limit:
                case.next_action_at = self._next_action_for(case, now)
                await self.store.update(case)
                result.unchanged += 1
                continue

            target = definition.timeout_target(case.state)
            if target is None:
                # Overdue with nowhere defined to go — the owner decides.
                if can_transition(case.state, CaseState.WAITING_OWNER):
                    await self.transition(
                        case,
                        CaseState.WAITING_OWNER,
                        now,
                        detail=f"exceeded {limit:.0f}s dwell limit in {case.state.value}",
                    )
                    result.escalated += 1
                else:
                    case.next_action_at = now + timedelta(seconds=DEFAULT_REVISIT_SECONDS)
                    await self.store.update(case)
                    result.unchanged += 1
                continue

            await self.transition(
                case,
                target,
                now,
                detail=f"timed out of {case.state.value} after {limit:.0f}s",
            )
            result.timed_out += 1
            if target is CaseState.WAITING_OWNER:
                result.escalated += 1
            elif target is CaseState.BLOCKED:
                result.blocked += 1

        if result.examined:
            log.info(
                "case_engine.tick",
                examined=result.examined,
                changed=result.changed,
                escalated=result.escalated,
            )
        return result

    async def open_case_count(self) -> int:
        return len(await self.store.open_cases(self.business_id))

    async def blocked_cases(self) -> list[Case]:
        return [
            c
            for c in await self.store.open_cases(self.business_id)
            if c.state is CaseState.BLOCKED
        ]

    # ------------------------------------------------------------------ internal

    def _next_action_for(self, case: Case, now: datetime) -> datetime | None:
        if case.state in TERMINAL_STATES:
            return None
        definition = self.registry.get(case.case_type)
        limit = definition.dwell_limit(case.state) if definition else None
        if limit is None:
            return now + timedelta(seconds=DEFAULT_REVISIT_SECONDS)
        # Wake exactly when the dwell limit expires, measured from state entry.
        return case.state_entered_at + timedelta(seconds=limit)
