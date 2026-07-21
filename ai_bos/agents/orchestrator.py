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
from dataclasses import dataclass
from enum import Enum
from typing import Any

import anthropic

from ai_bos.agents.context import AgentContext
from ai_bos.agents.watchdog import watchdog
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
Classify this incoming event and decide which specialist agent should handle it.

Event: {event}

Return JSON:
{
  "agent": "communication | scheduling | finance | compliance | research | owner_escalation",
  "urgency": "immediate | normal | low",
  "summary": "one sentence description of what needs to be done",
  "requires_owner": false
}"""


class Orchestrator:
    def __init__(
        self,
        business_id: uuid.UUID,
        memory: MemoryStore,
        executor: ToolExecutor,
    ) -> None:
        self.business_id = business_id
        self.memory = memory
        self.executor = executor
        self._client = anthropic.Anthropic(api_key=settings.anthropic_key)
        self._event_queue: asyncio.Queue[BusinessEvent] = asyncio.Queue()
        self._running = False

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

        context = AgentContext(
            business_id=self.business_id,
            task_id=uuid.uuid4(),
            agent_type=agent_type,
            action_budget=50.0,   # Default $50 per-task budget
        )

        if classification.get("requires_owner"):
            await self._escalate_to_owner(event, classification)
            return

        await self._dispatch(agent_type, event, context)

    async def _classify_event(self, event: BusinessEvent) -> dict[str, Any]:
        """Use claude-sonnet-4-6 to classify the event — novel judgment required."""
        try:
            response = self._client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=256,
                messages=[{
                    "role": "user",
                    "content": CLASSIFICATION_PROMPT.format(event=event.payload),
                }],
            )
            import json
            return json.loads(response.content[0].text)
        except Exception as exc:
            log.warning("orchestrator.classification_failed", error=str(exc))
            # Fallback to communication agent for unknown events
            return {"agent": "communication", "urgency": "normal", "requires_owner": False}

    async def _dispatch(
        self, agent_type: str, event: BusinessEvent, context: AgentContext
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
            result = await agent.run({"event": event.payload, "event_type": event.event_type.value})
            log.info("orchestrator.task_complete", agent=agent_type, task_id=task_id, result_status=result.get("status"))
        finally:
            watchdog.complete_task(task_id)

    async def _escalate_to_owner(self, event: BusinessEvent, classification: dict) -> None:
        log.info("orchestrator.owner_escalation", event_id=str(event.event_id), reason=classification.get("summary"))
        # Owner escalation handled by owner/escalation.py (Layer 7)

    async def _maintenance_cycle(self) -> None:
        log.debug("orchestrator.maintenance_cycle", business_id=str(self.business_id))

    def stop(self) -> None:
        self._running = False
        watchdog.stop()
