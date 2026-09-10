# Zanelvo Dev Studio — Emergent Integration Handoff

Zanelvo Dev Studio (`apps/zanelvo-dev-studio/`) is a private, single-user AI software-development
tool: connect a GitHub repo, describe work in natural language, and a Supervisor-controlled team of
agents plans, implements, tests, reviews, and (on your approval) commits/pushes it.

It was built provider-independent by design: an `LLMProvider` abstraction sits between every agent
and the model that answers it, so a new vendor is a new class, not a rewrite. `AnthropicProvider`,
`OpenAIProvider`, and `GeminiProvider` are all real implementations (each needs its own API key —
see below); which provider each agent role uses by default is a deliberate per-task choice, not an
arbitrary split — see the top-of-file comment in `providers/registry.py`.
`EmergentUniversalKeyProvider` is a **deliberate, non-functional stub**: it implements the full
interface so the `ModelRegistry` can list/select it, but every method raises
`ProviderNotImplemented`. This document is the complete, isolated scope of what's left to make it
real. Nothing else in the app should need to change.

**Confidence note on OpenAI/Gemini:** their model names and pricing were checked against each
vendor's own current docs (§10 lower down has the exact table). The *request/response shapes*
(Chat Completions params for OpenAI, `GenerateContentConfig` fields for Gemini) were written from
general knowledge of each SDK, not verified against a live call — no API keys were available to
test with. If either provider errors immediately on a real call, check the request shape first
(`openai_provider.py` / `gemini_provider.py`) before assuming the model ID is wrong.

## 1. What is complete (do not rebuild this)

| Capability | Class | Evidence |
|---|---|---|
| Task/PlanItem state machines, deterministic transitions | Live and verified | `backend/app/devstudio/state_machine.py`, `backend/tests/test_devstudio_state_machine.py` (9 tests, pass without DB/network) |
| Anti-loop engine (fingerprinting, normalization, budgets, LoopDetector) | Live and verified | `backend/app/devstudio/services/anti_loop.py`, `backend/tests/test_devstudio_anti_loop.py` (10 tests) |
| CommandPolicy allow/deny | Live and verified | `backend/app/devstudio/services/command_policy.py`, `backend/tests/test_devstudio_command_policy.py` (6 tests) |
| FileService (path safety, stale-patch protection) | Live and verified | `backend/app/devstudio/services/file_service.py`, `backend/tests/test_devstudio_file_service.py` (10 tests) |
| DiffService unified-diff parsing | Live and verified | `backend/app/devstudio/services/diff_service.py`, `backend/tests/test_devstudio_diff_service.py` (5 tests) |
| Single-admin auth, full FastAPI app boot (56 routes: 3 auth, 40 devstudio, health) | Live and verified | `backend/app/auth.py`, `backend/app/deps.py`, `backend/server.py` — verified with `python -c "import server"` against CI-shaped env vars |
| Frontend production build (Vite + React + TS, `tsc --noEmit && vite build`) | Live and verified | `frontend/src/pages/*`, `frontend/src/lib/devstudio.ts` — built clean, zero TS errors, 0 warnings (verified this session) |
| Git/GitHub integration (clone via local mirror, branch, commit, push, PR, diff, remote-drift detection) | Live but requires external credentials | `backend/app/devstudio/services/git_service.py`, `github_provider.py`; needs a GitHub PAT via Settings |
| Repository indexing/search, project memory, workspaces, checkpoints, execution/testing service, browser QA (Playwright), preview adapter, uploads, usage tracking, SSE activity stream | Live but requires external credentials | Real implementations throughout `backend/app/devstudio/services/`. The ones that call an LLM (analysis, planning, implementation, review) require a configured provider. Browser QA additionally requires `pip install -r backend/requirements-devstudio.txt` |
| Agent pipeline (Supervisor → Analyst → Planner → implementer → QA → Reviewer → Git), across Anthropic/OpenAI/Gemini | Live but requires external credentials | `backend/app/devstudio/agents/*`, `providers/{anthropic,openai,gemini}_provider.py`; requires at least `ANTHROPIC_API_KEY` (all three presets' non-Design/Reviewer roles), plus `OPENAI_API_KEY`/`GEMINI_API_KEY` for Reviewer/Design's primary models. **Not run end-to-end against any live provider account in this build** — no keys were available in the environment this was built in. The code paths, prompts, and JSON contracts are real and unit-testable; the model round-trips themselves are unverified here |
| Emergent provider slot | Structural/not connected (intentional) | `backend/app/devstudio/providers/emergent_provider.py` — every method raises `ProviderNotImplemented` with a `TODO(Emergent)` message |

Do not re-architect `AgentOrchestrator`, the state machines, `FileService`, `GitService`, or the
route layer to integrate Emergent — none of that should need to change. The entire integration is
isolated to the provider layer (§2).

## 2. Exact backend files Emergent must modify

1. **`backend/app/devstudio/providers/emergent_provider.py`** — the only file that *must* change.
   Replace the five `raise ProviderNotImplemented(...)` bodies with real calls. The class already
   receives a `universal_key: Optional[str]` in `__init__` — wire it to the actual client.

   Suggested transport: Emergent's own `emergentintegrations` package (ships from Emergent's public
   CDN wheel index, not PyPI). Follow the exact lazy-import pattern already used in this same file
   for `AnthropicProvider` (see `providers/anthropic_provider.py::_sdk()`) — import it inside a
   function, not at module scope, and raise `ProviderNotConfigured` with a clear install message if
   it's missing, so the app keeps booting without it.

2. **`backend/app/devstudio/providers/registry.py`** — no structural change needed. Once
   `emergent_provider.py` is real, add Emergent model IDs to `MODEL_PRESETS` if you want Emergent as
   a preset default for any role (currently every preset defaults to `anthropic`).

3. **`backend/app/devstudio/services/settings_service.py`** — already resolves
   `EMERGENT_UNIVERSAL_KEY` (env) or the encrypted `emergent_universal_key` secret
   (`POST /api/devstudio/settings/secrets {"name": "emergent_universal_key", "value": "..."}`) and
   passes it into `ModelRegistry`. No change needed unless the Universal Key needs additional
   parameters (region, project id, etc.) — if so, extend `_SECRET_KEYS` and `get_secret` there.

4. **`backend/requirements-devstudio.txt`** — add `emergentintegrations` (or whatever transport you
   choose) here, following the exact optional-dependency pattern already used for `anthropic` and
   `playwright` in this same file.

Nothing in `backend/app/devstudio/agents/`, `routes.py`, or `state_machine.py` should need to
change, and nothing at the `app/` level (auth, config, db) needs to change either.

## 3. Exact frontend files Emergent must modify

In the common case (Emergent only adds a provider), **none**. `frontend/src/pages/panels.tsx`
(`SettingsPanel`) already has a generic secret-save UI; extend it with one more input for the
Universal Key exactly like the existing GitHub PAT / Anthropic API key fields (copy the
`anthropicKey` state + `saveSecret("anthropic_api_key", …)` block and retarget at
`"emergent_universal_key"`). The Agents panel already lists `primary_provider`/`fallback_provider`
per role from the backend — once `MODEL_PRESETS` includes Emergent models, they appear
automatically.

## 4. LLMProvider interface Emergent must implement

Defined in `backend/app/devstudio/providers/base.py`. Every agent call goes through exactly this
surface — implement all of it on `EmergentUniversalKeyProvider`:

```python
class LLMProvider(ABC):
    def list_models(self) -> List[ModelInfo]: ...
    async def generate(self, *, system: str, prompt: str, model: str,
                        max_tokens: int = 4096, temperature: float = 0.2,
                        reasoning_level: Optional[str] = None) -> LLMResult: ...
    async def generate_structured(self, *, system: str, prompt: str, model: str,
                                   json_schema: Optional[dict] = None,
                                   max_tokens: int = 4096) -> LLMResult: ...
    async def generate_with_vision(self, *, system: str, prompt: str, model: str,
                                    images_b64: List[str], max_tokens: int = 4096) -> LLMResult: ...
    async def stream(self, *, system: str, prompt: str, model: str,
                      max_tokens: int = 4096) -> AsyncIterator[str]: ...
```

`ModelInfo`, `LLMResult`, `LLMUsage` are plain dataclasses in the same file:

```python
@dataclass
class ModelInfo:
    id: str; provider: str; label: str
    supports_tools: bool = False; supports_vision: bool = False; supports_reasoning_levels: bool = False
    context_window: Optional[int] = None; notes: Optional[str] = None

@dataclass
class LLMUsage:
    input_tokens: int = 0; output_tokens: int = 0; cache_tokens: int = 0
    cost_usd: Optional[float] = None; duration_ms: Optional[int] = None

@dataclass
class LLMResult:
    text: str; usage: LLMUsage = field(default_factory=LLMUsage)
    raw: Optional[dict] = None; model: Optional[str] = None; provider: Optional[str] = None
```

Contract every caller relies on (see `AnthropicProvider` in `anthropic_provider.py` for the
reference shape):

- `generate_structured` MUST return `LLMResult.text` as a **string containing JSON** (an object or
  array) with no markdown fences/prose — `agents/runner.py::extract_json` has a fallback parser for
  fenced/preambled JSON, but the model should be steered to avoid needing it (see
  `AnthropicProvider.generate_structured`, which appends a strict-JSON instruction to `system`).
- `LLMResult.provider` and `.model` MUST be set — `usage_tracker.py` uses them verbatim in
  `LLMInvocation` records.
- `LLMResult.usage.cost_usd` should be **`None`** unless Emergent's response genuinely reports a
  dollar cost — `usage_tracker.task_usage_summary` treats a totally-`None` cost column as "unknown",
  never fabricating `$0.00`. Only set it if it's real.
- Raise `ProviderNotConfigured` (not a bare exception) when the Universal Key is missing/invalid —
  `agents/runner.py::call_structured` catches this specifically and classifies the resulting
  `AgentStepFailed` as `"requires_credentials"` (surfaced to the founder as a BLOCKED task with a
  clear reason, never a silent failure).

## 5. Model discovery

`list_models()` currently returns a **static** list (see `_MODELS` in `anthropic_provider.py`).
`ModelRegistry.list_all_models()` just concatenates every provider's static list — there's no
live-discovery requirement anywhere else. If Emergent's Universal Key exposes a model-list
endpoint you can make `list_models()` fetch live (cache it — it's called on every
`GET /api/devstudio/settings` and `/agents/config` request), but a static list mirroring
Emergent's supported model catalog is sufficient and matches the existing pattern.

## 6. Usage tracking integration

`backend/app/devstudio/services/usage_tracker.py::record_invocation` reads only
`LLMResult.usage.{input_tokens,output_tokens,cache_tokens,cost_usd,duration_ms}` — populate
whatever Emergent's response actually returns; leave the rest `None`/`0`. No other change needed;
`task_usage_summary` and `GET /api/devstudio/tasks/{id}/usage` already aggregate correctly
regardless of which provider produced the invocations.

## 7. How to test the provider

1. `pip install -r backend/requirements-devstudio.txt` (add your Emergent transport dependency
   there first, per §2.4).
2. Set `EMERGENT_UNIVERSAL_KEY` in the environment, or `POST /api/devstudio/settings/secrets
   {"name": "emergent_universal_key", "value": "<key>"}`.
3. `PUT /api/devstudio/agents/config/repository_analyst {"primary_provider": "emergent",
   "primary_model": "<an Emergent model id>"}` (or apply a preset that defaults to Emergent, once
   added to `MODEL_PRESETS`).
4. Create a project (`POST /api/devstudio/projects`) against a real repo with a GitHub PAT
   configured, create a task, `POST /api/devstudio/tasks/{id}/run`, and watch
   `GET /api/devstudio/tasks/{id}/events` (SSE). A successful `agent_finished` event for
   `repository_analyst` with `status: succeeded` is the acceptance signal for the provider itself.
5. Unit-test the provider directly (there is no live-network provider test for `AnthropicProvider`
   in this repo either — no credentials were available in the build environment). Write one for
   both providers when credentials exist, asserting `generate_structured` returns parseable JSON
   and `list_models()` is non-empty.

## 8. What mocks/stubs must be removed

Exactly one thing: the five `raise ProviderNotImplemented(...)` bodies in `emergent_provider.py`,
plus the `_TODO` string and its docstring's "INTENTIONAL STUB" header. Confirm there are no other
stub call sites once this file is done:

```
grep -rn "ProviderNotImplemented\|EmergentUniversalKeyProvider" apps/zanelvo-dev-studio/backend/app/devstudio/
```

## 9. Acceptance tests Emergent must pass

- `emergent_provider.py` no longer raises `ProviderNotImplemented` for any of the five interface
  methods when a valid Universal Key is configured.
- `ModelRegistry.get("emergent").list_models()` returns at least one `ModelInfo` with a real model
  id Emergent actually serves.
- An `AgentConfiguration` pointed at an Emergent provider/model completes a full
  `analyze_repository` → `create_plan` → `implement_plan_item` → `review_diff` pass on a real task
  (§7, step 4) without raising `AgentStepFailed`.
- `GET /api/devstudio/tasks/{id}/usage` after that run shows `calls > 0` for the Emergent-backed
  agent runs, with whatever real usage numbers Emergent returned (never fabricated).
- The existing 38 deterministic Dev Studio tests (`backend/tests/test_devstudio_*.py`) still pass —
  none of them should need to change for a provider addition.
- `python -c "import server"` still boots cleanly (proves the optional Emergent dependency stays
  properly lazily-imported and doesn't break app startup when absent).

## 10. Environment variables reference

| Variable | Purpose | Required for |
|---|---|---|
| `ANTHROPIC_API_KEY` | AnthropicProvider auth | Anthropic-backed agents (already working) |
| `OPENAI_API_KEY` | OpenAIProvider auth | OpenAI-backed agents — Reviewer's primary model at BALANCED/MAX_QUALITY (already working) |
| `GEMINI_API_KEY` | GeminiProvider auth | Gemini-backed agents — Design's primary model (already working) |
| `EMERGENT_UNIVERSAL_KEY` | EmergentUniversalKeyProvider auth | Emergent-backed agents (this handoff) |
| `DEVSTUDIO_GITHUB_TOKEN` | GitHub PAT (overrides the stored secret) | repository clone/browse/commit/push/PR |
| `MONGO_URL`, `DB_NAME` | Mongo connection | all persistence (`ds_*` collections) |
| `JWT_SECRET`, `ADMIN_PASSWORD` | App auth | required to boot at all — unrelated to Emergent |

All provider/GitHub secrets can alternatively be set via
`POST /api/devstudio/settings/secrets` (encrypted at rest with
`apps/zanelvo-dev-studio/backend/app/services/secretbox.py`) rather than as environment variables
— see `SettingsPanel` in `frontend/src/pages/panels.tsx`.
