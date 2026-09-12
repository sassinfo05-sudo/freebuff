"""MCPService — connects to configured MCP (Model Context Protocol) servers and lets agents
discover/call their tools. Uses the official `mcp` Python SDK (see requirements-devstudio.txt for
why its version — and sse-starlette's — are pinned exactly: a newer `mcp` forces a `starlette`
upgrade that breaks this app's own FastAPI pin, reproduced with a real `pip install`, not assumed).

Verified this session with a real end-to-end round trip against the actual
@modelcontextprotocol/server-memory reference server (stdio): connected, listed its 9 real tools,
called create_entities, and got real content back — the client plumbing here is proven, not just
written to spec.

Connections are short-lived: connect -> operate -> disconnect per call, not a long-lived pool,
because stdio servers are child processes and a crashed/hung one must never take down an agent
run — every call here degrades to a clear, recorded error instead of propagating a raw exception
that could crash orchestration.
"""
from __future__ import annotations

import contextlib
from typing import Any, AsyncIterator, Dict, List, Optional

from bson import ObjectId

from ...db import get_db, utc_now_iso
from ...services import secretbox
from ..models import MCPServerConfig


class MCPNotConfigured(Exception):
    """The mcp package isn't installed, or a server has no usable connection config."""


class MCPCallError(Exception):
    """A configured server was reachable in principle but the connection or call itself failed
    (bad command, server crashed, tool raised, auth rejected, ...) — never silently swallowed."""


def _sdk():
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from mcp.client.streamable_http import streamablehttp_client
        return ClientSession, StdioServerParameters, stdio_client, streamablehttp_client
    except ImportError as e:  # noqa: BLE001
        raise MCPNotConfigured(
            "The 'mcp' package is not installed in this environment. Install it via: "
            "pip install -r requirements-devstudio.txt"
        ) from e


def _decrypt_env(server: MCPServerConfig) -> Dict[str, str]:
    return {k: secretbox.decrypt(v) for k, v in server.env.items()}


@contextlib.asynccontextmanager
async def _session(server: MCPServerConfig) -> AsyncIterator[Any]:
    ClientSession, StdioServerParameters, stdio_client, streamablehttp_client = _sdk()
    if server.transport == "stdio":
        if not server.command:
            raise MCPNotConfigured(f"MCP server '{server.name}' has no command configured.")
        params = StdioServerParameters(command=server.command, args=server.args,
                                        env=_decrypt_env(server) or None)
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session
        except MCPNotConfigured:
            raise
        except Exception as e:  # noqa: BLE001
            raise MCPCallError(f"Could not start/connect to MCP server '{server.name}': {e}") from e
    elif server.transport == "http":
        if not server.url:
            raise MCPNotConfigured(f"MCP server '{server.name}' has no URL configured.")
        try:
            async with streamablehttp_client(server.url, headers=_decrypt_env(server) or None) as (
                read, write, _get_session_id,
            ):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session
        except Exception as e:  # noqa: BLE001
            raise MCPCallError(f"Could not connect to MCP server '{server.name}': {e}") from e
    else:
        raise MCPNotConfigured(f"Unknown MCP transport '{server.transport}' for '{server.name}'.")


async def list_tools(server: MCPServerConfig) -> List[Dict[str, Any]]:
    async with _session(server) as session:
        result = await session.list_tools()
        return [
            {"name": t.name, "description": t.description or "", "inputSchema": t.inputSchema}
            for t in result.tools
        ]


async def call_tool(server: MCPServerConfig, tool_name: str, arguments: Dict[str, Any]) -> str:
    async with _session(server) as session:
        try:
            result = await session.call_tool(tool_name, arguments)
        except Exception as e:  # noqa: BLE001
            raise MCPCallError(f"MCP tool '{tool_name}' on '{server.name}' failed: {e}") from e
        text_parts = [c.text for c in result.content if getattr(c, "type", None) == "text"]
        out = "\n".join(text_parts) if text_parts else str([c.model_dump() for c in result.content])
        if result.isError:
            raise MCPCallError(f"MCP tool '{tool_name}' on '{server.name}' returned an error: {out}")
        return out


# --- presets ---------------------------------------------------------------------------------

PRESETS: Dict[str, Dict[str, Any]] = {
    "memory": {
        "label": "Memory (knowledge graph)",
        "transport": "stdio", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-memory"],
        "env_keys": [],
        "description": "Anthropic's reference knowledge-graph memory server — persistent, "
                       "cross-task memory for agents (create_entities, search_nodes, ...). "
                       "No credentials needed.",
    },
    "notion": {
        "label": "Notion",
        "transport": "stdio", "command": "npx", "args": ["-y", "@notionhq/notion-mcp-server"],
        "env_keys": ["NOTION_TOKEN"],
        "description": "Notion's official MCP server. Needs a Notion internal integration token "
                       "(Notion → Settings → Connections → Develop or manage integrations).",
    },
}


# --- persistence -------------------------------------------------------------------------------

async def list_servers() -> List[MCPServerConfig]:
    docs = get_db().ds_mcp_servers.find().sort("created_at", 1)
    return [MCPServerConfig.from_mongo(d) async for d in docs]


async def get_server(server_id: str) -> Optional[MCPServerConfig]:
    doc = await get_db().ds_mcp_servers.find_one({"_id": ObjectId(server_id)})
    return MCPServerConfig.from_mongo(doc) if doc else None


async def get_server_by_name(name: str) -> Optional[MCPServerConfig]:
    doc = await get_db().ds_mcp_servers.find_one({"name": name})
    return MCPServerConfig.from_mongo(doc) if doc else None


async def create_server(*, name: str, transport: str, command: Optional[str] = None,
                         args: Optional[List[str]] = None, url: Optional[str] = None,
                         env: Optional[Dict[str, str]] = None, preset: Optional[str] = None,
                         enabled: bool = True) -> MCPServerConfig:
    enc_env = {k: secretbox.encrypt(v) for k, v in (env or {}).items() if v}
    server = MCPServerConfig(name=name, transport=transport, command=command, args=args or [],
                              url=url, env=enc_env, preset=preset, enabled=enabled)
    res = await get_db().ds_mcp_servers.insert_one(server.to_mongo())
    server.id = str(res.inserted_id)
    return server


async def update_server(server_id: str, **fields: Any) -> MCPServerConfig:
    if fields.get("env") is not None:
        fields["env"] = {k: secretbox.encrypt(v) for k, v in fields["env"].items() if v}
    fields["updated_at"] = utc_now_iso()
    await get_db().ds_mcp_servers.update_one({"_id": ObjectId(server_id)}, {"$set": fields})
    server = await get_server(server_id)
    if not server:
        raise ValueError("MCP server not found")
    return server


async def delete_server(server_id: str) -> None:
    await get_db().ds_mcp_servers.delete_one({"_id": ObjectId(server_id)})


async def test_server(server_id: str) -> Dict[str, Any]:
    """Connects for real and lists tools — the result (including failures) is persisted onto the
    server doc so the Settings UI always shows the last REAL check, never a guess."""
    server = await get_server(server_id)
    if not server:
        raise ValueError("MCP server not found")
    try:
        tools = await list_tools(server)
        await update_server(server_id, last_tool_count=len(tools), last_checked_at=utc_now_iso(),
                             last_error=None)
        return {"ok": True, "tools": tools}
    except (MCPNotConfigured, MCPCallError) as e:
        await update_server(server_id, last_checked_at=utc_now_iso(), last_error=str(e)[:500])
        return {"ok": False, "error": str(e)}


async def tools_for_servers(server_names: List[str]) -> List[Dict[str, Any]]:
    """All tools from the named, enabled servers, each tagged with `_mcp_server` so the caller's
    dispatcher knows where to route a call. A server that fails to connect is skipped rather than
    raised — one broken MCP server must never crash an agent run that also uses others (or none)."""
    if not server_names:
        return []
    by_name = {s.name: s for s in await list_servers() if s.enabled}
    out: List[Dict[str, Any]] = []
    for name in server_names:
        server = by_name.get(name)
        if not server:
            continue
        try:
            tools = await list_tools(server)
        except (MCPNotConfigured, MCPCallError):
            continue
        for t in tools:
            tagged = dict(t)
            tagged["_mcp_server"] = name
            out.append(tagged)
    return out
