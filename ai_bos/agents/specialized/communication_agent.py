"""Communication agent — drafts a reply, then dispatches it through the executor.

The loop closes here: the agent produces a draft, hands it to the executor, and
moves its case according to what actually happened. It does not decide whether
the message is allowed to go out — the trust gate inside the executor does, and
the agent only observes the outcome.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from ai_bos.agents.base_agent import BaseAgent
from ai_bos.agents.conflict_resolver import ConflictResolver
from ai_bos.cases.states import CaseState
from ai_bos.logging_config import log
from ai_bos.tools.base import ExecutionContext, ToolResultStatus

_resolver = ConflictResolver()

COMMUNICATION_ROLE = """Your role: handle customer communications.
- Respond to inbound inquiries using only facts on record
- Never invent a policy, price, or commitment the business has not stated
- If a required fact is missing, say so plainly rather than guessing
- Maintain a consistent, plain, unfussy voice
- Never send regulated data over an unverified channel"""

# Maps the case being worked to the capability the trust ledger governs.
CASE_TYPE_TO_CAPABILITY = {
    "appointment_request": "appointment_confirmation",
    "recall_scheduling": "appointment_reminder",
    "payment_collection": "send_invoice",
    "records_request": "disclose_regulated_data",
    "general_inquiry": "general_reply",
}
DEFAULT_CAPABILITY = "general_reply"


class CommunicationAgent(BaseAgent):
    agent_type = "communication"

    async def run(self, task: dict[str, Any]) -> dict[str, Any]:
        event = task.get("event", {})
        cases = task.get("cases", []) or []
        case_engine = task.get("case_engine")

        customer_id = str(event.get("customer_id") or "unknown")
        business_id = str(self.context.business_id)

        # One outbound message per customer at a time, regardless of how many
        # agents are working their cases.
        if not await _resolver.acquire_send_lock(customer_id, business_id, self.agent_type):
            log.warning("communication_agent.send_lock_held", customer_id=customer_id)
            return {"status": "deferred", "reason": "send_lock_held"}

        try:
            draft = await self._draft(event, cases)
            capability = self._capability_for(cases)
            result = await self._dispatch(event, draft, capability)
            await self._settle_cases(case_engine, cases, result.status)

            return {
                "status": "handled",
                "capability": capability,
                "tool_status": result.status.value,
                "reached_customer": result.status
                in (ToolResultStatus.EXECUTED, ToolResultStatus.CONFIRMED,
                    ToolResultStatus.EXECUTED_UNVERIFIED),
                "draft": draft,
            }
        finally:
            await _resolver.release_send_lock(customer_id, business_id)

    # ------------------------------------------------------------------ internals

    async def _draft(self, event: dict, cases: list[dict]) -> str:
        memory_context = await self._query_memory(
            f"customer communication {event.get('text', '')[:120]}", domain="operational"
        )
        case_lines = "\n".join(
            f"- {c.get('case_type')} ({c.get('state')}): {c.get('summary')}" for c in cases
        )
        system_prompt = self._build_system_prompt(
            f"{COMMUNICATION_ROLE}\n\nOpen work for this customer:\n{case_lines or '(none)'}",
            memory_context,
        )
        self._increment_step()

        response = self._client.messages.create(
            model=self.default_model,
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": f"Inbound: {event.get('text', '')}"}],
        )
        return response.content[0].text

    def _capability_for(self, cases: list[dict]) -> str:
        """The most restricted capability among the open cases governs the send.

        A message that touches records and a booking is governed by the records
        rule, not the booking one.
        """
        capabilities = [
            CASE_TYPE_TO_CAPABILITY.get(c.get("case_type", ""), DEFAULT_CAPABILITY)
            for c in cases
        ] or [DEFAULT_CAPABILITY]
        if "disclose_regulated_data" in capabilities:
            return "disclose_regulated_data"
        if "send_invoice" in capabilities:
            return "send_invoice"
        return capabilities[0]

    async def _dispatch(self, event: dict, draft: str, capability: str):
        exec_context = ExecutionContext(
            business_id=self.context.business_id,
            agent_type=self.agent_type,
            task_id=self.context.task_id,
            action_budget=self.context.action_budget,
            confidence_floor=self.context.confidence_floor.value,
            dry_run=self.context.dry_run,
        )
        channel = (event.get("channel") or "EMAIL").upper()
        if channel == "SMS":
            tool, params = "send_sms", {
                "to_phone": event.get("from_phone", ""),
                "body": draft[:320],
            }
        else:
            tool, params = "send_email", {
                "to_email": event.get("from_email", ""),
                "subject": event.get("subject") or "Re: your message",
                "body_text": draft,
            }

        return await self.executor.run(tool, params, exec_context, capability=capability)

    async def _settle_cases(
        self, case_engine, cases: list[dict], status: ToolResultStatus
    ) -> None:
        """Move each case to reflect what actually happened to the message."""
        if case_engine is None or not cases:
            return

        now = datetime.now(tz=timezone.utc)
        for case_dict in cases:
            case = await case_engine.store.get(uuid.UUID(case_dict["case_id"]))
            if case is None or not case.is_open:
                continue

            if status in (
                ToolResultStatus.EXECUTED,
                ToolResultStatus.CONFIRMED,
                ToolResultStatus.EXECUTED_UNVERIFIED,
            ):
                target, detail = CaseState.WAITING_CUSTOMER, "reply sent"
            elif status is ToolResultStatus.AWAITING_APPROVAL:
                target, detail = CaseState.WAITING_OWNER, "reply queued for approval"
            elif status is ToolResultStatus.SHADOWED:
                # Shadow mode changes nothing in the world, so the case must
                # stay open — marking it handled would fake progress.
                continue
            else:
                target, detail = CaseState.WAITING_OWNER, f"send failed: {status.value}"

            try:
                await case_engine.transition(case, target, now, detail=detail)
            except Exception as exc:
                log.warning(
                    "communication_agent.case_transition_failed",
                    case_id=str(case.case_id),
                    error=str(exc),
                )
