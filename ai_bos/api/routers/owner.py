"""Owner communication endpoints — escalations and intake."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from ai_bos.owner.escalation import OwnerEscalation
from ai_bos.owner.report import generate_digest

router = APIRouter()
escalation = OwnerEscalation()


class EscalationResponseRequest(BaseModel):
    escalation_id: str
    response: str


@router.post("/escalation/respond")
async def respond_to_escalation(req: EscalationResponseRequest) -> dict:
    escalation.resolve(uuid.UUID(req.escalation_id), req.response)
    return {"status": "resolved"}


@router.get("/digest/{business_id}")
async def get_digest(business_id: str) -> dict:
    digest = await generate_digest(uuid.UUID(business_id))
    return {"digest": digest}
