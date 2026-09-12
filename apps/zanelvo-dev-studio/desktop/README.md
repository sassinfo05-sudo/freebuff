# Zanelvo Dev Studio — Desktop

Packages the existing Dev Studio (FastAPI backend + React frontend, unchanged) as a Windows
desktop app via Electron, instead of a browser tab. No rewrite: this is a shell around the same
`apps/zanelvo-dev-studio/backend` and `apps/zanelvo-dev-studio/frontend` this repo already has.

## What it does on launch

1. Starts a real, persistent local MongoDB (`mongodb-memory-server` — a genuine `mongod` binary,
   not a mock; data lives under the OS user-data dir, e.g.
   `%APPDATA%\Zanelvo Dev Studio\mongodb-data` on Windows, and survives restarts). On the very
   first launch this downloads a ~70MB `mongod` binary and caches it — needs real internet access
   once; a slow or restrictive network can make first launch take a while (seen directly while
   verifying this: the same download that took seconds earlier stalled on a later run in this
   container's own sandboxed network — worth knowing if a launch looks stuck on "Starting local
   database…" longer than expected).
2. Spawns the FastAPI backend (`python -m uvicorn server:app`) against it. A JWT secret and admin
   password are generated once on first launch and persisted alongside the Mongo data — you don't
   set anything up by hand.
3. Serves the pre-built frontend from a small local static server and injects the backend's
   (dynamically chosen) port into the page, so the existing frontend code needs no separate
   "desktop mode" — see `frontend/src/lib/api.ts`'s `window.__DESKTOP_API_BASE__`.
4. Opens the window once `/api/health` reports healthy.

## Requirement: Python 3.11+ on PATH

This shell does **not** bundle a Python runtime — building one from a Linux CI machine and
actually proving it works is a real cross-compilation project of its own (native extensions like
`pydantic-core`, `motor`/`pymongo`, `cryptography` all need genuine win_amd64 wheels), and shipping
that unverified would violate this repo's own evidence rules. **v1 requires the user to have
Python 3.11+ installed** (from python.org, with "Add to PATH" checked). On first launch the app
best-effort runs `pip install -r requirements.txt -r requirements-devstudio.txt` for you; if that's
already satisfied it's fast, and if it fails you get the actual `pip` error instead of a silent
freeze. A future v2 could bundle Python via the official Windows embeddable distribution — flagging
that as the natural next step, not attempting it here without a Windows machine to verify on.

`requirements-emergent.txt` (the Emergent provider's optional dependency) is intentionally **not**
auto-installed — it's large and most users won't have an Emergent Universal Key. Install it
manually in the bundled `backend/` folder if you want that provider.

## Building

```
cd apps/zanelvo-dev-studio/frontend && yarn build   # produces frontend/dist, bundled as a resource
cd ../desktop
npm install
npm run dist:win     # Windows: NSIS installer + portable .exe, in dist/
npm run dist:linux   # Linux: AppImage, in dist/ — useful for testing the packaging pipeline itself
```

Cross-building the Windows target from Linux needs `wine` (electron-builder uses it to embed the
`.exe`'s version metadata) — `apt-get install wine wine32:i386` (needs i386 multiarch:
`dpkg --add-architecture i386` first). Building on an actual Windows or macOS machine needs none of
that; `npm run dist:win` there is enough.

**Verified in this repo's dev environment:** `npm run dist:win` produces both `Zanelvo Dev Studio
Setup 0.1.0.exe` (NSIS installer) and `Zanelvo Dev Studio 0.1.0.exe` (portable) — `file` confirms
both are genuine `PE32 executable (GUI) Intel 80386, for MS Windows, Nullsoft Installer
self-extracting archive`, i.e. real, correctly-formed Windows installers, not placeholder files.
The Linux AppImage build boots the real app end-to-end under Xvfb — Mongo starts, the backend
becomes healthy, the window loads the built frontend, and the frontend's login screen correctly
calls the backend through the injected local port (`GET /api/health` → 200, `GET /api/auth/me` →
401 as expected with no session yet). **Not verified:** actually running either produced `.exe` on
a real Windows machine, or an install/uninstall cycle — this container is Linux, so that last step
needs you to try it and report back.

## Uninstalling / resetting

Delete the app's user-data directory (Windows: `%APPDATA%\Zanelvo Dev Studio\`) to wipe the local
database and generated secrets and start fresh — the installer/portable exe itself doesn't manage
that data, so a normal uninstall won't touch it (a deliberate choice: don't destroy the founder's
task history on an accidental uninstall/reinstall).

## Known limitations (v1)

- No auto-update (`"publish": null` — this app isn't hosted anywhere with a release feed yet).
- No custom app icon yet (`build/` is empty — drop an `icon.ico` there and reference it in
  `package.json`'s `build.win.icon` when you have one; electron-builder's default is used for now).
- A force-killed (not gracefully closed) app can leave the spawned Python backend process
  running — `main.js` handles `SIGTERM`/`SIGINT` and Electron's normal quit events, but not every
  way a process can be killed. Rare in practice; Task Manager is the fallback.
