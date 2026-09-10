"""AgentOrchestrator (Supervisor). Deterministic control flow drives the TaskStateMachine; LLM
role-agents only ever PROPOSE (analysis, plan, file edits, verdicts) — every state transition and
every file write happens in plain Python here, never as a side effect of parsing model output.

Only this module calls task_manager.set_status to move a task toward COMPLETED, and only after the
completion gate (verified plan items + passing tests + review approval) is satisfied — see
`_finalize_verification`. Committing/pushing to GitHub is never automatic: the founder triggers it
explicitly via the commit/push API once a task reaches READY_FOR_APPROVAL.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from ..models import AgentConfiguration, Project, Task, Workspace
from ..providers.registry import ModelRegistry
from ..services import (activity_service, anti_loop, execution_service, indexer, memory_service,
                          repository_service, settings_service, task_manager, workspace_manager)
from ..services.file_service import FileService, PathEscapeError, StalePatchError
from . import git_agent, qa_agent, registry as agent_registry, roles
from .runner import AgentStepFailed

logger = logging.getLogger("zanelvo.devstudio")


async def _block(task_id: str, reason: str) -> None:
    await task_manager.update_task(task_id, blocked_reason=reason)
    await task_manager.set_status(task_id, "BLOCKED", note=reason)
    await task_manager.add_message(task_id, "supervisor", f"Blocked: {reason}")


async def _cancel(task_id: str) -> None:
    await task_manager.set_status(task_id, "CANCELLED", note="stop requested")
    await task_manager.clear_stop(task_id)
    await task_manager.add_message(task_id, "supervisor", "Stopped. Workspace preserved — send another "
                                     "message (e.g. 'Continue.') to resume.")


async def run_task(task_id: str) -> None:
    task = await task_manager.get_task(task_id)
    if task is None:
        return
    project = await repository_service.get_project(task.project_id)
    if project is None:
        await _block(task_id, "Project no longer exists")
        return
    registry = await settings_service.build_model_registry()
    configs = await agent_registry.list_configs()
    loop_detector = anti_loop.LoopDetector()

    async def stopped() -> bool:
        return await task_manager.is_stop_requested(task_id)

    try:
        if task.status == "CREATED":
            await activity_service.emit(task_id, "supervisor_note", {"note": "Understanding request"})
            task = await task_manager.set_status(task_id, "UNDERSTANDING")

        if task.status in ("UNDERSTANDING", "CANCELLED", "FAILED"):
            workspace = await workspace_manager.get_workspace_for_task(task_id)
            if workspace is None:
                await activity_service.emit(task_id, "supervisor_note", {"note": "Provisioning workspace"})
                workspace = await workspace_manager.provision_task_workspace(
                    project, task.branch, task_id, task.title)
                await task_manager.update_task(task_id, workspace_id=workspace.id,
                                                 base_commit_sha=workspace.base_commit_sha)
            task = await task_manager.set_status(task_id, "ANALYZING_REPOSITORY")
        if await stopped():
            return await _cancel(task_id)

        analysis: Optional[dict] = None
        if task.status == "ANALYZING_REPOSITORY":
            snapshot = await indexer.get_snapshot(project.id, task.branch)
            if snapshot is None or not snapshot.indexed:
                await activity_service.emit(task_id, "supervisor_note", {"note": "Indexing repository"})
                await indexer.index_project_branch(project, task.branch)
            try:
                analysis = await roles.analyze_repository(task, project.id, task.branch, registry,
                                                             configs["repository_analyst"])
            except AgentStepFailed as e:
                return await _block(task_id, str(e))
            await memory_service.add_memory(
                project.id, "OUTSTANDING_WORK", f"Analysis for: {task.title}",
                str(analysis.get("summary", analysis))[:2000], branch=task.branch,
                source_task_id=task_id, confidence="medium")
            task = await task_manager.set_status(task_id, "PLANNING")
        if await stopped():
            return await _cancel(task_id)

        if task.status == "PLANNING":
            if analysis is None:
                try:
                    analysis = await roles.analyze_repository(task, project.id, task.branch, registry,
                                                                 configs["repository_analyst"])
                except AgentStepFailed as e:
                    return await _block(task_id, str(e))
            try:
                items = await roles.create_plan(task, analysis, project.id, registry, configs["planner"])
            except AgentStepFailed as e:
                return await _block(task_id, str(e))
            await task_manager.set_plan(task_id, items)
            task = await task_manager.set_status(task_id, "READY")
        if await stopped():
            return await _cancel(task_id)

        if task.status == "READY":
            task = await task_manager.set_status(task_id, "IMPLEMENTING")

        workspace = await workspace_manager.get_workspace_for_task(task_id)
        if workspace is None:
            return await _block(task_id, "Workspace missing — cannot implement")

        if task.status == "IMPLEMENTING":
            completed_ok = await _implement_loop(task, project, workspace, registry, configs, loop_detector)
            if not completed_ok:
                return  # _implement_loop already set BLOCKED/left state for retry
            task = await task_manager.get_task(task_id)
        if await stopped():
            return await _cancel(task_id)

        if task.status == "IMPLEMENTING":
            task = await task_manager.set_status(task_id, "TESTING")
        if task.status == "TESTING":
            runs = await qa_agent.run_risk_based_tests(task_id, workspace)
            if runs and not qa_agent.all_passed(runs):
                failing = next((r for r in runs if r.status != "passed"), runs[0])
                signal = await anti_loop.record_failure(
                    task_id, (failing.stdout_tail or "") + (failing.stderr_tail or ""),
                    command=failing.command, subsystem="tests")
                await task_manager.add_message(task_id, "supervisor",
                                                 f"Tests failed ({failing.command}). {signal.reason}")
                if signal.should_block:
                    return await _block(task_id, "Same test failure repeated — needs a strategy change")
                task = await task_manager.set_status(task_id, "DEBUGGING")
                task = await task_manager.set_status(task_id, "IMPLEMENTING")
                await task_manager.update_task(task_id, iterations_used=task.iterations_used + 1)
                return
            if runs:
                await _verify_implemented_items(task_id, runs)
            task = await task_manager.set_status(task_id, "REVIEWING")
        if await stopped():
            return await _cancel(task_id)

        if task.status == "REVIEWING":
            diff = await git_agent.diff_against_base(workspace)
            test_runs = await execution_service.get_test_runs(task_id)
            test_evidence = [{"type": r.test_type, "command": r.command, "status": r.status}
                               for r in test_runs]
            failures = await anti_loop.failure_history(task_id)
            try:
                verdict = await roles.review_diff(task, diff, test_evidence, failures, registry,
                                                    configs["reviewer"])
            except AgentStepFailed as e:
                return await _block(task_id, str(e))
            await task_manager.update_task(task_id, review_verdict=verdict.get("verdict"),
                                             current_diff_summary=diff)
            await task_manager.add_message(task_id, "supervisor",
                                             f"Review verdict: {verdict.get('verdict')} — "
                                             f"{verdict.get('reasoning', '')[:300]}")
            if verdict.get("verdict") == "REJECTED":
                task = await task_manager.set_status(task_id, "IMPLEMENTING")
                return
            task = await task_manager.set_status(task_id, "FINAL_VERIFICATION")

        if task.status == "FINAL_VERIFICATION":
            await _finalize_verification(task_id)
            task = await task_manager.set_status(task_id, "READY_FOR_APPROVAL")
            await task_manager.add_message(
                task_id, "supervisor",
                "Ready for your approval. Review the diff and tests, then POST "
                "/api/devstudio/tasks/{id}/commit and /push when you're satisfied.")
    except Exception as e:  # noqa: BLE001 — orchestrator must never crash silently; always BLOCKED
        logger.exception("Dev Studio orchestrator error on task %s", task_id)
        await _block(task_id, f"Unexpected orchestrator error: {type(e).__name__}: {e}")


async def _verify_implemented_items(task_id: str, passing_test_runs) -> None:
    """A plan item cannot become VERIFIED without evidence — here that evidence is the passing
    TestRun(s) that covered this implementation pass."""
    evidence = {"kind": "test_runs", "test_run_ids": [r.id for r in passing_test_runs],
                 "commands": [r.command for r in passing_test_runs]}
    for item in await task_manager.list_plan_items(task_id):
        if item.status == "IMPLEMENTED":
            await task_manager.set_plan_item_status(item.id, "VERIFYING")
            await task_manager.set_plan_item_status(item.id, "VERIFIED", evidence=evidence)


async def _finalize_verification(task_id: str) -> None:
    all_verified = await task_manager.all_required_items_verified(task_id)
    test_runs = await execution_service.get_test_runs(task_id)
    tests_ok = qa_agent.all_passed(test_runs) if test_runs else False
    if all_verified and tests_ok:
        await task_manager.update_task(task_id, verification_status="verified")
    elif tests_ok:
        await task_manager.update_task(task_id, verification_status="partial")
    else:
        await task_manager.update_task(task_id, verification_status="limited")


async def _implement_loop(task: Task, project: Project, workspace: Workspace, registry: ModelRegistry,
                           configs: Dict[str, AgentConfiguration], loop_detector: anti_loop.LoopDetector) -> bool:
    """Implements plan items in dependency order. Returns True if the loop reached a stopping
    point cleanly (all runnable items attempted); False if it already transitioned the task to a
    state the caller should not continue from (BLOCKED, or returned for the founder to retry)."""
    fs = FileService(workspace.local_path)
    items = await task_manager.list_plan_items(task.id)
    by_title = {i.title: i for i in items}
    id_index = {i.id: i for i in items}

    for item in items:
        if await task_manager.is_stop_requested(task.id):
            await _cancel(task.id)
            return False
        if item.status in ("VERIFIED", "SKIPPED", "IMPLEMENTED", "VERIFYING"):
            continue
        deps = [id_index.get(d) or by_title.get(d) for d in item.depends_on]
        if any(d and d.status not in ("VERIFIED", "IMPLEMENTED", "SKIPPED") for d in deps):
            continue  # dependency not ready yet; leave PENDING

        task = await task_manager.get_task(task.id)
        if anti_loop.budget_exhausted(task.iterations_used, task.iteration_budget):
            await _block(task.id, f"Orchestration budget exhausted ({task.iteration_budget} iterations)")
            return False

        await task_manager.set_plan_item_status(item.id, "READY")
        await task_manager.set_plan_item_status(item.id, "RUNNING")
        config = configs.get(item.assigned_agent, configs["backend"])

        file_contents: Dict[str, str] = {}
        expected_hashes: Dict[str, Optional[str]] = {}
        for path in item.relevant_files[:12]:
            try:
                file_contents[path] = fs.read_file(path)
                expected_hashes[path] = fs.read_hash(path)
            except (FileNotFoundError, PathEscapeError, ValueError):
                continue

        try:
            plan_result = await roles.implement_plan_item(task, item, project.id, task.branch,
                                                             file_contents, registry, config)
        except AgentStepFailed as e:
            await task_manager.set_plan_item_status(item.id, "FAILED")
            signal = await anti_loop.record_failure(task.id, str(e), command="implement", subsystem=item.assigned_agent)
            await task_manager.add_message(task.id, "supervisor", f"{item.title}: implementation failed — {e}")
            if signal.should_block:
                await _block(task.id, f"Repeated implementation failure on '{item.title}': {e}")
                return False
            continue

        ops = plan_result.get("file_operations", []) if isinstance(plan_result, dict) else []
        diff_before = await git_agent.diff_against_base(workspace)
        try:
            _apply_file_operations(fs, ops, expected_hashes)
        except (StalePatchError, PathEscapeError, ValueError, FileNotFoundError, FileExistsError) as e:
            await task_manager.set_plan_item_status(item.id, "FAILED")
            signal = await anti_loop.record_failure(task.id, str(e), command="apply_patch", subsystem=item.assigned_agent)
            await task_manager.add_message(task.id, "supervisor", f"{item.title}: could not apply changes — {e}")
            if signal.should_block:
                await _block(task.id, f"Repeated patch failure on '{item.title}': {e}")
                return False
            continue

        diff_after = await git_agent.diff_against_base(workspace)
        no_progress = loop_detector.record_diff(str(diff_after))
        if no_progress and diff_before == diff_after:
            await task_manager.add_message(task.id, "supervisor",
                                             f"{item.title}: no diff change after implementation attempt")

        await task_manager.set_plan_item_status(item.id, "IMPLEMENTED",
                                                   evidence={"kind": "file_operations", "count": len(ops)})
        await task_manager.update_task(task.id, iterations_used=task.iterations_used + 1,
                                         current_diff_summary=diff_after)

    return True


def _apply_file_operations(fs: FileService, ops: List[dict], expected_hashes: Dict[str, Optional[str]]) -> None:
    for op in ops:
        action = op.get("action")
        path = op.get("path")
        if not path:
            raise ValueError("file_operation missing 'path'")
        if action == "create":
            fs.create_file(path, op.get("content", ""))
        elif action == "replace":
            fs.replace_file(path, op.get("content", ""), expected_hash=expected_hashes.get(path))
        elif action == "patch":
            fs.patch_file(path, op.get("find", ""), op.get("replace", ""),
                           expected_hash=expected_hashes.get(path))
        elif action == "delete":
            fs.delete_file(path)
        elif action == "move":
            fs.move_file(path, op.get("new_path", ""))
        else:
            raise ValueError(f"Unknown file operation action: {action!r}")
