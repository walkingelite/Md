"""The trust gate is enforced inside the executor, not by the agent."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from ai_bos.tools.base import BaseTool, ExecutionContext, ToolResult, ToolResultStatus
from ai_bos.tools.executor import ToolExecutor
from ai_bos.trust.gate import TrustGate
from ai_bos.trust.ledger import ApprovalRecord, TrustLedger


class SpyTool(BaseTool):
    name = "spy_tool"
    description = "records whether it actually ran"
    requires_verification = False
    idempotency_key_fields = ["marker"]

    def __init__(self) -> None:
        self.ran = False

    async def _execute(self, params, context):
        self.ran = True
        return ToolResult(status=ToolResultStatus.EXECUTED, data={"ok": True})


def _context() -> ExecutionContext:
    return ExecutionContext(
        business_id=uuid.uuid4(),
        agent_type="communication",
        task_id=uuid.uuid4(),
        action_budget=10.0,
        confidence_floor="INFERRED",
    )


def _executor(ledger: TrustLedger) -> tuple[ToolExecutor, SpyTool]:
    tool = SpyTool()
    ex = ToolExecutor(trust_gate=TrustGate(ledger))
    ex.register(tool)
    return ex, tool


@pytest.fixture(autouse=True)
def _no_db():
    """These tests exercise gate logic, not persistence."""
    with patch("ai_bos.tools.executor.ToolExecutor._get_prior_result", AsyncMock(return_value=None)), \
         patch("ai_bos.tools.executor.ToolExecutor._log_pending", AsyncMock(return_value=uuid.uuid4())), \
         patch("ai_bos.tools.executor.ToolExecutor._update_log", AsyncMock()), \
         patch("ai_bos.tools.executor.ToolExecutor._log_gated", AsyncMock()):
        yield


async def test_shadow_capability_never_executes_the_tool():
    ledger = TrustLedger(business_id=uuid.uuid4())
    ex, tool = _executor(ledger)

    result = await ex.run(
        "spy_tool", {"marker": "a"}, _context(), capability="appointment_reminder"
    )
    assert result.status is ToolResultStatus.SHADOWED
    assert tool.ran is False


async def test_draft_capability_queues_instead_of_running():
    ledger = TrustLedger(business_id=uuid.uuid4())
    for _ in range(20):
        ledger.record(ApprovalRecord(capability="appointment_reminder", approved=True))
    ex, tool = _executor(ledger)

    result = await ex.run(
        "spy_tool", {"marker": "b"}, _context(), capability="appointment_reminder"
    )
    assert result.status is ToolResultStatus.AWAITING_APPROVAL
    assert tool.ran is False


async def test_fully_trusted_capability_executes():
    ledger = TrustLedger(business_id=uuid.uuid4())
    for _ in range(20 + 50 + 100):
        ledger.record(ApprovalRecord(capability="appointment_confirmation", approved=True))
    ex, tool = _executor(ledger)

    result = await ex.run(
        "spy_tool", {"marker": "c"}, _context(), capability="appointment_confirmation"
    )
    assert result.status is ToolResultStatus.EXECUTED
    assert tool.ran is True


async def test_regulated_capability_cannot_be_unlocked_by_volume():
    ledger = TrustLedger(business_id=uuid.uuid4())
    for _ in range(5000):
        ledger.record(ApprovalRecord(capability="disclose_regulated_data", approved=True))
    ex, tool = _executor(ledger)

    result = await ex.run(
        "spy_tool", {"marker": "d"}, _context(), capability="disclose_regulated_data"
    )
    assert result.status is ToolResultStatus.SHADOWED
    assert tool.ran is False


async def test_no_capability_means_no_gating():
    """Tools invoked without a declared capability bypass the ramp; the gate
    governs customer-facing capabilities, not internal calls."""
    ledger = TrustLedger(business_id=uuid.uuid4())
    ex, tool = _executor(ledger)
    result = await ex.run("spy_tool", {"marker": "e"}, _context())
    assert result.status is ToolResultStatus.EXECUTED
    assert tool.ran is True


async def test_executor_without_a_gate_still_runs():
    tool = SpyTool()
    ex = ToolExecutor()
    ex.register(tool)
    result = await ex.run(
        "spy_tool", {"marker": "f"}, _context(), capability="appointment_reminder"
    )
    assert result.status is ToolResultStatus.EXECUTED


async def test_shadowed_result_reports_what_would_have_happened():
    ledger = TrustLedger(business_id=uuid.uuid4())
    ex, _ = _executor(ledger)
    result = await ex.run(
        "spy_tool", {"marker": "g"}, _context(), capability="appointment_reminder"
    )
    assert result.data["would_call"] == "spy_tool"
    assert result.data["params"] == {"marker": "g"}
    assert result.data["stage"] == "SHADOW"
