"""Finance agent — invoicing, billing, payment tracking."""

from __future__ import annotations

from typing import Any

from ai_bos.agents.base_agent import BaseAgent
from ai_bos.logging_config import log

FINANCE_ROLE = """Your role: handle all financial operations.
- Create and send invoices
- Track payment status
- Follow up on overdue invoices
- Generate financial summaries
- Never create a charge without explicit customer agreement on the amount
- Flag any unusual payment patterns to the orchestrator"""


class FinanceAgent(BaseAgent):
    agent_type = "finance"

    async def run(self, task: dict[str, Any]) -> dict[str, Any]:
        event = task.get("event", {})
        log.info("finance_agent.run", task_keys=list(event.keys()))

        memory_context = await self._query_memory("billing invoicing payments", domain="operational")
        system_prompt = self._build_system_prompt(FINANCE_ROLE, memory_context)
        self._increment_step()

        response = self._client.messages.create(
            model=self.default_model,
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": f"Handle finance task: {event}"}],
        )
        return {"status": "handled", "result": response.content[0].text}
