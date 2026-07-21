"""BaseAgent — all specialist agents extend this."""

from __future__ import annotations

import abc
import uuid
from typing import Any

import anthropic

from ai_bos.agents.context import AgentContext
from ai_bos.config import settings
from ai_bos.memory.store import MemoryStore, MemoryQuery
from ai_bos.tools.executor import ToolExecutor
from ai_bos.tools.registry import ToolRegistry
from ai_bos.logging_config import log


class BaseAgent(abc.ABC):
    """
    An agent has: context (authority), memory (knowledge), tools (actions).
    It uses claude-haiku-4-5 by default; complex tasks escalate to claude-sonnet-4-6.
    """

    agent_type: str = "base"
    default_model: str = "claude-haiku-4-5-20251001"
    reasoning_model: str = "claude-sonnet-4-6"

    def __init__(
        self,
        context: AgentContext,
        memory: MemoryStore,
        executor: ToolExecutor,
    ) -> None:
        self.context = context
        self.memory = memory
        self.executor = executor
        self._client = anthropic.Anthropic(api_key=settings.anthropic_key)
        self._step_count = 0

    @abc.abstractmethod
    async def run(self, task: dict[str, Any]) -> dict[str, Any]:
        """Execute the task and return the result."""
        ...

    async def _query_memory(self, query: str, domain: str | None = None) -> list[dict]:
        """Retrieve business knowledge relevant to this task."""
        results = await self.memory.retrieve(
            MemoryQuery(
                business_id=self.context.business_id,
                domain=domain,
                semantic_query=query,
                limit=10,
            )
        )
        return [
            {
                "content": r.content,
                "confidence": r.confidence.value,
                "staleness_warning": r.staleness_warning,
                "domain": r.domain,
                "key": r.key,
            }
            for r in results
        ]

    def _build_system_prompt(self, role_description: str, memory_context: list[dict]) -> str:
        mem_text = "\n".join(
            f"[{m['confidence']}] {m['domain']}/{m['key']}: {m['content']}"
            + (" ⚠️ STALE" if m["staleness_warning"] else "")
            for m in memory_context
        )
        return f"""You are the {self.agent_type} agent for an AI Business Operating System.
You autonomously run a real business. You are not an assistant — you are the operator.

Business context from memory:
{mem_text or "(no relevant context retrieved)"}

Rules you must follow:
- Facts marked ASSUMED must not be acted on without verification.
- Facts marked INFERRED should be stated as likely, not certain.
- STALE facts should be used with caution and flagged for refresh.
- Stay within your action budget.
- Log your reasoning before taking any irreversible action.

{role_description}"""

    def _increment_step(self) -> None:
        self._step_count += 1
        if self._step_count % 20 == 0:
            log.info("agent.step_milestone", agent=self.agent_type, steps=self._step_count)
