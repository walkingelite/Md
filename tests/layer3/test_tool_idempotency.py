"""Layer 3: tools compute deterministic idempotency keys."""

from ai_bos.tools.base import BaseTool, ExecutionContext, ToolResult, ToolResultStatus
import uuid


class MockTool(BaseTool):
    name = "mock_tool"
    description = "A mock tool for testing"
    idempotency_key_fields = ["to_email", "subject"]

    async def _execute(self, params, context):
        return ToolResult(status=ToolResultStatus.CONFIRMED)


def test_idempotency_key_is_deterministic():
    tool = MockTool()
    params = {"to_email": "a@b.com", "subject": "Hello", "extra": "ignored"}
    key1 = tool.compute_idempotency_key(params)
    key2 = tool.compute_idempotency_key(params)
    assert key1 == key2


def test_idempotency_key_differs_for_different_params():
    tool = MockTool()
    key1 = tool.compute_idempotency_key({"to_email": "a@b.com", "subject": "Hello"})
    key2 = tool.compute_idempotency_key({"to_email": "b@c.com", "subject": "Hello"})
    assert key1 != key2
