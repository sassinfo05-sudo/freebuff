"""MongoDB connection + BaseDocument with ObjectId <-> id coercion."""
import os
from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def _coerce_object_id(v: Any) -> str:
    if v is None:
        return v
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, str):
        return v
    raise ValueError("Invalid ObjectId")


PyObjectId = Annotated[str, BeforeValidator(_coerce_object_id)]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BaseDocument(BaseModel):
    """All Mongo-backed models extend this. `id` maps to Mongo `_id`."""

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)

    def to_mongo(self) -> dict:
        data = self.model_dump(by_alias=True, exclude_none=True)
        # Mongo generates _id on insert if not present
        if "_id" in data and data["_id"] is None:
            del data["_id"]
        return data

    @classmethod
    def from_mongo(cls, doc: Optional[dict]):
        if not doc:
            return None
        # Copy so we don't mutate the caller's dict — some callers still need
        # doc["_id"] as an ObjectId for follow-up queries (e.g. update_one).
        doc = {**doc}
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return cls.model_validate(doc)


# Mongo client (single, shared)
_mongo_client: Optional[AsyncIOMotorClient] = None


def get_client() -> AsyncIOMotorClient:
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return _mongo_client


def get_db():
    return get_client()[os.environ["DB_NAME"]]
