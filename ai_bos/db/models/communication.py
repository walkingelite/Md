"""Communication models — every message ever sent or received."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_bos.db.base import Base, TimestampMixin, UUIDMixin


class MessageThread(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "message_threads"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("business_profiles.id"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True, index=True
    )
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel: Mapped[str] = mapped_column(Text, nullable=False)  # EMAIL | SMS | VOICE
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")

    messages: Mapped[list["Message"]] = relationship(back_populates="thread")


class Message(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "messages"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("business_profiles.id"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True, index=True
    )
    thread_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("message_threads.id"), nullable=True, index=True
    )

    direction: Mapped[str] = mapped_column(Text, nullable=False)  # INBOUND | OUTBOUND
    channel: Mapped[str] = mapped_column(Text, nullable=False)    # EMAIL | SMS | VOICE
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    compliance_checks: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    thread: Mapped["MessageThread"] = relationship(back_populates="messages")
    customer: Mapped["Customer"] = relationship(back_populates="messages")  # type: ignore[name-defined]
