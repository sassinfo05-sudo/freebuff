"""Deterministic Task/PlanItem state machines.

Orchestration logic (agents/orchestrator.py) is the ONLY caller of `transition()`. LLM output is
never allowed to set a state directly — a model can only request/recommend a transition, which is
validated here against ALLOWED_TRANSITIONS before it is applied. This is what "Do not let arbitrary
LLM responses directly manipulate states" means in practice.
"""
from __future__ import annotations

from typing import Dict, Set

from .models import PlanItemStatus, TaskStatus

# --- Task state machine -----------------------------------------------------------------

ALLOWED_TRANSITIONS: Dict[TaskStatus, Set[TaskStatus]] = {
    "CREATED": {"UNDERSTANDING", "CANCELLED", "FAILED"},
    "UNDERSTANDING": {"ANALYZING_REPOSITORY", "BLOCKED", "CANCELLED", "FAILED"},
    "ANALYZING_REPOSITORY": {"PLANNING", "BLOCKED", "CANCELLED", "FAILED"},
    "PLANNING": {"READY", "BLOCKED", "CANCELLED", "FAILED"},
    "READY": {"IMPLEMENTING", "CANCELLED", "FAILED"},
    "IMPLEMENTING": {"TESTING", "DEBUGGING", "BLOCKED", "CANCELLED", "FAILED"},
    "TESTING": {"REVIEWING", "DEBUGGING", "IMPLEMENTING", "BLOCKED", "CANCELLED", "FAILED"},
    "DEBUGGING": {"IMPLEMENTING", "TESTING", "BLOCKED", "CANCELLED", "FAILED"},
    "REVIEWING": {"FINAL_VERIFICATION", "IMPLEMENTING", "BLOCKED", "CANCELLED", "FAILED"},
    "FINAL_VERIFICATION": {"READY_FOR_APPROVAL", "IMPLEMENTING", "BLOCKED", "CANCELLED", "FAILED"},
    "READY_FOR_APPROVAL": {"COMMITTING", "IMPLEMENTING", "CANCELLED", "FAILED"},
    "COMMITTING": {"PUSHING", "BLOCKED", "CANCELLED", "FAILED"},
    "PUSHING": {"COMPLETED", "BLOCKED", "CANCELLED", "FAILED"},
    "COMPLETED": set(),
    # BLOCKED/FAILED/CANCELLED are recoverable — natural-language follow-ups ("Continue.", "Fix
    # it.") resume a task from any of them. Only COMPLETED is truly terminal.
    "BLOCKED": {"UNDERSTANDING", "ANALYZING_REPOSITORY", "PLANNING", "IMPLEMENTING", "CANCELLED", "FAILED"},
    "FAILED": {"UNDERSTANDING", "ANALYZING_REPOSITORY", "PLANNING", "IMPLEMENTING", "CANCELLED"},
    "CANCELLED": {"UNDERSTANDING", "ANALYZING_REPOSITORY", "PLANNING", "IMPLEMENTING"},
}

TERMINAL_STATES: Set[TaskStatus] = {"COMPLETED"}


class InvalidTransition(Exception):
    pass


def can_transition(current: TaskStatus, target: TaskStatus) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, set())


def transition(current: TaskStatus, target: TaskStatus) -> TaskStatus:
    """Validate and return the new state. Raises InvalidTransition if not allowed."""
    if current == target:
        return current
    if not can_transition(current, target):
        raise InvalidTransition(f"Cannot transition task from {current} to {target}")
    return target


def is_terminal(status: TaskStatus) -> bool:
    return status in TERMINAL_STATES


# --- Plan item state machine --------------------------------------------------------------

PLAN_ITEM_TRANSITIONS: Dict[PlanItemStatus, Set[PlanItemStatus]] = {
    "PENDING": {"READY", "BLOCKED", "SKIPPED"},
    "READY": {"RUNNING", "BLOCKED", "SKIPPED"},
    "RUNNING": {"IMPLEMENTED", "FAILED", "BLOCKED"},
    "IMPLEMENTED": {"VERIFYING", "FAILED"},
    "VERIFYING": {"VERIFIED", "FAILED", "IMPLEMENTED"},
    "VERIFIED": set(),
    "BLOCKED": {"READY", "SKIPPED", "FAILED"},
    "FAILED": {"READY", "SKIPPED"},
    "SKIPPED": set(),
}

PLAN_ITEM_TERMINAL: Set[PlanItemStatus] = {"VERIFIED", "SKIPPED"}


def plan_item_transition(current: PlanItemStatus, target: PlanItemStatus) -> PlanItemStatus:
    if current == target:
        return current
    if target not in PLAN_ITEM_TRANSITIONS.get(current, set()):
        raise InvalidTransition(f"Cannot transition plan item from {current} to {target}")
    return target


def requires_evidence(target: PlanItemStatus) -> bool:
    """A plan item cannot become VERIFIED without evidence (test/build reference)."""
    return target == "VERIFIED"
