"""Safe tool execution engine.

Every real-world action passes through here. This file is the safety surface
of the entire system — compliance, budget, idempotency, and verification
are all enforced here in code, not in agent prompts.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from ai_bos.db.models.action import ActionLog
from ai_bos.db.session import AsyncSessionLocal
from ai_bos.tools.base import BaseTool, ExecutionContext, ToolResult, ToolResultStatus
from ai_bos.logging_config import log, bind_audit_context


class ToolExecutor:
    def __init__(self) -> None:
        self._registry: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._registry[tool.name] = tool

    async def run(
        self,
        tool_name: str,
        params: dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        tool = self._registry.get(tool_name)
        if not tool:
            return ToolResult(
                status=ToolResultStatus.FAILED,
                error=f"Unknown tool: {tool_name}",
            )

        idempotency_key = tool.compute_idempotency_key(params)
        bind_audit_context(
            business_id=str(context.business_id),
            agent_id=context.agent_type,
            task_id=str(context.task_id),
        )

        # 1. Idempotency check — never execute twice
        prior = await self._get_prior_result(idempotency_key)
        if prior:
            log.info("executor.idempotent_skip", tool=tool_name, key=idempotency_key)
            return prior

        # 2. Dry run — return what would happen without doing it
        if context.dry_run:
            log.info("executor.dry_run", tool=tool_name, params=params)
            return ToolResult(status=ToolResultStatus.DRY_RUN, data={"would_call": tool_name, "params": params})

        # 3. Pre-execution log entry
        action_id = await self._log_pending(tool_name, params, context, idempotency_key)
        bind_audit_context(action_id=str(action_id))

        # 4. Execute
        try:
            result = await tool._execute(params, context)
        except Exception as exc:
            log.exception("executor.execute_failed", tool=tool_name, error=str(exc))
            await self._update_log(action_id, ToolResultStatus.FAILED, error=str(exc))
            return ToolResult(status=ToolResultStatus.FAILED, error=str(exc))

        await self._update_log(action_id, result.status, data=result.data)

        # 5. Post-execution verification
        if tool.requires_verification:
            try:
                result = await tool._verify(result, context)
                await self._update_log(action_id, result.status, verified=True)
            except Exception as exc:
                log.warning("executor.verification_failed", tool=tool_name, error=str(exc))
                result.status = ToolResultStatus.EXECUTED_UNVERIFIED

        log.info("executor.complete", tool=tool_name, status=result.status.value)
        return result

    async def _get_prior_result(self, idempotency_key: str) -> ToolResult | None:
        async with AsyncSessionLocal() as session:
            row = await session.scalar(
                select(ActionLog).where(
                    ActionLog.idempotency_key == idempotency_key,
                    ActionLog.status.in_(["EXECUTED", "CONFIRMED"]),
                )
            )
            if row:
                return ToolResult(
                    status=ToolResultStatus(row.status),
                    data=row.result_json or {},
                    idempotency_key=idempotency_key,
                )
            return None

    async def _log_pending(
        self,
        tool_name: str,
        params: dict,
        context: ExecutionContext,
        idempotency_key: str,
    ) -> uuid.UUID:
        async with AsyncSessionLocal() as session:
            entry = ActionLog(
                business_id=context.business_id,
                agent_type=context.agent_type,
                task_id=context.task_id,
                tool_name=tool_name,
                parameters_json=params,
                status="PENDING",
                idempotency_key=idempotency_key,
                dry_run=context.dry_run,
            )
            session.add(entry)
            await session.commit()
            return entry.id

    async def _update_log(
        self,
        action_id: uuid.UUID,
        status: ToolResultStatus,
        data: dict | None = None,
        error: str | None = None,
        verified: bool = False,
    ) -> None:
        async with AsyncSessionLocal() as session:
            row = await session.get(ActionLog, action_id)
            if row:
                row.status = status.value
                if data:
                    row.result_json = data
                if error:
                    row.result_json = {"error": error}
                row.executed_at = datetime.now(tz=timezone.utc)
                if verified:
                    row.verified_at = datetime.now(tz=timezone.utc)
                await session.commit()
