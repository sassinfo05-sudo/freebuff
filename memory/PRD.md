# Zanelvo Dev Studio — PRD / Working Notes

Private, single-user AI software-development environment (monorepo `apps/zanelvo-dev-studio`).
FastAPI backend (port 8001) + Vite/React frontend (port 3000) + MongoDB. One admin password gates
the whole app (`ADMIN_PASSWORD`). See `apps/zanelvo-dev-studio/CLAUDE.md` for architecture.

## Setup done (this workspace)
- Created `backend/.env` (JWT_SECRET, ADMIN_PASSWORD, SECRETS_ENC_KEY, Mongo, CORS) with the
  Emergent Universal Key as `EMERGENT_UNIVERSAL_KEY`.
- Installed provider deps: `requirements-devstudio.txt` then `requirements-emergent.txt`
  (emergentintegrations; openai pinned to 1.99.9 per the app's documented tradeoff).
- Admin password recorded in `memory/test_credentials.md`.

## Agent / provider model changes (2026-06)
Requirement: all MCP servers + tools auto-enabled for every agent; auto-fallback to whatever key
is available with **Emergent always the main provider**; ECONOMICAL/BALANCED/MAX_QUALITY buttons
must NOT change the provider; presets redone to use best cross-family models (not only Claude).

- `providers/registry.py`: `MODEL_PRESETS` rewritten — every entry routes through provider
  `emergent` (the Universal Key serves GPT/Claude/Gemini). Models are cross-family per role:
  Gemini → design/vision/repository_analyst; GPT → planner/qa/reviewer; Claude →
  supervisor/frontend/backend/integration. `_AUTO_FALLBACK_ORDER` now emergent-first;
  `auto_attempts(config, registry)` always tries Emergent (with the role's curated model) first,
  then any other configured provider.
- `agents/registry.py`: `_default_config` now defaults `auto_provider=True`, `tools_enabled`=all
  built-in tools, `mcp_servers`=all enabled servers. `apply_preset` only changes the model
  (provider stays emergent), keeps auto-provider + all tools + all MCP servers on.
  `add_mcp_server_to_all()` propagates newly added servers to every agent.
- `services/mcp_service.py`: `seed_memory_server()` seeds the credential-free memory server.
- `server.py` startup: seeds custom roles + memory MCP server + agent defaults.
- `routes.py`: creating an MCP server enables it on all agents.
- Frontend `pages/panels.tsx`: Agents panel copy updated (presets change model, not provider).

Verified: login + `POST /agents/preset/{ECONOMICAL|BALANCED|MAX_QUALITY}` all keep provider
`emergent` for 16/16 roles; models change per tier; each role shows 13 tools (memory + 12).

## Backlog / next
- P2: optional migration if a founder had customized agent configs (this run reset defaults).
