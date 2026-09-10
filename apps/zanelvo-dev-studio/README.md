# Zanelvo Dev Studio

A private, single-user AI software-development environment: connect a GitHub repository, describe
a feature or bug fix in natural language, and a Supervisor-controlled team of specialist agents
(Repository Analyst, Planner, Design, Frontend, Backend, Integration, QA, Reviewer, Git) analyzes
the repo, plans the work, edits real files in an isolated working copy, runs tests, reviews the
diff, and — once you approve — commits and pushes it back to GitHub.

It is a tool, not a product: no signup, no billing, no multi-user accounts. One admin password
gates the whole thing.

See the root [`CLAUDE.md`](../../CLAUDE.md) for this monorepo's conventions and this app's own
[`CLAUDE.md`](./CLAUDE.md) for how the code here is organized. See
[`docs/EMERGENT_INTEGRATION_HANDOFF.md`](../../docs/EMERGENT_INTEGRATION_HANDOFF.md) for the one
piece intentionally left unfinished (the Emergent provider).

## Models: three presets, not one vendor

Every agent's model is independently configurable (Settings → Agents), and three presets pick
sane defaults across **Anthropic, OpenAI, and Gemini** — not just Anthropic everywhere:

| Preset | Supervisor/Analyst/Planner/Frontend | Backend/Integration | Design | Reviewer |
|---|---|---|---|---|
| ECONOMICAL | Claude Haiku 4.5 | Claude Haiku 4.5 | Gemini 3.1 Flash-Lite | Claude Haiku 4.5 |
| BALANCED | Claude Sonnet 5 | Claude Sonnet 5 | Gemini 3.1 Pro Preview | GPT-5.6 Terra |
| MAX_QUALITY | Claude Fable 5.1 | Claude Opus 5 | Gemini 3.1 Pro Preview | GPT-6 Astra |

Coding-heavy roles stay on Claude across every tier — it has the most consistently-reported edge
on agentic coding benchmarks, so anything else there would be diversity for its own sake. At
MAX_QUALITY, Claude itself splits by role: **Supervisor/Analyst/Planner/Frontend** use Fable 5.1,
Anthropic's newest flagship for long-running agentic work, which beats Opus 5 on most benchmarks
but has lower single-shot accuracy and safety guardrails that can block on security-adjacent code.
**Backend/Integration** stay on Opus 5 instead, since those roles routinely write auth/crypto/
permission code where a Fable safety block is a real risk and Opus's higher pass@1 matters more
than Fable's efficiency. Two roles diverge from Anthropic entirely: **Design** uses Gemini for its
multimodal/large-context strength (screenshots, reference images), and **Reviewer** uses OpenAI as
an independent second opinion from a different lab than the implementer (with Claude as its
fallback). See the comment at the top of `app/devstudio/providers/registry.py` for the full
reasoning.

## Credentials: native keys, Amazon Bedrock, or Emergent

Every role's provider/model is independently overridable from Settings → Agents — including its
*fallback* provider/model, not just its primary — regardless of which preset is applied. Three
credential paths are available, side by side, from Settings → Secrets:

- **Native per-vendor API keys** — Anthropic, OpenAI, Gemini. One key each; this is what the three
  presets use by default.
- **Amazon Bedrock** — the same Claude models, routed through AWS instead of api.anthropic.com
  (data residency, existing AWS billing, Bedrock provisioned throughput, VPC-only egress). Needs
  an `aws_region`; the access key/secret pair is optional — leave it blank to use boto3's own
  default AWS credential chain (env vars, `~/.aws/credentials`, an EC2/ECS/Lambda IAM role).
- **Emergent Universal Key** — intentional stub, see
  [`docs/EMERGENT_INTEGRATION_HANDOFF.md`](../../docs/EMERGENT_INTEGRATION_HANDOFF.md).

None of the three presets route through Bedrock or Emergent by default — pick a role in Settings →
Agents and set its provider explicitly to opt in, without changing what everyone else uses. See
`app/devstudio/providers/bedrock_provider.py` for exactly how Bedrock credentials resolve and why
its model IDs need confirming against the Bedrock console before production use.

## Running it

### Backend

```bash
cd apps/zanelvo-dev-studio/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Optional — real Anthropic/OpenAI/Gemini-backed agents + Playwright browser QA:
pip install -r requirements-devstudio.txt
cp .env.example .env   # then fill in MONGO_URL, JWT_SECRET, ADMIN_PASSWORD at minimum
uvicorn server:app --reload --port 8000
```

Requires a running MongoDB (`MONGO_URL`). Everything else in `.env.example` is optional or can be
set later from the app's own Settings screen (GitHub PAT, provider API keys — encrypted at rest).

### Frontend

```bash
cd apps/zanelvo-dev-studio/frontend
yarn install
yarn dev   # http://localhost:5173, proxies /api to the backend on :8000
```

### Tests

```bash
cd apps/zanelvo-dev-studio/backend
pip install pytest pytest-xdist
python -m pytest tests/ -q
```

53 deterministic tests (state machine, anti-loop engine, command policy, execution/testing-service
cwd safety, file safety, diff parsing, provider registry) — no database or network required.

## What's real vs. what needs credentials

Everything is real code — nothing is mocked. Two things need external credentials before they
actually do anything, and say so clearly (never silently) when they don't have them:

- **GitHub integration** (clone/browse/commit/push/PR) needs a Personal Access Token, set via the
  Settings screen or `DEVSTUDIO_GITHUB_TOKEN`.
- **Agent LLM calls** (repository analysis, planning, implementation, review) need at least
  `ANTHROPIC_API_KEY` configured (Settings screen or env var) — `OPENAI_API_KEY` and
  `GEMINI_API_KEY` are only needed if you want the Reviewer/Design roles' primary models rather
  than their Claude fallback. A task that reaches an unconfigured provider goes to `BLOCKED` with
  a clear reason — it never fakes a result. Amazon Bedrock (`aws_region` + optionally an AWS key
  pair) and the Emergent Universal Key are additional opt-in credential paths — see "Credentials"
  above — not required unless a role is explicitly pointed at them.

Browser QA additionally needs `pip install -r requirements-devstudio.txt` (Playwright); without
it, browser runs are recorded as `unavailable`, not silently skipped.
