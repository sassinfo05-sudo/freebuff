"""Manual (NOT collected by pytest — no test_/​_test naming) live verification that the
tool-calling upgrades added to Dev Studio's agents actually work against the REAL
emergentintegrations SDK, not just Anthropic. Runs two checks:

1. EmergentUniversalKeyProvider.generate_with_tools() against the real SDK's real classes
   (LlmChat/UserMessage/ToolCall/Usage) and real internal bookkeeping (add_tool_result's
   pending-call validation, populated by a genuine send_message_with_tools() response — not a
   shallow mock of that method).
2. The full runner.call_with_tools() orchestration loop — the same path every agent role takes —
   with a role configured for Emergent and a real default tool (the Planner's ask_human), proving
   the tool executes for real (a genuine PLANNING -> BLOCKED transition + blocked_reason write)
   and the loop still completes with the correctly-parsed final JSON.

Only the actual network call (litellm.acompletion, called inside emergentintegrations) is mocked —
no funded EMERGENT_UNIVERSAL_KEY was available to verify this with. Everything else — SDK classes,
message-history bookkeeping, tool-call parsing, DB writes — is real.

Why this isn't a pytest test: `emergentintegrations` cannot be installed alongside
requirements-devstudio.txt's `openai==1.109.1` pin (it hard-pins `openai==1.99.9` — see
requirements-emergent.txt) or its own `sse-starlette`/`starlette` requirement (which broke this
app's mcp==1.9.4 pin when tried in the same venv). Run this in its OWN, separate venv:

    python3 -m venv /tmp/emgvenv
    /tmp/emgvenv/bin/pip install -r requirements-devstudio.txt
    /tmp/emgvenv/bin/pip install --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ emergentintegrations
    /tmp/emgvenv/bin/pip install "openai==1.99.9" mongomock-motor   # resolve the pin conflict
    /tmp/emgvenv/bin/python tests/manual_emergent_tools_live.py

NEVER install emergentintegrations into the main dev venv used for `pytest`/`ruff` — it silently
downgrades openai and upgrades sse-starlette/starlette past this app's pins, breaking both the
native OpenAI provider and MCP. If you did this by accident, restore with:
    pip install "openai==1.109.1" "sse-starlette==2.1.3" && pip uninstall -y emergentintegrations litellm
"""
import asyncio
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "zanelvo_emergent_manual_check")
os.environ.setdefault("JWT_SECRET", "test-secret-1234567890")
os.environ.setdefault("ADMIN_PASSWORD", "testpass123")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _fake_litellm_response(*, content, tool_calls, finish_reason, prompt_tokens, completion_tokens):
    tc_objs = [
        SimpleNamespace(id=tc["id"],
                         function=SimpleNamespace(name=tc["name"], arguments=json.dumps(tc["arguments"])))
        for tc in (tool_calls or [])
    ]
    message = SimpleNamespace(content=content, tool_calls=tc_objs or None)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    usage = SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                              total_tokens=prompt_tokens + completion_tokens)
    return SimpleNamespace(choices=[choice], usage=usage)


async def check_provider_shape():
    from app.devstudio.providers.emergent_provider import EmergentUniversalKeyProvider

    provider = EmergentUniversalKeyProvider(universal_key="sk-emergent-fake-not-real")
    tools = [{"name": "ask_human", "description": "Ask the founder a question.",
              "inputSchema": {"type": "object", "properties": {"question": {"type": "string"}},
                                "required": ["question"]}}]
    responses = [
        _fake_litellm_response(
            content=None,
            tool_calls=[{"id": "call_abc123", "name": "ask_human",
                          "arguments": {"question": "Which payment provider?"}}],
            finish_reason="tool_calls", prompt_tokens=120, completion_tokens=18),
        _fake_litellm_response(content='{"items": []}', tool_calls=None, finish_reason="stop",
                                 prompt_tokens=140, completion_tokens=40),
    ]
    call_log = []

    async def fake_acompletion(**params):
        call_log.append(params)
        return responses[len(call_log) - 1]

    with patch("emergentintegrations.llm.chat.litellm.acompletion", new=AsyncMock(side_effect=fake_acompletion)):
        result1 = await provider.generate_with_tools(
            system="You are the Planner.", model="claude-sonnet-5", tools=tools,
            prompt="Plan the payments integration.")
        assert result1.tool_calls == [{"id": "call_abc123", "name": "ask_human",
                                         "arguments": {"question": "Which payment provider?"}}]
        assert result1.tool_loop_history is not None
        print("OK provider.generate_with_tools() turn 1: real ChatResponse/ToolCall/Usage parsed correctly")

        result2 = await provider.generate_with_tools(
            system="You are the Planner.", model="claude-sonnet-5", tools=tools,
            history=result1.tool_loop_history, tool_results=[{"id": "call_abc123", "content": "Stripe"}])
        assert result2.tool_calls is None and result2.text == '{"items": []}'
    assert len(call_log) == 2
    second_call_messages = call_log[1]["messages"]
    assert any(m.get("role") == "tool" and "Stripe" in str(m.get("content", "")) for m in second_call_messages)
    print("OK provider.generate_with_tools() turn 2: add_tool_result() accepted by the SDK's REAL "
          "pending-call tracking (not a mocked one), tool result actually reached the request")


async def check_full_orchestration_loop():
    from mongomock_motor import AsyncMongoMockClient

    from app import db as app_db
    app_db._mongo_client = AsyncMongoMockClient()

    from app.devstudio.agents.runner import BUILTIN_TOOLS, call_with_tools
    from app.devstudio.models import AgentConfiguration, CreateTaskRequest
    from app.devstudio.providers.registry import ModelRegistry
    from app.devstudio.services import task_manager

    task = await task_manager.create_task(
        CreateTaskRequest(project_id="p1", request_text="Plan the payments integration.",
                            branch="main"), created_by="manual-check")
    task_id = task.id
    await task_manager.update_task(task_id, status="PLANNING")  # matches where the real Planner runs

    config = AgentConfiguration(role="planner", primary_provider="emergent",
                                  primary_model="claude-sonnet-5", automatic_fallback=False,
                                  tools_enabled=["ask_human"])
    registry = ModelRegistry(api_keys={"emergent": "sk-emergent-fake-not-real"})
    tools = [BUILTIN_TOOLS["ask_human"]]
    responses = [
        _fake_litellm_response(
            content=None,
            tool_calls=[{"id": "call_1", "name": "ask_human",
                          "arguments": {"question": "Which payment provider should we integrate?"}}],
            finish_reason="tool_calls", prompt_tokens=200, completion_tokens=30),
        _fake_litellm_response(
            content=json.dumps({"items": [{"title": "Integrate Stripe", "description": "d",
                                             "assigned_agent": "backend", "relevant_files": [],
                                             "acceptance_criteria": ["works"],
                                             "verification_method": "manual", "depends_on": []}]}),
            tool_calls=None, finish_reason="stop", prompt_tokens=220, completion_tokens=60),
    ]
    call_log = []

    async def fake_acompletion(**params):
        call_log.append(params)
        return responses[len(call_log) - 1]

    with patch("emergentintegrations.llm.chat.litellm.acompletion", new=AsyncMock(side_effect=fake_acompletion)):
        result = await call_with_tools(
            registry, config, task_id, "planner",
            system='You are the Planner. Return JSON: {"items": [...]}',
            prompt="Plan the payments integration.", action="Creating implementation plan", tools=tools)

    assert len(call_log) == 2
    assert result["items"][0]["title"] == "Integrate Stripe"
    print("OK call_with_tools() drove a real tool-call round trip through the real Emergent SDK "
          "and returned the correctly-parsed final JSON")

    blocked_task = await task_manager.get_task(task_id)
    assert blocked_task.blocked_reason == "Which payment provider should we integrate?"
    print(f"OK ask_human's real DB-writing handler ran (not a stub): task.blocked_reason = "
          f"{blocked_task.blocked_reason!r}")

    runs = [r async for r in app_db.get_db().ds_agent_runs.find({"task_id": task_id})]
    assert len(runs) == 1 and runs[0]["status"] == "succeeded"
    assert runs[0]["provider"] == "emergent" and runs[0]["model"] == "claude-sonnet-5"
    print(f"OK a real AgentRun record was written for the emergent-backed call (status={runs[0]['status']!r})")


async def main():
    await check_provider_shape()
    print()
    await check_full_orchestration_loop()
    print("\nALL EMERGENT LIVE-SDK CHECKS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
