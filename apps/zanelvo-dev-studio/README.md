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
piece intentionally left unfinished (a second LLM provider).

## Running it

### Backend

```bash
cd apps/zanelvo-dev-studio/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Optional — real Anthropic-backed agents + Playwright browser QA:
pip install -r requirements-devstudio.txt
cp .env.example .env   # then fill in MONGO_URL, JWT_SECRET, ADMIN_PASSWORD at minimum
uvicorn server:app --reload --port 8000
```

Requires a running MongoDB (`MONGO_URL`). Everything else in `.env.example` is optional or can be
set later from the app's own Settings screen (GitHub PAT, Anthropic API key — encrypted at rest).

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

38 deterministic tests (state machine, anti-loop engine, command policy, file safety, diff
parsing) — no database or network required.

## What's real vs. what needs credentials

Everything is real code — nothing is mocked. Two things need external credentials before they
actually do anything, and say so clearly (never silently) when they don't have them:

- **GitHub integration** (clone/browse/commit/push/PR) needs a Personal Access Token, set via the
  Settings screen or `DEVSTUDIO_GITHUB_TOKEN`.
- **Agent LLM calls** (repository analysis, planning, implementation, review) need
  `ANTHROPIC_API_KEY` (Settings screen or env var). A task that reaches this point without a key
  configured goes to `BLOCKED` with a clear reason — it never fakes a result.

Browser QA additionally needs `pip install -r requirements-devstudio.txt` (Playwright); without
it, browser runs are recorded as `unavailable`, not silently skipped.
