"""Deterministic tests for Dev Studio's TaskStateMachine / PlanItem state machine.
No DB/network — pure logic (app.devstudio.state_machine)."""
import pytest

from app.devstudio import state_machine as sm


def test_created_can_only_advance_to_understanding_or_terminate():
    assert sm.can_transition("CREATED", "UNDERSTANDING")
    assert sm.can_transition("CREATED", "CANCELLED")
    assert sm.can_transition("CREATED", "FAILED")
    assert not sm.can_transition("CREATED", "PLANNING")
    assert not sm.can_transition("CREATED", "COMPLETED")


def test_happy_path_full_walk():
    path = ["CREATED", "UNDERSTANDING", "ANALYZING_REPOSITORY", "PLANNING", "READY",
            "IMPLEMENTING", "TESTING", "REVIEWING", "FINAL_VERIFICATION",
            "READY_FOR_APPROVAL", "COMMITTING", "PUSHING", "COMPLETED"]
    current = path[0]
    for target in path[1:]:
        current = sm.transition(current, target)
        assert current == target


def test_cannot_skip_states():
    with pytest.raises(sm.InvalidTransition):
        sm.transition("CREATED", "IMPLEMENTING")
    with pytest.raises(sm.InvalidTransition):
        sm.transition("PLANNING", "COMPLETED")


def test_llm_cannot_force_completed_from_arbitrary_state():
    # This is the concrete regression this state machine exists to prevent: a model claiming
    # "done" from mid-flight states must never be accepted.
    for state in ("CREATED", "UNDERSTANDING", "ANALYZING_REPOSITORY", "PLANNING", "IMPLEMENTING",
                  "TESTING", "DEBUGGING", "REVIEWING"):
        assert not sm.can_transition(state, "COMPLETED"), f"{state} -> COMPLETED must be blocked"


def test_completed_is_terminal_but_blocked_failed_cancelled_are_recoverable():
    assert sm.is_terminal("COMPLETED")
    assert not sm.is_terminal("BLOCKED")
    assert not sm.is_terminal("FAILED")
    assert not sm.is_terminal("CANCELLED")
    # "Continue." / "Fix it." follow-ups must be able to resume a blocked/failed/cancelled task.
    assert sm.can_transition("BLOCKED", "IMPLEMENTING")
    assert sm.can_transition("FAILED", "IMPLEMENTING")
    assert sm.can_transition("CANCELLED", "IMPLEMENTING")


def test_same_state_transition_is_a_noop_not_an_error():
    assert sm.transition("IMPLEMENTING", "IMPLEMENTING") == "IMPLEMENTING"


def test_plan_item_requires_evidence_only_for_verified():
    assert sm.requires_evidence("VERIFIED")
    assert not sm.requires_evidence("IMPLEMENTED")
    assert not sm.requires_evidence("VERIFYING")


def test_plan_item_transition_rules():
    assert sm.plan_item_transition("PENDING", "READY") == "READY"
    assert sm.plan_item_transition("RUNNING", "IMPLEMENTED") == "IMPLEMENTED"
    with pytest.raises(sm.InvalidTransition):
        sm.plan_item_transition("PENDING", "VERIFIED")
    with pytest.raises(sm.InvalidTransition):
        sm.plan_item_transition("VERIFIED", "PENDING")  # VERIFIED has no outgoing transitions
