"""QA agent — deterministic (no LLM needed to run tests). Independent from implementation:
discovers real test/build/lint commands and risk-selects which to run based on changed files.

A freshly cloned workspace (see WorkspaceManager) never has dependencies installed — `node_modules`
doesn't exist, .git excludes it. Without an install step, every frontend command would fail on a
missing/wrong-version toolchain (this was caught by running the real thing against a real clone,
not assumed) rather than on anything the implementer actually did. There's no equivalent auto-step
for the backend: `pip install`-ing an arbitrary repo's requirements into the process that's running
Dev Studio itself would be invasive; that's a known, documented limitation, not silently patched
over."""
from __future__ import annotations

import os
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

    if profile.has_frontend and any(c["type"] in ("frontend_unit", "build", "lint") for c in commands):
        fe_dir = profile.frontend_dir or ""
        node_modules = os.path.join(workspace.local_path, fe_dir, "node_modules")
        if not os.path.isdir(node_modules):
            install_run = await execution_service.run_command(
                workspace.local_path, task_id, "npm install", "setup",
                cwd_subdir=profile.frontend_dir, timeout=600)
            runs.append(install_run)

    for c in commands:
        decision = command_policy.evaluate(c["command"])
        if not decision.allowed:
            continue  # never silently run something the policy would reject
        run = await execution_service.run_command(workspace.local_path, task_id, c["command"], c["type"],
                                                    cwd_subdir=c.get("cwd"))
        runs.append(run)
    return runs


def all_passed(runs: List[TestRun]) -> bool:
    real_runs = [r for r in runs if r.test_type != "setup"]
    if not real_runs:
        return False
    return all(r.status == "passed" for r in real_runs)
