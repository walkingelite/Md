"""Scheduling agent — manages appointments and calendar."""

from __future__ import annotations

from typing import Any

from ai_bos.agents.base_agent import BaseAgent
from ai_bos.logging_config import log

SCHEDULING_ROLE = """Your role: manage the business calendar and scheduling.
- Check availability before booking
- Prevent double-booking (use check_availability tool first)
- Account for preparation and cleanup time between appointments
- Send confirmation to customers after booking
- Normalize all times to UTC internally; display in customer's local timezone"""


class SchedulingAgent(BaseAgent):
    agent_type = "scheduling"

    async def run(self, task: dict[str, Any]) -> dict[str, Any]:
        event = task.get("event", {})
        log.info("scheduling_agent.run", task_keys=list(event.keys()))

        memory_context = await self._query_memory("scheduling appointments calendar", domain="operational")
        system_prompt = self._build_system_prompt(SCHEDULING_ROLE, memory_context)
        self._increment_step()

        response = self._client.messages.create(
            model=self.default_model,
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": f"Handle scheduling task: {event}"}],
        )
        return {"status": "handled", "result": response.content[0].text}
