"""AgentRegistry — per-role AgentConfiguration (enabled, primary/fallback provider+model,
reasoning level, max attempts, automatic fallback), seeded with defaults and overridable per role
or wholesale via a global preset (ECONOMICAL/BALANCED/MAX_QUALITY)."""
from __future__ import annotations

from typing import Dict, List

from ...db import get_db, utc_now_iso
from ..models import AgentConfiguration, AgentRole
from ..providers.registry import preset_for_role

ROLES: List[AgentRole] = [
    "supervisor", "repository_analyst", "planner", "design", "frontend", "backend",
    "integration", "qa", "reviewer", "git",
]


def _default_config(role: AgentRole, preset: str = "BALANCED") -> AgentConfiguration:
    p = preset_for_role(preset, role)
    return AgentConfiguration(
        role=role, enabled=True,
        primary_provider=p["primary_provider"], primary_model=p["primary_model"],
        fallback_provider=p["fallback_provider"], fallback_model=p["fallback_model"],
        reasoning_level="medium" if role in ("planner", "reviewer") else None,
        max_attempts=2, automatic_fallback=True,
    )


async def ensure_defaults(preset: str = "BALANCED") -> None:
    db = get_db()
    for role in ROLES:
        existing = await db.ds_agent_configs.find_one({"role": role})
        if not existing:
            await db.ds_agent_configs.insert_one(_default_config(role, preset).to_mongo())


async def get_config(role: AgentRole) -> AgentConfiguration:
    doc = await get_db().ds_agent_configs.find_one({"role": role})
    if not doc:
        cfg = _default_config(role)
        res = await get_db().ds_agent_configs.insert_one(cfg.to_mongo())
        cfg.id = str(res.inserted_id)
        return cfg
    return AgentConfiguration.from_mongo(doc)


async def list_configs() -> Dict[str, AgentConfiguration]:
    await ensure_defaults()
    docs = get_db().ds_agent_configs.find({})
    out = {}
    async for d in docs:
        cfg = AgentConfiguration.from_mongo(d)
        out[cfg.role] = cfg
    return out


async def update_config(role: AgentRole, **fields) -> AgentConfiguration:
    fields["updated_at"] = utc_now_iso()
    await get_db().ds_agent_configs.update_one({"role": role}, {"$set": fields}, upsert=True)
    return await get_config(role)


async def apply_preset(preset: str) -> Dict[str, AgentConfiguration]:
    for role in ROLES:
        p = preset_for_role(preset, role)
        await update_config(role, primary_provider=p["primary_provider"], primary_model=p["primary_model"],
                             fallback_provider=p["fallback_provider"], fallback_model=p["fallback_model"])
    return await list_configs()
