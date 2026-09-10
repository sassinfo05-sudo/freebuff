# freebuff

A personal monorepo: a home for new apps and sites as they come up, rather than one repo per idea.

## Layout

```
apps/
  <app-name>/     # one self-contained project per folder
```

Each app under `apps/` is independent — its own stack, its own dependencies, its own README. Add
a new one by creating `apps/<name>/` and describing what it is in `apps/<name>/README.md`. Nothing
at the repo root assumes any particular language or framework.

See `CLAUDE.md` for working conventions in this repo.
Verified by a live Dev Studio smoke test.
