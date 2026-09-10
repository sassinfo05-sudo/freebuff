"""QA agent — deterministic (no LLM needed to run tests). Independent from implementation:
discovers real test/build/lint commands and risk-selects which to run based on changed files."""
from __future__ import annotations

from typing import List

from ..models import TestRun, Workspace
from ..services import command_policy, execution_service, testing_service
from ..services.git_service import GitService


async def run_risk_based_tests(task_id: str, workspace: Workspace) -> List[TestRun]:
    profile = testing_service.discover(workspace.local_path)
    git = GitService()
    changed = await git.changed_files(workspace.local_path, base_ref=workspace.base_commit_sha)
    commands = testing_service.select_commands(profile, changed)
    runs: List[TestRun] = []
    for c in commands:
        decision = command_policy.evaluate(c["command"])
        if not decision.allowed:
            continue  # never silently run something the policy would reject
        run = await execution_service.run_command(workspace.local_path, task_id, c["command"], c["type"])
        runs.append(run)
    return runs


def all_passed(runs: List[TestRun]) -> bool:
    if not runs:
        return False
    return all(r.status == "passed" for r in runs)
