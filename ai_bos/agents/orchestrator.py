"""Central orchestrator — the system's single coordinating mind.

Event loop:
1. Drain inbound event queue
2. Classify each event (type, urgency)
3. Dispatch to appropriate specialist agent(s)
4. Monitor running tasks for completion, stalls, conflicts
5. Integrate results and update shared memory
6. Surface owner escalations
7. Schedule next-cycle tasks
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum
from typing import Any

import anthropic

from ai_bos.agents.context import AgentContext
from ai_bos.agents.watchdog import watchdog
from ai_bos.cases.engine import CaseEngine
from ai_bos.cases.states import CaseState
from ai_bos.cases.store import Case
from ai_bos.config import settings
from ai_bos.memory.store import MemoryStore
from ai_bos.tools.executor import ToolExecutor
from ai_bos.logging_config import log, bind_audit_context


class EventType(str, Enum):
    INBOUND_EMAIL = "inbound_email"
    INBOUND_SMS = "inbound_sms"
    INBOUND_CALL = "inbound_call"
    SCHEDULED = "scheduled"
    OWNER_MESSAGE = "owner_message"
    SYSTEM = "system"


@dataclass
class BusinessEvent:
    event_id: uuid.UUID
    business_id: uuid.UUID
    event_type: EventType
    payload: dict[str, Any]
    priority: int = 5   # 1 (highest) to 10 (lowest)


CLASSIFICATION_PROMPT = """You are the orchestrator of an AI Business Operating System.
Classify this incoming event, decide which specialist agent should handle it, and
break it into the discrete pieces of work it actually contains.

A single message often carries several unrelated requests. Each one is separate
work with its own lifecycle — list them all, or the ones you omit will be
silently dropped.

Available case types: {case_types}

Event: {event}

Return JSON:
{{
  "agent": "communication | scheduling | finance | compliance | research | owner_escalation",
  "urgency": "immediate | normal | low",
  "summary": "one sentence description of what needs to be done",
  "requires_owner": false,
  "requests": [
    {{"case_type": "<one of the available case types>", "summary": "what this request is"}}
  ]
}}"""


class Orchestrator:
    def __init__(
        self,
        business_id: uuid.UUID,
        memory: MemoryStore,
        executor: ToolExecutor,
        case_engine: CaseEngine | None = None,
    ) -> None:
        self.business_id = business_id
        self.memory = memory
        self.executor = executor
        # Optional so an orchestrator can still be constructed without the case
        # layer; when absent, events are handled statelessly as before.
        self.case_engine = case_engine
        self._client = anthropic.Anthropic(api_key=settings.anthropic_key)
        self._event_queue: asyncio.Queue[BusinessEvent] = asyncio.Queue()
        self._running = False

    def _now(self) -> datetime:
        return datetime.now(tz=timezone.utc)

    def enqueue(self, event: BusinessEvent) -> None:
        self._event_queue.put_nowait(event)

    async def run(self) -> None:
        """Main orchestrator loop — runs indefinitely."""
        self._running = True
        watchdog.start()
        log.info("orchestrator.started", business_id=str(self.business_id))

        while self._running:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=30.0)
                await self._process_event(event)
            except asyncio.TimeoutError:
                # No events — run maintenance cycle
                await self._maintenance_cycle()
            except Exception as exc:
                log.exception("orchestrator.error", error=str(exc))

    async def _process_event(self, event: BusinessEvent) -> None:
        bind_audit_context(business_id=str(event.business_id))
        log.info("orchestrator.event_received", event_type=event.event_type.value, event_id=str(event.event_id))

        classification = await self._classify_event(event)
        agent_type = classification.get("agent", "communication")

        # Cases are opened before dispatch, so work survives even if the agent
        # step fails. An event that opens no case is an event that can be lost.
        cases = await self.ensure_cases(event, classification, self._now())

        context = AgentContext(
            business_id=self.business_id,
            task_id=uuid.uuid4(),
            agent_type=agent_type,
            action_budget=50.0,   # Default $50 per-task budget
        )

        if classification.get("requires_owner"):
            await self._escalate_to_owner(event, classification)
            for case in cases:
                await self._park_for_owner(case)
            return

        await self._dispatch(agent_type, event, context, cases)

    async def _classify_event(self, event: BusinessEvent) -> dict[str, Any]:
        """Use claude-sonnet-4-6 to classify the event — novel judgment required."""
        try:
            response = self._client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=256,
                messages=[{
                    "role": "user",
                    "content": CLASSIFICATION_PROMPT.format(
                        event=event.payload,
                        case_types=", ".join(self._available_case_types()),
                    ),
                }],
            )
            import json
            return json.loads(response.content[0].text)
        except Exception as exc:
            log.warning("orchestrator.classification_failed", error=str(exc))
            # Fall back to a single general case rather than dropping the event.
            return {
                "agent": "communication",
                "urgency": "normal",
                "requires_owner": False,
                "requests": [
                    {"case_type": "general_inquiry", "summary": "unclassified inbound"}
                ],
            }

    async def _dispatch(
        self,
        agent_type: str,
        event: BusinessEvent,
        context: AgentContext,
        cases: list[Case] | None = None,
    ) -> None:
        """Dispatch event to the appropriate specialist agent."""
        from ai_bos.agents.specialized.communication_agent import CommunicationAgent
        from ai_bos.agents.specialized.scheduling_agent import SchedulingAgent
        from ai_bos.agents.specialized.finance_agent import FinanceAgent

        agents = {
            "communication": CommunicationAgent,
            "scheduling": SchedulingAgent,
            "finance": FinanceAgent,
        }

        agent_class = agents.get(agent_type)
        if not agent_class:
            log.warning("orchestrator.unknown_agent", agent_type=agent_type)
            return

        task_id = str(context.task_id)
        watchdog.register_task(task_id, agent_type)
        try:
            agent = agent_class(context, self.memory, self.executor)
            result = await agent.run(
                {
                    "event": event.payload,
                    "event_type": event.event_type.value,
                    "cases": [
                        {
                            "case_id": str(c.case_id),
                            "case_type": c.case_type,
                            "state": c.state.value,
                            "summary": c.summary,
                        }
                        for c in (cases or [])
                    ],
                }
            )
            log.info("orchestrator.task_complete", agent=agent_type, task_id=task_id, result_status=result.get("status"))
        finally:
            watchdog.complete_task(task_id)

    # ------------------------------------------------------------------- cases

    def _available_case_types(self) -> list[str]:
        if self.case_engine is None:
            return ["general_inquiry"]
        return self.case_engine.registry.all_types()

    async def ensure_cases(
        self,
        event: BusinessEvent,
        classification: dict[str, Any],
        now: datetime,
    ) -> list[Case]:
        """Open or resume the cases this event implies.

        Kept free of any model call so it can be tested directly: the
        classification is an argument, not something fetched in here.

        A message that continues existing work resumes those cases rather than
        opening duplicates. Anything genuinely new gets its own case, one per
        discrete request, which is what stops a compound message from being
        answered once and dropped twice.
        """
        if self.case_engine is None:
            return []

        customer_id = self._customer_id_from(event)
        requests = self._requests_from(classification)

        resumed = await self._resume_existing(customer_id, now)
        if resumed and not self._is_new_work(classification):
            return resumed

        opened: list[Case] = []
        for request in requests:
            case_type = request.get("case_type") or "general_inquiry"
            if case_type not in self.case_engine.registry:
                log.warning(
                    "orchestrator.unknown_case_type",
                    case_type=case_type,
                    falling_back_to="general_inquiry",
                )
                case_type = "general_inquiry"
            opened.append(
                await self.case_engine.open_case(
                    case_type=case_type,
                    summary=request.get("summary", "")[:200],
                    now=now,
                    customer_id=customer_id,
                    context={"event_id": str(event.event_id)},
                )
            )

        log.info(
            "orchestrator.cases_ensured",
            opened=len(opened),
            resumed=len(resumed),
            event_id=str(event.event_id),
        )
        return opened + resumed

    async def _resume_existing(
        self, customer_id: uuid.UUID | None, now: datetime
    ) -> list[Case]:
        """Wake cases that were waiting on this customer.

        A reply arriving is the awaited event; leaving the case in
        WAITING_CUSTOMER would let it time out into ABANDONED despite the
        customer having answered.
        """
        if self.case_engine is None or customer_id is None:
            return []

        existing = await self.case_engine.store.cases_for_customer(
            self.business_id, customer_id
        )
        resumed: list[Case] = []
        for case in existing:
            if case.state is CaseState.WAITING_CUSTOMER:
                resumed.append(
                    await self.case_engine.transition(
                        case, CaseState.OPEN, now, detail="customer replied", actor="customer"
                    )
                )
        return resumed

    async def _park_for_owner(self, case: Case) -> None:
        """Move an escalated event's cases into WAITING_OWNER."""
        if self.case_engine is None:
            return
        from ai_bos.cases.states import can_transition

        if can_transition(case.state, CaseState.WAITING_OWNER):
            await self.case_engine.transition(
                case, CaseState.WAITING_OWNER, self._now(), detail="escalated to owner"
            )

    @staticmethod
    def _requests_from(classification: dict[str, Any]) -> list[dict[str, Any]]:
        requests = classification.get("requests")
        if isinstance(requests, list) and requests:
            return [r for r in requests if isinstance(r, dict)]
        # No breakdown offered — treat the whole event as one piece of work.
        return [
            {
                "case_type": "general_inquiry",
                "summary": classification.get("summary", ""),
            }
        ]

    @staticmethod
    def _is_new_work(classification: dict[str, Any]) -> bool:
        requests = classification.get("requests")
        return isinstance(requests, list) and len(requests) > 0

    @staticmethod
    def _customer_id_from(event: BusinessEvent) -> uuid.UUID | None:
        raw = event.payload.get("customer_id")
        if not raw:
            return None
        try:
            return uuid.UUID(str(raw))
        except (ValueError, AttributeError):
            return None

    async def _escalate_to_owner(self, event: BusinessEvent, classification: dict) -> None:
        log.info("orchestrator.owner_escalation", event_id=str(event.event_id), reason=classification.get("summary"))
        # Owner escalation handled by owner/escalation.py (Layer 7)

    async def _maintenance_cycle(self) -> None:
        """Idle time is when open cases get advanced.

        Without this the system is purely reactive: a case waiting on a third
        party would sit untouched until that party happened to write back,
        which is exactly the silence the case model exists to break.
        """
        if self.case_engine is None:
            log.debug("orchestrator.maintenance_cycle", business_id=str(self.business_id))
            return

        result = await self.case_engine.advance_all(self._now())
        if result.examined:
            log.info(
                "orchestrator.cases_advanced",
                examined=result.examined,
                changed=result.changed,
                escalated=result.escalated,
            )

    def stop(self) -> None:
        self._running = False
        watchdog.stop()
