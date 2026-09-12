"""Deterministic tests for MCP presets and the built-in agent tool-calling plumbing. No DB, no
network, no subprocess — the live end-to-end pieces (an actual MCP server round trip, an actual
Anthropic/Emergent tool-calling API call) were verified manually this session (see the session
notes / commit message) since they need real credentials or npx/node this test environment can't
assume every CI runner has; what's covered here is everything that doesn't.
"""
import asyncio

import pytest

from app.devstudio.agents.runner import BUILTIN_TOOLS, ToolExecutionError, _execute_tool_call, _run_builtin_tool
from app.devstudio.services.custom_agent_service import SEED_ROLES
from app.devstudio.services.mcp_service import PRESETS


def test_mcp_presets_are_well_formed():
    assert set(PRESETS) == {"memory", "notion"}
    for name, preset in PRESETS.items():
        assert preset["transport"] in ("stdio", "http")
        if preset["transport"] == "stdio":
            assert preset["command"]
            assert isinstance(preset["args"], list) and preset["args"]
        assert isinstance(preset["env_keys"], list)
        assert preset["description"]


def test_notion_preset_declares_its_required_token():
    assert PRESETS["notion"]["env_keys"] == ["NOTION_TOKEN"]


def test_memory_preset_needs_no_credentials():
    assert PRESETS["memory"]["env_keys"] == []


def test_builtin_tools_all_have_a_valid_json_schema_shape():
    for name, tool in BUILTIN_TOOLS.items():
        assert tool["name"] == name
        assert tool["description"]
        schema = tool["inputSchema"]
        assert schema["type"] == "object"
        assert isinstance(schema.get("properties"), dict)
        assert isinstance(schema.get("required", []), list)


def test_finish_tool_acknowledges_the_summary():
    result = asyncio.run(_run_builtin_tool("finish", {"summary": "done here"}, task_id="t1", role="qa"))
    assert "done here" in result


def test_get_assets_tool_is_honestly_not_implemented():
    with pytest.raises(ToolExecutionError, match="NOT|not implemented|no real"):
        asyncio.run(_run_builtin_tool("get_assets", {"query": "logo"}, task_id="t1", role="design"))


def test_web_search_tool_explains_it_needs_an_anthropic_model():
    # Only reached for non-Anthropic providers — AnthropicProvider intercepts "web_search" before
    # it would ever become a tool call needing this executor (see anthropic_provider.py).
    with pytest.raises(ToolExecutionError, match="Anthropic"):
        asyncio.run(_run_builtin_tool("web_search", {"query": "x"}, task_id="t1", role="planner"))


def test_unknown_builtin_tool_raises():
    with pytest.raises(ToolExecutionError, match="Unknown"):
        asyncio.run(_run_builtin_tool("not_a_real_tool", {}, task_id="t1", role="qa"))


def test_execute_tool_call_never_raises_reports_error_as_content_instead():
    # A failed tool call must become tool_result content the model can see and adapt to, not an
    # exception that crashes the whole agent step (see call_with_tools' design note).
    result = asyncio.run(_execute_tool_call(
        {"id": "call_1", "name": "get_assets", "arguments": {"query": "x"}}, {}, task_id="t1", role="design"))
    assert result["id"] == "call_1"
    assert result["content"].startswith("ERROR:")


def test_execute_tool_call_unknown_tool_name_reports_error_as_content():
    result = asyncio.run(_execute_tool_call(
        {"id": "call_2", "name": "does_not_exist", "arguments": {}}, {}, task_id="t1", role="design"))
    assert "ERROR" in result["content"]


def test_seed_roles_cover_the_six_seeded_specialists_with_unique_slugs():
    # "Integration" — the 7th Emergent-style specialist in the original ask — is already a
    # built-in implementer role (models.BUILTIN_AGENT_ROLES), so it isn't re-seeded here.
    slugs = [r["role"] for r in SEED_ROLES]
    assert len(slugs) == len(set(slugs)), "duplicate role slugs in SEED_ROLES"
    assert set(slugs) == {
        "vision", "frontend_testing", "backend_testing", "fullstack_testing",
        "troubleshoot", "deployment",
    }
    for spec in SEED_ROLES:
        assert spec["label"]
        assert spec["system_prompt"] and len(spec["system_prompt"]) > 20
        assert spec["icon"]
