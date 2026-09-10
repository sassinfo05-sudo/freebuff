"""ProjectMemoryService — durable engineering memory, independent of any single task's chat.

"If current code conflicts with memory: CURRENT CODE WINS. Mark memory stale." Dev Studio never
auto-deletes memory on conflict — it marks it stale and lets the founder (or a later Analyst pass)
refresh it, preserving history via MemoryRevision.
"""
from __future__ import annotations

from typing import List, Optional

from bson import ObjectId

from ...db import get_db, utc_now_iso
from ..models import MemoryCategory, MemoryRevision, ProjectMemory


async def add_memory(project_id: str, category: MemoryCategory, title: str, content: str,
                      branch: Optional[str] = None, commit_sha: Optional[str] = None,
                      source_task_id: Optional[str] = None, confidence: str = "medium") -> ProjectMemory:
    mem = ProjectMemory(project_id=project_id, category=category, title=title, content=content,
                         branch=branch, commit_sha=commit_sha, source_task_id=source_task_id,
                         confidence=confidence)
    res = await get_db().ds_project_memory.insert_one(mem.to_mongo())
    mem.id = str(res.inserted_id)
    return mem


async def list_memory(project_id: str, category: Optional[str] = None,
                       include_stale: bool = True) -> List[ProjectMemory]:
    q = {"project_id": project_id}
    if category:
        q["category"] = category
    if not include_stale:
        q["stale"] = {"$ne": True}
    docs = get_db().ds_project_memory.find(q).sort("category", 1)
    return [ProjectMemory.from_mongo(d) async for d in docs]


async def search_memory(project_id: str, query: str) -> List[ProjectMemory]:
    import re as _re
    docs = get_db().ds_project_memory.find({
        "project_id": project_id,
        "$or": [{"title": {"$regex": _re.escape(query), "$options": "i"}},
                 {"content": {"$regex": _re.escape(query), "$options": "i"}}],
    })
    return [ProjectMemory.from_mongo(d) async for d in docs]


async def update_memory(memory_id: str, content: str, reason: str) -> ProjectMemory:
    db = get_db()
    existing = await db.ds_project_memory.find_one({"_id": ObjectId(memory_id)})
    if not existing:
        raise ValueError("Memory entry not found")
    rev = MemoryRevision(memory_id=memory_id, previous_content=existing.get("content", ""), reason=reason)
    await db.ds_memory_revisions.insert_one(rev.to_mongo())
    await db.ds_project_memory.update_one(
        {"_id": ObjectId(memory_id)},
        {"$set": {"content": content, "stale": False, "updated_at": utc_now_iso()}},
    )
    doc = await db.ds_project_memory.find_one({"_id": ObjectId(memory_id)})
    return ProjectMemory.from_mongo(doc)


async def mark_stale(memory_id: str, reason: str = "code changed") -> None:
    db = get_db()
    existing = await db.ds_project_memory.find_one({"_id": ObjectId(memory_id)})
    if existing:
        rev = MemoryRevision(memory_id=memory_id, previous_content=existing.get("content", ""), reason=reason)
        await db.ds_memory_revisions.insert_one(rev.to_mongo())
    await db.ds_project_memory.update_one({"_id": ObjectId(memory_id)}, {"$set": {"stale": True}})


async def delete_memory(memory_id: str) -> None:
    await get_db().ds_project_memory.delete_one({"_id": ObjectId(memory_id)})
