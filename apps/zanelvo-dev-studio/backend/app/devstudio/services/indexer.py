"""RepositoryIndexer + RepositorySearchService.

Builds a lightweight per-file index (language, hash, size, one-line summary, top-level symbols,
imports) into `ds_index_files`, keyed by (project, branch, commit). This is what lets
ContextBuilder hand agents a short, relevant slice of the repository instead of the whole tree —
"Do NOT send the entire repository to every LLM request."
"""
from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

from bson import ObjectId

from ...db import get_db
from ..models import IndexedFile, Project, RepositorySnapshot
from .file_service import _BINARY_EXT, _EXCLUDE_DIRS
from .git_service import GitService
from .workspace_manager import ensure_browse_checkout

_LANG_BY_EXT = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript", ".ts": "typescript",
    ".tsx": "typescript", ".json": "json", ".md": "markdown", ".css": "css",
    ".html": "html", ".yml": "yaml", ".yaml": "yaml", ".toml": "toml", ".sh": "shell",
    ".sql": "sql",
}

_MAX_INDEX_FILE_BYTES = 300_000

_PY_SYMBOL = re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+(\w+)", re.MULTILINE)
_JS_SYMBOL = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)|"
    r"^\s*(?:export\s+)?class\s+(\w+)|"
    r"^\s*(?:export\s+)?const\s+(\w+)\s*=\s*(?:\([^)]*\)\s*=>|async\s*\()",
    re.MULTILINE,
)
_PY_IMPORT = re.compile(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", re.MULTILINE)
_JS_IMPORT = re.compile(r"^\s*import\s+.*?from\s+['\"]([^'\"]+)['\"]", re.MULTILINE)

# FastAPI route markers, useful for the Repository Analyst without a full AST pass.
_API_ROUTE = re.compile(r"@\w*router\.(get|post|put|patch|delete)\(\s*[\"']([^\"']+)")


def _extract_symbols(content: str, language: Optional[str]) -> List[str]:
    if language == "python":
        return list(dict.fromkeys(_PY_SYMBOL.findall(content)))[:60]
    if language in ("javascript", "typescript"):
        found = []
        for a, b, c in _JS_SYMBOL.findall(content):
            found.append(a or b or c)
        return list(dict.fromkeys(x for x in found if x))[:60]
    return []


def _extract_imports(content: str, language: Optional[str]) -> List[str]:
    if language == "python":
        return list(dict.fromkeys(a or b for a, b in _PY_IMPORT.findall(content)))[:40]
    if language in ("javascript", "typescript"):
        return list(dict.fromkeys(_JS_IMPORT.findall(content)))[:40]
    return []


def _summary(content: str, path: str) -> str:
    routes = _API_ROUTE.findall(content)
    if routes:
        return "API routes: " + ", ".join(f"{m.upper()} {p}" for m, p in routes[:8])
    for line in content.splitlines()[:15]:
        s = line.strip().strip('"""').strip("'''").strip("#").strip("//").strip()
        if s and len(s) > 8:
            return s[:200]
    return os.path.basename(path)


async def index_project_branch(project: Project, branch: str) -> RepositorySnapshot:
    path = await ensure_browse_checkout(project, branch)
    git = GitService()
    commit_sha = await git.current_sha(path)
    db = get_db()

    languages: Dict[str, int] = {}
    manifests: List[str] = []
    frontend_root = backend_root = None
    count = 0

    docs_to_write = []
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = [d for d in dirnames if d not in _EXCLUDE_DIRS and not d.startswith(".")]
        for f in filenames:
            full = os.path.join(dirpath, f)
            rel = os.path.relpath(full, path)
            ext = os.path.splitext(f)[1].lower()
            if ext in _BINARY_EXT:
                continue
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            if size > _MAX_INDEX_FILE_BYTES:
                continue
            language = _LANG_BY_EXT.get(ext)
            if language:
                languages[language] = languages.get(language, 0) + 1
            if f in ("package.json", "requirements.txt", "pyproject.toml", "Pipfile", "go.mod"):
                manifests.append(rel)
                if f == "package.json" and frontend_root is None and "backend" not in rel:
                    frontend_root = os.path.dirname(rel) or "."
                if f in ("requirements.txt", "pyproject.toml") and backend_root is None:
                    backend_root = os.path.dirname(rel) or "."
            try:
                with open(full, "rb") as fh:
                    raw = fh.read()
            except OSError:
                continue
            h = hashlib.sha256(raw).hexdigest()[:16]
            count += 1
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError:
                content = ""
            docs_to_write.append(IndexedFile(
                project_id=str(project.id), branch=branch, commit_sha=commit_sha, path=rel,
                language=language, hash=h, size_bytes=size,
                summary=_summary(content, rel) if content else None,
                symbols=_extract_symbols(content, language) if content else [],
                imports=_extract_imports(content, language) if content else [],
            ).to_mongo())

    await db.ds_index_files.delete_many({"project_id": str(project.id), "branch": branch})
    if docs_to_write:
        for i in range(0, len(docs_to_write), 500):
            await db.ds_index_files.insert_many(docs_to_write[i:i + 500])

    snapshot = RepositorySnapshot(
        project_id=str(project.id), branch=branch, commit_sha=commit_sha,
        tree_file_count=count, languages=languages, package_manifests=manifests,
        frontend_root=frontend_root, backend_root=backend_root, indexed=True,
        indexed_at=datetime.now(timezone.utc).isoformat(),
    )
    await db.ds_repository_snapshots.update_one(
        {"project_id": str(project.id), "branch": branch},
        {"$set": snapshot.to_mongo()}, upsert=True,
    )
    await db.ds_projects.update_one({"_id": ObjectId(project.id)},
                                      {"$set": {"last_indexed_commit_sha": commit_sha}})
    return snapshot


async def get_snapshot(project_id: str, branch: str) -> Optional[RepositorySnapshot]:
    doc = await get_db().ds_repository_snapshots.find_one({"project_id": project_id, "branch": branch})
    return RepositorySnapshot.from_mongo(doc)


async def search_index(project_id: str, branch: str, query: str, limit: int = 40) -> List[dict]:
    """Search indexed symbols/paths/summaries (fast, no disk I/O) — used by ContextBuilder to find
    'relevant files' without grepping the whole tree on every agent turn."""
    db = get_db()
    q = query.strip()
    if not q:
        return []
    cursor = db.ds_index_files.find({
        "project_id": project_id, "branch": branch,
        "$or": [
            {"path": {"$regex": re.escape(q), "$options": "i"}},
            {"symbols": {"$regex": re.escape(q), "$options": "i"}},
            {"summary": {"$regex": re.escape(q), "$options": "i"}},
        ],
    }).limit(limit)
    out = []
    async for d in cursor:
        out.append({"path": d["path"], "language": d.get("language"), "summary": d.get("summary"),
                     "symbols": d.get("symbols", [])[:10]})
    return out


async def relevant_files_for(project_id: str, branch: str, keywords: List[str], limit: int = 25) -> List[dict]:
    seen: Dict[str, dict] = {}
    for kw in keywords[:8]:
        for hit in await search_index(project_id, branch, kw, limit=limit):
            seen.setdefault(hit["path"], hit)
    return list(seen.values())[:limit]
