"""TaskManager — create/load/list tasks, plan items, messages; the only place that calls
state_machine.transition() and persists the result (with an ActivityEvent for every change)."""
from __future__ import annotations

from typing import List, Optional

from bson import ObjectId

from ...db import get_db, utc_now_iso
from .. import state_machine
from ..models import (CreateTaskRequest, PlanItem, Task, TaskMessage, TaskMessageRequest, TaskStatus)
from . import activity_service, anti_loop

DEFAULT_CHAT_TITLE = "New chat"


def generate_title_from_text(text: str) -> str:
    """Heuristic chat title from a first message — first line, truncated at a word boundary.
    No LLM call: fast, free, and the user can always rename it (PATCH /tasks/{id})."""
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    if not first_line:
        return DEFAULT_CHAT_TITLE
    limit = 60
    if len(first_line) <= limit:
        return first_line
    truncated = first_line[:limit].rsplit(" ", 1)[0] or first_line[:limit]
    return truncated.rstrip(",.;:") + "…"


async def create_task(req: CreateTaskRequest, created_by: Optional[str]) -> Task:
    budget = anti_loop.budget_for_preset("BALANCED")
    title = req.title or (generate_title_from_text(req.request_text) if req.request_text.strip()
                           else DEFAULT_CHAT_TITLE)
    task = Task(project_id=req.project_id, title=title, request_text=req.request_text,
                mode=req.mode, branch=req.branch, model_preset=req.model_preset,
                iteration_budget=budget, created_by=created_by)
    res = await get_db().ds_tasks.insert_one(task.to_mongo())
    task.id = str(res.inserted_id)
    await activity_service.emit(task.id, "task_created", {"title": task.title, "mode": task.mode})
    if req.request_text.strip():
        await add_message(task.id, "user", req.request_text)
    return task


async def get_task(task_id: str) -> Optional[Task]:
    doc = await get_db().ds_tasks.find_one({"_id": ObjectId(task_id)})
    return Task.from_mongo(doc)


async def list_tasks(project_id: Optional[str] = None) -> List[Task]:
    q: dict = {"archived": {"$ne": True}}
    if project_id:
        q["project_id"] = project_id
    docs = get_db().ds_tasks.find(q).sort("created_at", -1)
    return [Task.from_mongo(d) async for d in docs]


async def archive_task(task_id: str) -> None:
    await get_db().ds_tasks.update_one({"_id": ObjectId(task_id)},
                                         {"$set": {"archived": True, "updated_at": utc_now_iso()}})


async def set_status(task_id: str, target: TaskStatus, note: Optional[str] = None) -> Task:
    task = await get_task(task_id)
    if not task:
        raise ValueError("Task not found")
    new_status = state_machine.transition(task.status, target)
    await get_db().ds_tasks.update_one({"_id": ObjectId(task_id)},
                                         {"$set": {"status": new_status, "updated_at": utc_now_iso()}})
    await activity_service.emit(task_id, "state_change",
                                  {"from": task.status, "to": new_status, "note": note})
    task.status = new_status
    return task


async def update_task(task_id: str, **fields) -> Task:
    fields["updated_at"] = utc_now_iso()
    await get_db().ds_tasks.update_one({"_id": ObjectId(task_id)}, {"$set": fields})
    return await get_task(task_id)


async def request_stop(task_id: str) -> Task:
    await get_db().ds_tasks.update_one({"_id": ObjectId(task_id)}, {"$set": {"stop_requested": True}})
    await activity_service.emit(task_id, "stop_requested", {})
    return await get_task(task_id)


async def clear_stop(task_id: str) -> None:
    await get_db().ds_tasks.update_one({"_id": ObjectId(task_id)}, {"$set": {"stop_requested": False}})


async def is_stop_requested(task_id: str) -> bool:
    task = await get_task(task_id)
    return bool(task and task.stop_requested)


async def add_message(task_id: str, role: str, text: str, attachments: Optional[List[str]] = None) -> TaskMessage:
    msg = TaskMessage(task_id=task_id, role=role, text=text, attachments=attachments or [])
    res = await get_db().ds_task_messages.insert_one(msg.to_mongo())
    msg.id = str(res.inserted_id)
    await activity_service.emit(task_id, "message", {"role": role, "text": text})
    return msg


async def add_message_from_request(task_id: str, req: TaskMessageRequest) -> TaskMessage:
    return await add_message(task_id, "user", req.text, req.attachments)


async def list_messages(task_id: str) -> List[dict]:
    docs = get_db().ds_task_messages.find({"task_id": task_id}).sort("created_at", 1)
    out = []
    async for d in docs:
        out.append({"role": d["role"], "text": d["text"], "created_at": d["created_at"]})
    return out


# --- Plan items --------------------------------------------------------------------------

async def set_plan(task_id: str, items: List[dict]) -> List[PlanItem]:
    db = get_db()
    await db.ds_plan_items.delete_many({"task_id": task_id})
    out: List[PlanItem] = []
    for i, item in enumerate(items):
        # The planner LLM is asked for title strings, but models occasionally emit positional
        # indices/ids instead despite the prompt — coerce to str rather than crash the run; an
        # unmatched value just fails the id/title lookup in orchestrator._implement_loop, which
        # already treats that as "not a real dependency" rather than erroring.
        depends_on = [str(d) for d in item.get("depends_on", []) if d is not None]
        pi = PlanItem(task_id=task_id, order=i, title=item["title"], description=item["description"],
                       assigned_agent=item.get("assigned_agent", "backend"),
                       relevant_files=item.get("relevant_files", []),
                       acceptance_criteria=item.get("acceptance_criteria", []),
                       verification_method=item.get("verification_method", ""),
                       depends_on=depends_on)
        res = await db.ds_plan_items.insert_one(pi.to_mongo())
        pi.id = str(res.inserted_id)
        out.append(pi)
    await activity_service.emit(task_id, "plan_created", {"item_count": len(out)})
    return out


async def list_plan_items(task_id: str) -> List[PlanItem]:
    docs = get_db().ds_plan_items.find({"task_id": task_id}).sort("order", 1)
    return [PlanItem.from_mongo(d) async for d in docs]


async def set_plan_item_status(plan_item_id: str, target: str, evidence: Optional[dict] = None) -> PlanItem:
    doc = await get_db().ds_plan_items.find_one({"_id": ObjectId(plan_item_id)})
    if not doc:
        raise ValueError("Plan item not found")
    current = PlanItem.from_mongo(doc)
    if state_machine.requires_evidence(target) and not (evidence or current.evidence):
        raise ValueError("Plan item cannot become VERIFIED without evidence (a test/build reference)")
    new_status = state_machine.plan_item_transition(current.status, target)
    update = {"status": new_status, "updated_at": utc_now_iso()}
    push = {"$set": update}
    if evidence:
        push["$push"] = {"evidence": evidence}
    await get_db().ds_plan_items.update_one({"_id": ObjectId(plan_item_id)}, push)
    await activity_service.emit(current.task_id, "plan_item_status",
                                  {"plan_item_id": plan_item_id, "title": current.title,
                                    "from": current.status, "to": new_status})
    current.status = new_status
    return current


async def reassign_plan_item(plan_item_id: str, new_agent: str, reason: str) -> PlanItem:
    """Hands a plan item to a different role for its next attempt — used by the anti-loop escalation
    path (see orchestrator._escalate_strategy) to route a repeatedly-failing item to a specialist
    (e.g. troubleshoot) instead of retrying the same role/strategy a third time."""
    doc = await get_db().ds_plan_items.find_one({"_id": ObjectId(plan_item_id)})
    if not doc:
        raise ValueError("Plan item not found")
    current = PlanItem.from_mongo(doc)
    await get_db().ds_plan_items.update_one(
        {"_id": ObjectId(plan_item_id)},
        {"$set": {"assigned_agent": new_agent, "updated_at": utc_now_iso()}},
    )
    await activity_service.emit(current.task_id, "plan_item_reassigned",
                                  {"plan_item_id": plan_item_id, "title": current.title,
                                    "from_agent": current.assigned_agent, "to_agent": new_agent,
                                    "reason": reason})
    current.assigned_agent = new_agent
    return current


async def all_required_items_verified(task_id: str) -> bool:
    items = await list_plan_items(task_id)
    if not items:
        return False
    return all(i.status in ("VERIFIED", "SKIPPED") for i in items)
