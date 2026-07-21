"""Layer 4: agent context inherits and enforces budget limits."""

import uuid
from ai_bos.agents.context import AgentContext
from ai_bos.memory.confidence import KnowledgeConfidence


def test_child_context_cannot_exceed_parent_budget():
    parent = AgentContext(
        business_id=uuid.uuid4(),
        task_id=uuid.uuid4(),
        agent_type="orchestrator",
        action_budget=100.0,
    )
    child = parent.child_context("communication", action_budget=200.0)
    assert child.action_budget <= parent.action_budget


def test_child_context_inherits_business_id():
    bid = uuid.uuid4()
    parent = AgentContext(
        business_id=bid,
        task_id=uuid.uuid4(),
        agent_type="orchestrator",
        action_budget=50.0,
    )
    child = parent.child_context("scheduling")
    assert child.business_id == bid


def test_child_context_gets_new_task_id():
    parent = AgentContext(
        business_id=uuid.uuid4(),
        task_id=uuid.uuid4(),
        agent_type="orchestrator",
        action_budget=50.0,
    )
    child = parent.child_context("finance")
    assert child.task_id != parent.task_id
    assert child.parent_task_id == parent.task_id
