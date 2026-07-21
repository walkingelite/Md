"""Queue of items that must be confirmed before the system acts on them."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum


class VerificationPriority(str, Enum):
    CRITICAL = "CRITICAL"   # Blocks initial operation
    HIGH = "HIGH"           # Needed within 24h
    MEDIUM = "MEDIUM"       # Needed within 1 week
    LOW = "LOW"             # Nice to have


@dataclass
class VerificationItem:
    item_id: uuid.UUID = field(default_factory=uuid.uuid4)
    business_id: uuid.UUID = field(default_factory=uuid.uuid4)
    description: str = ""
    why_needed: str = ""
    priority: VerificationPriority = VerificationPriority.MEDIUM
    is_resolved: bool = False
    resolved_value: str | None = None


class VerificationQueue:
    def __init__(self, business_id: uuid.UUID) -> None:
        self.business_id = business_id
        self._items: list[VerificationItem] = []

    def add(self, description: str, why_needed: str, priority: VerificationPriority) -> VerificationItem:
        item = VerificationItem(
            business_id=self.business_id,
            description=description,
            why_needed=why_needed,
            priority=priority,
        )
        self._items.append(item)
        return item

    def resolve(self, item_id: uuid.UUID, value: str) -> None:
        for item in self._items:
            if item.item_id == item_id:
                item.is_resolved = True
                item.resolved_value = value
                return

    def pending(self) -> list[VerificationItem]:
        return [i for i in self._items if not i.is_resolved]

    def critical_pending(self) -> list[VerificationItem]:
        return [i for i in self.pending() if i.priority == VerificationPriority.CRITICAL]
