"""ContextBuilder — assembles the minimal, role-appropriate context for each agent call.

Never resends full chat history: task messages are summarized into a short "conversation so far"
block, and repository content is limited to indexed search hits / explicitly relevant files rather
than the whole tree (see services/indexer.py).
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..models import PlanItem, Task
from . import indexer, memory_service


def _messages_summary(messages: List[dict], max_chars: int = 2000) -> str:
    lines = [f"[{m['role']}] {m['text']}" for m in messages[-12:]]
    text = "\n".join(lines)
    return text[-max_chars:]


async def build_supervisor_context(task: Task, messages: List[dict]) -> Dict[str, Any]:
    return {
        "task_title": task.title,
        "request": task.request_text,
        "mode": task.mode,
        "status": task.status,
        "conversation": _messages_summary(messages),
        "iterations_used": task.iterations_used,
        "iteration_budget": task.iteration_budget,
    }


async def build_analyst_context(task: Task, project_id: str, branch: str) -> Dict[str, Any]:
    snapshot = await indexer.get_snapshot(project_id, branch)
    keywords = [w for w in task.request_text.replace("\n", " ").split(" ") if len(w) > 3][:10]
    relevant = await indexer.relevant_files_for(project_id, branch, keywords)
    memories = await memory_service.list_memory(project_id, include_stale=False)
    arch_memory = [m for m in memories if m.category in ("ARCHITECTURE", "PROJECT_OVERVIEW", "CODING_CONVENTIONS")]
    return {
        "request": task.request_text,
        "repository_summary": {
            "languages": snapshot.languages if snapshot else {},
            "package_manifests": snapshot.package_manifests if snapshot else [],
            "frontend_root": snapshot.frontend_root if snapshot else None,
            "backend_root": snapshot.backend_root if snapshot else None,
            "commit_sha": snapshot.commit_sha if snapshot else None,
        },
        "likely_relevant_files": relevant,
        "architecture_memory": [{"title": m.title, "content": m.content[:600]} for m in arch_memory[:8]],
    }


async def build_planner_context(task: Task, analysis_text: str, project_id: str) -> Dict[str, Any]:
    conventions = await memory_service.list_memory(project_id, category="CODING_CONVENTIONS", include_stale=False)
    return {
        "request": task.request_text,
        "mode": task.mode,
        "repository_analysis": analysis_text,
        "conventions": [m.content[:400] for m in conventions[:5]],
    }


async def build_implementer_context(task: Task, plan_item: PlanItem, project_id: str, branch: str,
                                      file_contents: Dict[str, str]) -> Dict[str, Any]:
    memories = await memory_service.list_memory(project_id, include_stale=False)
    relevant_mem = [m for m in memories
                     if m.category in ("FRONTEND", "BACKEND", "DATABASE", "AUTHENTICATION",
                                        "AUTHORIZATION", "DESIGN_SYSTEM", "CODING_CONVENTIONS")]
    return {
        "plan_item": {"title": plan_item.title, "description": plan_item.description,
                       "acceptance_criteria": plan_item.acceptance_criteria,
                       "relevant_files": plan_item.relevant_files},
        "task_request": task.request_text,
        "file_contents": file_contents,
        "conventions_and_context": [m.content[:500] for m in relevant_mem[:6]],
    }


async def build_qa_context(task: Task, plan_items: List[PlanItem], diff_summary: dict) -> Dict[str, Any]:
    return {
        "acceptance_criteria": [ac for pi in plan_items for ac in pi.acceptance_criteria],
        "diff": diff_summary,
        "mode": task.mode,
    }


async def build_reviewer_context(task: Task, diff_summary: dict, test_evidence: List[dict],
                                   failure_history: List[dict]) -> Dict[str, Any]:
    return {
        "original_request": task.request_text,
        "diff": diff_summary,
        "test_evidence": test_evidence,
        "failure_history": failure_history[-10:],
    }
