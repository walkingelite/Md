"""Payments tool via Stripe."""

from __future__ import annotations

from typing import Any

import httpx

from ai_bos.config import settings
from ai_bos.tools.base import BaseTool, ExecutionContext, ToolResult, ToolResultStatus
from ai_bos.tools.rate_limiter import get_circuit_breaker
from ai_bos.logging_config import log


class CreateInvoiceTool(BaseTool):
    name = "create_invoice"
    description = (
        "Create and send an invoice to a customer via Stripe. "
        "Provide: customer_email, amount_cents (integer), currency (e.g. 'usd'), "
        "description, due_date (ISO 8601 optional). "
        "Returns an invoice_id and hosted_invoice_url."
    )
    is_reversible = False
    reversal_tool = "void_invoice"
    requires_verification = True
    idempotency_key_fields = ["customer_email", "amount_cents", "description"]

    async def _execute(self, params: dict[str, Any], context: ExecutionContext) -> ToolResult:
        cb = get_circuit_breaker("stripe")
        if not cb.can_proceed():
            return ToolResult(status=ToolResultStatus.FAILED, error="Stripe circuit open")

        secret_key = settings.stripe_secret_key.get_secret_value()
        try:
            async with httpx.AsyncClient(
                auth=(secret_key, ""), timeout=15.0
            ) as client:
                # 1. Find or create customer
                cust_resp = await client.post(
                    "https://api.stripe.com/v1/customers",
                    data={"email": params["customer_email"]},
                )
                customer_id = cust_resp.json().get("id", "")

                # 2. Create invoice item
                await client.post(
                    "https://api.stripe.com/v1/invoiceitems",
                    data={
                        "customer": customer_id,
                        "amount": params["amount_cents"],
                        "currency": params.get("currency", "usd"),
                        "description": params["description"],
                    },
                )

                # 3. Create and finalize invoice
                inv_resp = await client.post(
                    "https://api.stripe.com/v1/invoices",
                    data={"customer": customer_id, "auto_advance": "true"},
                )
                invoice = inv_resp.json()
                if "id" in invoice:
                    cb.record_success()
                    log.info("invoice.created", invoice_id=invoice["id"], customer=params["customer_email"])
                    return ToolResult(
                        status=ToolResultStatus.EXECUTED,
                        data={
                            "invoice_id": invoice["id"],
                            "hosted_invoice_url": invoice.get("hosted_invoice_url"),
                            "amount_cents": params["amount_cents"],
                        },
                    )
                cb.record_failure()
                return ToolResult(status=ToolResultStatus.FAILED, error=str(invoice))
        except Exception as exc:
            cb.record_failure()
            return ToolResult(status=ToolResultStatus.FAILED, error=str(exc))
