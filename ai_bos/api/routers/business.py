"""Business onboarding and management endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai_bos.business.intake import BusinessIntake
from ai_bos.business.domain_extractor import extract_domain
from ai_bos.db.models.business import BusinessProfile
from ai_bos.db.session import AsyncSessionLocal
from ai_bos.logging_config import log

router = APIRouter()
intake = BusinessIntake()


class DescribeBusinessRequest(BaseModel):
    description: str
    owner_email: str


class DescribeBusinessResponse(BaseModel):
    business_id: str
    status: str
    domain_extracted: dict


@router.post("/describe", response_model=DescribeBusinessResponse)
async def describe_business(req: DescribeBusinessRequest) -> DescribeBusinessResponse:
    """
    Owner describes their business in plain text.
    The system immediately starts building and running.
    """
    business_id = uuid.uuid4()

    # Extract domain model from description
    domain = extract_domain(req.description)

    # Persist business profile
    async with AsyncSessionLocal() as session:
        profile = BusinessProfile(
            id=business_id,
            name=domain.business_type,
            description_raw=req.description,
            domain_json=domain.raw_extraction,
            status="onboarding",
        )
        session.add(profile)
        await session.commit()

    log.info("api.business_created", business_id=str(business_id), type=domain.business_type)

    return DescribeBusinessResponse(
        business_id=str(business_id),
        status="onboarding",
        domain_extracted={
            "business_type": domain.business_type,
            "industry_vertical": domain.industry_vertical,
            "regulatory_domains": domain.regulatory_domains,
            "verification_queue": domain.verification_queue,
        },
    )
