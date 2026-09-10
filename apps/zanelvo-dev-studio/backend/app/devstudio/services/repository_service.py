"""RepositoryService — Project CRUD + repository browsing (tree/read/search) against a
fast-forwarded local checkout, independent of any task workspace."""
from __future__ import annotations

from typing import List, Optional

from bson import ObjectId

from ...db import get_db
from ..models import CreateProjectRequest, Project
from . import github_provider
from .file_service import FileService
from .git_service import GitService
from .workspace_manager import ensure_browse_checkout


async def create_project(req: CreateProjectRequest) -> Project:
    repo_meta = await github_provider.get_repo(req.github_owner, req.github_repo)
    project = Project(
        name=req.name or f"{req.github_owner}/{req.github_repo}",
        github_owner=req.github_owner, github_repo=req.github_repo,
        default_branch=req.default_branch or repo_meta["default_branch"],
        description=req.description,
    )
    res = await get_db().ds_projects.insert_one(project.to_mongo())
    project.id = str(res.inserted_id)
    return project


async def list_projects() -> List[Project]:
    docs = get_db().ds_projects.find({"archived": {"$ne": True}}).sort("created_at", -1)
    return [Project.from_mongo(d) async for d in docs]


async def get_project(project_id: str) -> Optional[Project]:
    doc = await get_db().ds_projects.find_one({"_id": ObjectId(project_id)})
    return Project.from_mongo(doc)


async def list_branches(project: Project) -> list:
    return await github_provider.list_branches(project.github_owner, project.github_repo)


async def browse_tree(project: Project, branch: str, subdir: str = ""):
    path = await ensure_browse_checkout(project, branch)
    return FileService(path).list_tree(subdir)


async def browse_read_file(project: Project, branch: str, rel_path: str) -> str:
    path = await ensure_browse_checkout(project, branch)
    return FileService(path).read_file(rel_path)


async def browse_search(project: Project, branch: str, query: str, glob: Optional[str] = None):
    path = await ensure_browse_checkout(project, branch)
    return FileService(path).search_repo(query, glob=glob)


async def current_commit_sha(project: Project, branch: str) -> str:
    path = await ensure_browse_checkout(project, branch)
    return await GitService().current_sha(path)
