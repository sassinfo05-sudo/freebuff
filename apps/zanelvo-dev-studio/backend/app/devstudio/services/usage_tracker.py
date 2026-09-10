"""UsageTracker — records exactly what each provider call returned. Never invents unavailable
data (e.g. Anthropic responses carry no $ cost, so cost_usd stays null — it is not estimated)."""
from __future__ import annotations

from typing import List, Optional

from ...db import get_db
from ..models import AgentRole, LLMInvocation
from ..providers.base import LLMResult


async def record_invocation(task_id: str, role: AgentRole, result: LLMResult,
                             agent_run_id: Optional[str] = None, kind: str = "generate",
                             ok: bool = True, error: Optional[str] = None) -> LLMInvocation:
    inv = LLMInvocation(
        task_id=task_id, agent_run_id=agent_run_id, role=role,
        provider=result.provider or "unknown", model=result.model or "unknown", kind=kind,
        input_tokens=result.usage.input_tokens or None, output_tokens=result.usage.output_tokens or None,
        cache_tokens=result.usage.cache_tokens or None, cost_usd=result.usage.cost_usd,
        duration_ms=result.usage.duration_ms, ok=ok, error=error,
    )
    res = await get_db().ds_llm_invocations.insert_one(inv.to_mongo())
    inv.id = str(res.inserted_id)
    return inv


async def task_usage_summary(task_id: str) -> dict:
    docs = get_db().ds_llm_invocations.find({"task_id": task_id})
    totals = {"input_tokens": 0, "output_tokens": 0, "cache_tokens": 0, "cost_usd": 0.0, "calls": 0}
    any_cost = False
    async for d in docs:
        totals["calls"] += 1
        totals["input_tokens"] += d.get("input_tokens") or 0
        totals["output_tokens"] += d.get("output_tokens") or 0
        totals["cache_tokens"] += d.get("cache_tokens") or 0
        if d.get("cost_usd") is not None:
            totals["cost_usd"] += d["cost_usd"]
            any_cost = True
    if not any_cost:
        totals["cost_usd"] = None  # never fabricate a $0.00 that looks like real data
    return totals


async def list_invocations(task_id: str) -> List[LLMInvocation]:
    docs = get_db().ds_llm_invocations.find({"task_id": task_id}).sort("created_at", -1)
    return [LLMInvocation.from_mongo(d) async for d in docs]
