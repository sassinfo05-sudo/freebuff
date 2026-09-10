"""WorkspaceManager — creates and tracks working copies on server disk.

Two kinds of checkout, both derived from a per-project local *bare mirror* (fast, avoids
re-cloning from GitHub on every task):

- "browse" checkout: read-only, kept fast-forwarded to the remote branch HEAD. Used for repository
  browsing/search/indexing before any task exists.
- task workspace: a real working copy with its own `ai/<slug>-<short-id>` branch, created once per
  Task. This is the only place Dev Studio ever writes files or commits.

Nothing here ever touches this application's own `.git` working tree — everything lives under
`backend/var/devstudio/workspaces/` (gitignored).
"""
from __future__ import annotations

import os
import re
import uuid
from typing import Optional

from ...db import get_db
from ..models import Project, Workspace
from .git_service import GitService
from . import github_provider

WORKSPACES_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                                "var", "devstudio", "workspaces")
_ROOT = WORKSPACES_ROOT  # internal alias used throughout this module


def _mirror_path(project: Project) -> str:
    return os.path.join(_ROOT, "_mirrors", f"{project.github_owner}__{project.github_repo}.git")


def _browse_path(project: Project, branch: str) -> str:
    safe_branch = re.sub(r"[^A-Za-z0-9._-]", "_", branch)
    return os.path.join(_ROOT, "_browse", str(project.id), safe_branch)


def slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s or "task")[:max_len]


async def ensure_mirror(project: Project, git: Optional[GitService] = None) -> str:
    git = git or GitService()
    mirror = _mirror_path(project)
    if os.path.isdir(mirror):
        await git.update_mirror(mirror)
    else:
        url = await github_provider.authenticated_clone_url(project.github_owner, project.github_repo)
        await git.clone_mirror(url, mirror)
    return mirror


async def ensure_browse_checkout(project: Project, branch: str) -> str:
    """Fast-forward (or create) a read-only local checkout of `branch` for browsing/indexing."""
    git = GitService()
    mirror = await ensure_mirror(project, git)
    path = _browse_path(project, branch)
    if os.path.isdir(os.path.join(path, ".git")):
        await git.checkout(path, branch)
        # hard-reset to the freshly-updated mirror's branch tip
        sha = await git.remote_head_sha(mirror, branch)
        if sha:
            await git.reset_hard(path, sha)
    else:
        push_url = await github_provider.authenticated_clone_url(project.github_owner, project.github_repo)
        await git.clone_from_mirror(mirror, path, branch, push_url)
    return path


async def provision_task_workspace(project: Project, branch: str, task_id: str, task_title: str) -> Workspace:
    git = GitService(task_id=task_id)
    mirror = await ensure_mirror(project, git)
    dest = os.path.join(_ROOT, task_id)
    push_url = await github_provider.authenticated_clone_url(project.github_owner, project.github_repo)
    await git.clone_from_mirror(mirror, dest, branch, push_url)
    base_sha = await git.current_sha(dest)
    working_branch = f"ai/{slugify(task_title)}-{uuid.uuid4().hex[:6]}"
    await git.create_and_checkout_branch(dest, working_branch, "HEAD")
    remote_head = await git.remote_head_sha(mirror, branch)

    ws = Workspace(project_id=str(project.id), task_id=task_id, base_branch=branch,
                    base_commit_sha=base_sha, working_branch=working_branch, local_path=dest,
                    remote_head_sha=remote_head, status="ready")
    res = await get_db().ds_workspaces.insert_one(ws.to_mongo())
    ws.id = str(res.inserted_id)
    return ws


async def detect_remote_drift(project: Project, workspace: Workspace) -> bool:
    """True if the base branch has moved on GitHub since this workspace was provisioned."""
    git = GitService()
    url = await github_provider.authenticated_clone_url(project.github_owner, project.github_repo)
    current = await git.remote_head_sha(url, workspace.base_branch)
    return bool(current and workspace.remote_head_sha and current != workspace.remote_head_sha)


async def get_workspace(workspace_id: str) -> Optional[Workspace]:
    doc = await get_db().ds_workspaces.find_one({"_id": _oid(workspace_id)})
    return Workspace.from_mongo(doc)


async def get_workspace_for_task(task_id: str) -> Optional[Workspace]:
    doc = await get_db().ds_workspaces.find_one({"task_id": task_id})
    return Workspace.from_mongo(doc)


def _oid(id_str: str):
    from bson import ObjectId
    return ObjectId(id_str)
