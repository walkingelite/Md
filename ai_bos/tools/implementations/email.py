"""Email tool via SendGrid — with delivery verification."""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ai_bos.config import settings
from ai_bos.tools.base import BaseTool, ExecutionContext, ToolResult, ToolResultStatus
from ai_bos.tools.rate_limiter import get_circuit_breaker
from ai_bos.logging_config import log


class SendEmailTool(BaseTool):
    name = "send_email"
    description = (
        "Send an email to a customer or contact. "
        "Provide: to_email, subject, body_text, body_html (optional). "
        "The tool verifies delivery via SendGrid webhooks. "
        "Do NOT use for PHI unless the channel is confirmed HIPAA-compliant. "
        "Irreversible — a correction email is sent as rollback if this was a mistake."
    )
    is_reversible = False
    reversal_tool = "send_correction_email"
    requires_verification = True
    idempotency_key_fields = ["to_email", "subject"]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    async def _execute(self, params: dict[str, Any], context: ExecutionContext) -> ToolResult:
        cb = get_circuit_breaker("sendgrid")
        if not cb.can_proceed():
            return ToolResult(status=ToolResultStatus.FAILED, error="SendGrid circuit open")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={
                        "Authorization": f"Bearer {settings.sendgrid_api_key.get_secret_value()}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "personalizations": [{"to": [{"email": params["to_email"]}]}],
                        "from": {"email": settings.sendgrid_from_email},
                        "subject": params["subject"],
                        "content": [{"type": "text/plain", "value": params["body_text"]}],
                    },
                )
                if resp.status_code in (200, 202):
                    cb.record_success()
                    message_id = resp.headers.get("X-Message-Id", "")
                    log.info("email.sent", to=params["to_email"], message_id=message_id)
                    return ToolResult(
                        status=ToolResultStatus.EXECUTED,
                        data={"message_id": message_id, "to": params["to_email"]},
                    )
                else:
                    cb.record_failure()
                    return ToolResult(
                        status=ToolResultStatus.FAILED,
                        error=f"SendGrid error {resp.status_code}: {resp.text}",
                    )
        except Exception as exc:
            cb.record_failure()
            raise exc

    async def _verify(self, result: ToolResult, context: ExecutionContext) -> ToolResult:
        # Delivery verification happens asynchronously via SendGrid webhooks.
        # Mark as EXECUTED_UNVERIFIED; the webhook handler updates to CONFIRMED.
        result.status = ToolResultStatus.EXECUTED_UNVERIFIED
        return result
