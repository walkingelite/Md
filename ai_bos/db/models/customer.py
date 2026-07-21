"""Customer identity and interaction models."""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_bos.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class Customer(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "customers"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("business_profiles.id"), nullable=False, index=True
    )
    emails: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    phones: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    names: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    identity_confidence: Mapped[str] = mapped_column(
        Text, nullable=False, default="LOW"
    )  # LOW | MEDIUM | HIGH | CERTAIN
    consent_records: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    business: Mapped["BusinessProfile"] = relationship(back_populates="customers")  # type: ignore[name-defined]
    messages: Mapped[list["Message"]] = relationship(back_populates="customer")  # type: ignore[name-defined]
