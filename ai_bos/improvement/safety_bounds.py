"""Hard limits on what the self-improvement engine may modify.

These are unconditional constraints — not enforced by prompts
but by code that the improvement engine cannot route around.
"""

from __future__ import annotations

from ai_bos.logging_config import log

# Capabilities that may NEVER be autonomously modified
IMMUTABLE_COMPONENTS = {
    "orchestrator",
    "compliance",
    "safety_bounds",
    "executor_budget_check",
    "escalation_thresholds",
}

# Hard financial limits
MAX_AUTONOMOUS_TRANSACTION_USD = 500.0
MAX_NEW_CAPABILITIES_PER_MONTH = 2


def can_modify_component(component_name: str) -> bool:
    """Returns False if the component is immutable to self-improvement."""
    if component_name in IMMUTABLE_COMPONENTS:
        log.warning("safety_bounds.modification_blocked", component=component_name)
        return False
    return True


def can_create_financial_tool(max_transaction_usd: float) -> bool:
    """Block tools that can process transactions above the hard limit."""
    if max_transaction_usd > MAX_AUTONOMOUS_TRANSACTION_USD:
        log.warning(
            "safety_bounds.financial_tool_blocked",
            max_transaction=max_transaction_usd,
            limit=MAX_AUTONOMOUS_TRANSACTION_USD,
        )
        return False
    return True
