"""UploadService — task/project attachments. Images are exposed to vision-capable agents on
request only (never auto-injected into every context, per spec)."""
from __future__ import annotations

import os
import uuid
from typing import List, Optional

from ...db import get_db
from ..models import Upload

_ALLOWED_TYPES = {
    "image/png": True, "image/jpeg": True, "image/webp": True,
    "application/pdf": False, "text/plain": False, "text/markdown": False,
    "application/json": False, "text/x-log": False, "text/csv": False,
}
_MAX_BYTES = 15 * 1024 * 1024

_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                            "var", "devstudio", "uploads")


class UploadRejected(Exception):
    pass


async def save_upload(filename: str, content_type: str, data: bytes,
                       task_id: Optional[str] = None, project_id: Optional[str] = None) -> Upload:
    if content_type not in _ALLOWED_TYPES:
        raise UploadRejected(f"Content type not allowed: {content_type}")
    if len(data) > _MAX_BYTES:
        raise UploadRejected(f"File too large ({len(data)} bytes, max {_MAX_BYTES})")
    os.makedirs(_UPLOAD_DIR, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}-{os.path.basename(filename)}"
    path = os.path.join(_UPLOAD_DIR, safe_name)
    with open(path, "wb") as fh:
        fh.write(data)
    up = Upload(task_id=task_id, project_id=project_id, filename=filename, content_type=content_type,
                size_bytes=len(data), path=path, is_image=_ALLOWED_TYPES[content_type])
    res = await get_db().ds_uploads.insert_one(up.to_mongo())
    up.id = str(res.inserted_id)
    return up


async def list_uploads(task_id: str) -> List[Upload]:
    docs = get_db().ds_uploads.find({"task_id": task_id}).sort("created_at", -1)
    return [Upload.from_mongo(d) async for d in docs]


async def get_upload(upload_id: str) -> Optional[Upload]:
    from bson import ObjectId
    doc = await get_db().ds_uploads.find_one({"_id": ObjectId(upload_id)})
    return Upload.from_mongo(doc)
