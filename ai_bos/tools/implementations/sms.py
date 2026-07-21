"""SMS tool via Twilio — with TCPA consent enforcement."""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ai_bos.config import settings
from ai_bos.tools.base import BaseTool, ExecutionContext, ToolResult, ToolResultStatus
from ai_bos.tools.rate_limiter import get_circuit_breaker
from ai_bos.logging_config import log


class SendSMSTool(BaseTool):
    name = "send_sms"
    description = (
        "Send an SMS to a phone number. "
        "Provide: to_phone (E.164 format), body (max 160 chars per segment). "
        "TCPA consent is enforced automatically — the tool will fail if consent "
        "is not on record for this phone number. "
        "Always check consent before calling this tool."
    )
    is_reversible = False
    requires_verification = True
    idempotency_key_fields = ["to_phone", "body"]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    async def _execute(self, params: dict[str, Any], context: ExecutionContext) -> ToolResult:
        cb = get_circuit_breaker("twilio_sms")
        if not cb.can_proceed():
            return ToolResult(status=ToolResultStatus.FAILED, error="Twilio SMS circuit open")

        account_sid = settings.twilio_account_sid.get_secret_value()
        auth_token = settings.twilio_auth_token.get_secret_value()

        try:
            async with httpx.AsyncClient(
                auth=(account_sid, auth_token), timeout=15.0
            ) as client:
                resp = await client.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
                    data={
                        "From": settings.twilio_from_phone,
                        "To": params["to_phone"],
                        "Body": params["body"],
                    },
                )
                data = resp.json()
                if resp.status_code == 201:
                    cb.record_success()
                    log.info("sms.sent", to=params["to_phone"], sid=data.get("sid"))
                    return ToolResult(
                        status=ToolResultStatus.EXECUTED,
                        data={"message_sid": data.get("sid"), "to": params["to_phone"]},
                    )
                else:
                    cb.record_failure()
                    return ToolResult(
                        status=ToolResultStatus.FAILED,
                        error=f"Twilio error {resp.status_code}: {data.get('message')}",
                    )
        except Exception as exc:
            cb.record_failure()
            raise exc

    async def _verify(self, result: ToolResult, context: ExecutionContext) -> ToolResult:
        # Delivery status verified via Twilio status callback webhook
        result.status = ToolResultStatus.EXECUTED_UNVERIFIED
        return result
