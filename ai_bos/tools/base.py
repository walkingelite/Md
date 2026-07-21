"""BaseTool — every tool the AI can use must implement this contract."""

from __future__ import annotations

import abc
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ToolResultStatus(str, Enum):
    PENDING = "PENDING"
    EXECUTED = "EXECUTED"
    CONFIRMED = "CONFIRMED"           # Verified against external state
    EXECUTED_UNVERIFIED = "EXECUTED_UNVERIFIED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    ROLLED_BACK = "ROLLED_BACK"
    DRY_RUN = "DRY_RUN"


@dataclass
class ToolResult:
    status: ToolResultStatus
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    executed_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    idempotency_key: str = ""


@dataclass
class ExecutionContext:
    business_id: uuid.UUID
    agent_type: str
    task_id: uuid.UUID
    action_budget: float        # Max spend this agent can authorize (USD)
    confidence_floor: str       # Minimum confidence level required
    dry_run: bool = False
    deadline: datetime | None = None


class BaseTool(abc.ABC):
    name: str = ""
    description: str = ""       # Written for LLM consumption
    is_reversible: bool = True
    reversal_tool: str | None = None
    requires_verification: bool = True
    max_retries: int = 3
    idempotency_key_fields: list[str] = []

    @abc.abstractmethod
    async def _execute(self, params: dict[str, Any], context: ExecutionContext) -> ToolResult:
        """Core execution logic — implement in each tool."""
        ...

    async def _verify(self, result: ToolResult, context: ExecutionContext) -> ToolResult:
        """Override in tools that need post-execution verification."""
        result.status = ToolResultStatus.CONFIRMED
        return result

    async def _rollback(self, result: ToolResult, context: ExecutionContext) -> ToolResult:
        """Override in irreversible tools to define compensation actions."""
        return ToolResult(status=ToolResultStatus.ROLLED_BACK)

    def compute_idempotency_key(self, params: dict[str, Any]) -> str:
        fields = self.idempotency_key_fields or list(params.keys())
        parts = [self.name] + [f"{k}={params.get(k)}" for k in sorted(fields)]
        return "|".join(parts)
