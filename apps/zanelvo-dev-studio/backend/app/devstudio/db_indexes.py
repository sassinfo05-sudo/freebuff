"""Mongo indexes for Dev Studio's `ds_*` collections. Called once from server.py's startup hook,
mirroring the main app's index-creation pattern in server.py."""
from __future__ import annotations

from ..db import get_db


async def ensure_indexes() -> None:
    db = get_db()
    await db.ds_projects.create_index([("github_owner", 1), ("github_repo", 1)])
    await db.ds_repository_snapshots.create_index([("project_id", 1), ("branch", 1)], unique=True)
    await db.ds_index_files.create_index([("project_id", 1), ("branch", 1), ("path", 1)])
    await db.ds_workspaces.create_index("task_id")
    await db.ds_tasks.create_index([("project_id", 1), ("created_at", -1)])
    await db.ds_task_messages.create_index([("task_id", 1), ("created_at", 1)])
    await db.ds_plan_items.create_index([("task_id", 1), ("order", 1)])
    await db.ds_agent_configs.create_index("role", unique=True)
    await db.ds_agent_runs.create_index([("task_id", 1), ("created_at", -1)])
    await db.ds_llm_invocations.create_index([("task_id", 1), ("created_at", -1)])
    await db.ds_project_memory.create_index([("project_id", 1), ("category", 1)])
    await db.ds_memory_revisions.create_index("memory_id")
    await db.ds_failure_records.create_index([("task_id", 1), ("fingerprint", 1)], unique=True)
    await db.ds_test_runs.create_index([("task_id", 1), ("created_at", -1)])
    await db.ds_browser_runs.create_index([("task_id", 1), ("created_at", -1)])
    await db.ds_screenshots.create_index("task_id")
    await db.ds_checkpoints.create_index([("task_id", 1), ("created_at", -1)])
    await db.ds_git_operations.create_index([("task_id", 1), ("created_at", -1)])
    await db.ds_uploads.create_index("task_id")
    await db.ds_activity_events.create_index([("task_id", 1), ("created_at", 1)])
    await db.ds_custom_agent_roles.create_index("role", unique=True)
    await db.ds_mcp_servers.create_index("name", unique=True)
