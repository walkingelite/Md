"""Customer identity resolution — matches incoming contacts to existing records."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import or_, select

from ai_bos.db.models.customer import Customer
from ai_bos.db.session import AsyncSessionLocal
from ai_bos.logging_config import log


class IdentityConfidence(str, Enum):
    CERTAIN = "CERTAIN"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


@dataclass
class IdentityMatch:
    customer_id: uuid.UUID | None
    confidence: IdentityConfidence
    matched_on: list[str]  # e.g. ["email", "phone"]
    is_new: bool = False


class IdentityResolver:
    async def resolve(
        self,
        business_id: uuid.UUID,
        *,
        email: str | None = None,
        phone: str | None = None,
        name: str | None = None,
    ) -> IdentityMatch:
        """Find an existing customer or flag as new."""
        async with AsyncSessionLocal() as session:
            conditions = []
            if email:
                conditions.append(Customer.emails.contains([email]))
            if phone:
                conditions.append(Customer.phones.contains([phone]))

            if not conditions:
                return IdentityMatch(
                    customer_id=None,
                    confidence=IdentityConfidence.UNKNOWN,
                    matched_on=[],
                    is_new=True,
                )

            results = await session.scalars(
                select(Customer).where(
                    Customer.business_id == business_id,
                    Customer.deleted_at.is_(None),
                    or_(*conditions),
                )
            )
            customers = list(results)

            if not customers:
                return IdentityMatch(
                    customer_id=None,
                    confidence=IdentityConfidence.UNKNOWN,
                    matched_on=[],
                    is_new=True,
                )

            if len(customers) == 1:
                c = customers[0]
                matched_on = []
                if email and email in (c.emails or []):
                    matched_on.append("email")
                if phone and phone in (c.phones or []):
                    matched_on.append("phone")

                confidence = IdentityConfidence.HIGH if len(matched_on) >= 2 else IdentityConfidence.MEDIUM
                log.info(
                    "identity.resolved",
                    customer_id=str(c.id),
                    confidence=confidence.value,
                    matched_on=matched_on,
                )
                return IdentityMatch(
                    customer_id=c.id,
                    confidence=confidence,
                    matched_on=matched_on,
                )

            # Multiple matches — ambiguous identity
            log.warning("identity.ambiguous", match_count=len(customers), email=email, phone=phone)
            return IdentityMatch(
                customer_id=None,
                confidence=IdentityConfidence.LOW,
                matched_on=[],
            )
