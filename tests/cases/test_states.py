"""Transition validation — the guard against silent state corruption."""

import pytest

from ai_bos.cases.states import (
    ACTIVE_STATES,
    TERMINAL_STATES,
    WAITING_STATES,
    CaseState,
    InvalidTransition,
    allowed_targets,
    can_transition,
)


def test_open_can_reach_every_waiting_state():
    for target in WAITING_STATES:
        assert can_transition(CaseState.OPEN, target)


def test_cannot_transition_to_self():
    for state in CaseState:
        assert not can_transition(state, state)


def test_waiting_states_cannot_jump_to_each_other():
    """A case awaiting an insurer is not awaiting the customer. Conflating
    them loses track of who owes the next move."""
    assert not can_transition(CaseState.WAITING_EXTERNAL, CaseState.WAITING_CUSTOMER)
    assert not can_transition(CaseState.WAITING_CUSTOMER, CaseState.WAITING_EXTERNAL)


def test_blocked_cannot_resolve_directly():
    """Resolving straight out of BLOCKED would mean closing work while the
    fact that blocked it is still missing."""
    assert not can_transition(CaseState.BLOCKED, CaseState.RESOLVED)


def test_terminal_states_can_only_reopen():
    for state in TERMINAL_STATES:
        assert allowed_targets(state) == frozenset({CaseState.OPEN})


def test_resolved_can_reopen():
    assert can_transition(CaseState.RESOLVED, CaseState.OPEN)


def test_every_state_has_a_transition_table_entry():
    for state in CaseState:
        assert allowed_targets(state) is not None


def test_active_states_exclude_terminal():
    assert not (ACTIVE_STATES & TERMINAL_STATES)
    assert CaseState.OPEN in ACTIVE_STATES


def test_invalid_transition_message_lists_options():
    exc = InvalidTransition(CaseState.BLOCKED, CaseState.RESOLVED)
    assert "BLOCKED" in str(exc)
    assert "RESOLVED" in str(exc)
    assert "OPEN" in str(exc)
