# CLAUDE.md

## What this repo is

A personal multi-project monorepo. It is not one product — it's a place for whatever gets built
next. Each project lives in its own folder under `apps/` and is self-contained: its own stack,
dependencies, config, and README. Don't assume shared tooling, a shared framework, or a shared
brand across apps unless a root-level doc says otherwise.

## Starting a new app

1. Create `apps/<name>/` (pick a short, lowercase, hyphenated name).
2. Set it up with whatever stack fits the app — no house stack is imposed here.
3. Add `apps/<name>/README.md` describing what it is and how to run it.
4. If the app has its own non-obvious conventions, put them in `apps/<name>/CLAUDE.md` rather than
   growing this root file — keep this file about the monorepo as a whole.

## Working rules

- Never commit secrets, API keys, or credentials. Use `.env` files (gitignored) and document the
  required variable names in each app's README instead of hardcoding them.
- Keep each app's dependencies scoped to its own folder (its own `package.json`,
  `requirements.txt`, etc.) — don't create a shared root dependency file unless multiple apps
  genuinely share code, and if that happens, prefer an explicit `packages/` shared-code folder over
  implicit coupling.
- Prefer editing an existing app over restructuring the monorepo layout.
- When in doubt about scope (which app a change belongs in, whether something is shared), ask
  rather than guessing.
