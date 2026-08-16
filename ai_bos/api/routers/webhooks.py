"""Provider webhooks — the other half of delivery verification.

Sends are recorded as EXECUTED_UNVERIFIED because dispatch is not delivery.
These endpoints are what promote them to CONFIRMED, or mark them failed.
Without them the system would quietly believe every message arrived.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import select, update

from ai_bos.config import settings
from ai_bos.db.models.action import ActionLog
from ai_bos.db.session import AsyncSessionLocal
from ai_bos.logging_config import log

router = APIRouter()

# SendGrid event names that mean the message reached the recipient.
SENDGRID_DELIVERED = {"delivered"}
SENDGRID_FAILED = {"bounce", "dropped", "blocked", "spamreport"}

# Twilio message statuses.
TWILIO_DELIVERED = {"delivered"}
TWILIO_FAILED = {"failed", "undelivered"}


async def _promote(provider_message_id: str, delivered: bool, provider: str) -> bool:
    """Move the matching action from EXECUTED_UNVERIFIED to a settled status."""
    if not provider_message_id:
        return False

    async with AsyncSessionLocal() as session:
        rows = await session.scalars(
            select(ActionLog).where(
                ActionLog.status.in_(["EXECUTED", "EXECUTED_UNVERIFIED"])
            )
        )
        for row in rows:
            result = row.result_json or {}
            if provider_message_id in (
                result.get("message_id"),
                result.get("message_sid"),
            ):
                row.status = "CONFIRMED" if delivered else "FAILED"
                await session.commit()
                log.info(
                    "webhook.action_settled",
                    provider=provider,
                    action_id=str(row.id),
                    status=row.status,
                )
                return True

    log.warning(
        "webhook.no_matching_action", provider=provider, message_id=provider_message_id
    )
    return False


@router.post("/sendgrid")
async def sendgrid_events(request: Request) -> dict[str, Any]:
    """SendGrid posts a batch of events."""
    events = await request.json()
    if not isinstance(events, list):
        raise HTTPException(status_code=400, detail="expected a list of events")

    settled = 0
    for event in events:
        name = str(event.get("event", "")).lower()
        message_id = event.get("sg_message_id", "").split(".")[0]
        if name in SENDGRID_DELIVERED:
            settled += await _promote(message_id, True, "sendgrid")
        elif name in SENDGRID_FAILED:
            settled += await _promote(message_id, False, "sendgrid")

    return {"received": len(events), "settled": settled}


@router.post("/twilio")
async def twilio_status(request: Request) -> dict[str, Any]:
    """Twilio posts a form-encoded status callback per message."""
    form = await request.form()
    status = str(form.get("MessageStatus", "")).lower()
    sid = str(form.get("MessageSid", ""))

    if status in TWILIO_DELIVERED:
        settled = await _promote(sid, True, "twilio")
    elif status in TWILIO_FAILED:
        settled = await _promote(sid, False, "twilio")
    else:
        # Intermediate statuses (queued, sending) are not outcomes.
        return {"status": status, "settled": False}

    return {"status": status, "settled": bool(settled)}


@router.post("/stripe")
async def stripe_events(
    request: Request, stripe_signature: str = Header(default="")
) -> dict[str, Any]:
    """Stripe webhook with signature verification.

    An unsigned payment webhook is an open invitation to mark invoices paid,
    so verification is mandatory rather than best-effort.
    """
    payload = await request.body()
    secret = settings.stripe_webhook_secret.get_secret_value()

    if not _stripe_signature_valid(payload, stripe_signature, secret):
        log.warning("webhook.stripe_bad_signature")
        raise HTTPException(status_code=400, detail="invalid signature")

    import json

    event = json.loads(payload)
    log.info("webhook.stripe_event", event_type=event.get("type"))
    return {"received": True, "type": event.get("type")}


def _stripe_signature_valid(payload: bytes, header: str, secret: str) -> bool:
    if not header or not secret:
        return False
    parts = dict(
        piece.split("=", 1) for piece in header.split(",") if "=" in piece
    )
    timestamp, signature = parts.get("t"), parts.get("v1")
    if not timestamp or not signature:
        return False

    signed = f"{timestamp}.".encode() + payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
