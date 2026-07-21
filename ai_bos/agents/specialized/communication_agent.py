"""Communication agent — handles all inbound and outbound messages."""

from __future__ import annotations

from typing import Any

from ai_bos.agents.base_agent import BaseAgent
from ai_bos.agents.conflict_resolver import ConflictResolver
from ai_bos.logging_config import log

_resolver = ConflictResolver()

COMMUNICATION_ROLE = """Your role: handle customer communications.
- Respond to inbound inquiries with the appropriate information
- Draft and send emails and SMS messages when needed
- Maintain consistent brand voice
- Never send duplicate messages to the same customer
- Never send PHI over unencrypted channels
- For any message to a customer: check consent status first"""


class CommunicationAgent(BaseAgent):
    agent_type = "communication"

    async def run(self, task: dict[str, Any]) -> dict[str, Any]:
        event_type = task.get("event_type", "")
        event = task.get("event", {})
        customer_id = event.get("customer_id", "unknown")

        log.info("communication_agent.run", event_type=event_type, customer_id=customer_id)

        # Acquire send lock — prevents duplicate messages
        business_id = str(self.context.business_id)
        lock_acquired = await _resolver.acquire_send_lock(customer_id, business_id, self.agent_type)
        if not lock_acquired:
            log.warning("communication_agent.send_lock_failed", customer_id=customer_id)
            return {"status": "skipped", "reason": "send_lock_held"}

        try:
            memory_context = await self._query_memory(
                f"customer communication {event_type}", domain="operational"
            )
            system_prompt = self._build_system_prompt(COMMUNICATION_ROLE, memory_context)
            self._increment_step()

            # Use haiku for routine drafting
            response = self._client.messages.create(
                model=self.default_model,
                max_tokens=512,
                system=system_prompt,
                messages=[{"role": "user", "content": f"Handle this event: {event}"}],
            )
            draft = response.content[0].text
            log.info("communication_agent.draft_ready", customer_id=customer_id)
            return {"status": "handled", "draft": draft}
        finally:
            await _resolver.release_send_lock(customer_id, business_id)
