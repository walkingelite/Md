"""AgentContext — scopes every agent's authority.

The budget and confidence_floor in context are enforced by the executor,
not by prompts. Agents cannot reason their way past these limits.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from ai_bos.memory.confidence import KnowledgeConfidence


@dataclass
class AgentContext:
    business_id: uuid.UUID
    task_id: uuid.UUID
    agent_type: str
    parent_task_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    active_thread_id: uuid.UUID | None = None
    action_budget: float = 0.0         # Max USD this agent can spend
    confidence_floor: KnowledgeConfidence = KnowledgeConfidence.INFERRED
    dry_run: bool = False
    started_at: datetime | None = None
    deadline: datetime | None = None

    def child_context(
        self,
        agent_type: str,
        action_budget: float | None = None,
    ) -> "AgentContext":
        """Create a child context with a subset of this context's authority."""
        return AgentContext(
            business_id=self.business_id,
            task_id=uuid.uuid4(),
            agent_type=agent_type,
            parent_task_id=self.task_id,
            customer_id=self.customer_id,
            action_budget=min(action_budget or 0.0, self.action_budget),
            confidence_floor=self.confidence_floor,
            dry_run=self.dry_run,
            deadline=self.deadline,
        )
