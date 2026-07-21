"""Tool registry — discovers, validates, and routes tool calls."""

from __future__ import annotations

from ai_bos.tools.base import BaseTool
from ai_bos.logging_config import log


class ToolRegistry:
    _instance: "ToolRegistry | None" = None

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    @classmethod
    def get(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = ToolRegistry()
        return cls._instance

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool
        log.info("registry.tool_registered", tool=tool.name)

    def get_tool(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def all_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def tool_descriptions_for_llm(self) -> list[dict]:
        """Return tool definitions in Claude's tool_use format."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": {"type": "object", "properties": {}, "required": []},
            }
            for t in self._tools.values()
        ]
