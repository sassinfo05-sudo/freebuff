"""ActivityService — persists every ActivityEvent BEFORE broadcasting it, so a browser refresh
(or a client that connects to the SSE stream late) never loses task history: it reads persisted
events first, then subscribes for new ones. In-process pub/sub only (no Redis, per instructions);
fine for a single-process private tool — documented as a scaling limit, not hidden.
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator, Dict, List

from ...db import get_db
from ..models import ActivityEvent

_subscribers: Dict[str, List[asyncio.Queue]] = {}


async def emit(task_id: str, kind: str, payload: dict) -> ActivityEvent:
    event = ActivityEvent(task_id=task_id, kind=kind, payload=payload)
    res = await get_db().ds_activity_events.insert_one(event.to_mongo())
    event.id = str(res.inserted_id)
    for q in _subscribers.get(task_id, []):
        q.put_nowait(event)
    return event


async def history(task_id: str, limit: int = 500) -> List[ActivityEvent]:
    docs = get_db().ds_activity_events.find({"task_id": task_id}).sort("created_at", 1).limit(limit)
    return [ActivityEvent.from_mongo(d) async for d in docs]


def _event_to_sse(event: ActivityEvent) -> str:
    data = {"id": event.id, "kind": event.kind, "payload": event.payload, "created_at": event.created_at}
    return f"event: {event.kind}\ndata: {json.dumps(data)}\n\n"


async def stream(task_id: str) -> AsyncIterator[str]:
    """Replays persisted history first, then live events, so reconnecting never loses state."""
    for event in await history(task_id):
        yield _event_to_sse(event)
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.setdefault(task_id, []).append(q)
    try:
        while True:
            event = await q.get()
            yield _event_to_sse(event)
    finally:
        _subscribers.get(task_id, []).remove(q)
