"use strict";
/**
 * Zanelvo Dev Studio desktop shell.
 *
 * Wraps the existing FastAPI backend + React frontend in an Electron window — no rewrite of
 * either. On launch this process:
 *   1. starts a real, persistent local MongoDB (mongodb-memory-server: a genuine mongod binary,
 *      not a mock — data lives under the OS user-data dir and survives restarts),
 *   2. spawns the FastAPI backend (`python -m uvicorn server:app`) against it, generating and
 *      persisting a JWT secret + admin password on first run,
 *   3. serves the already-built frontend (apps/zanelvo-dev-studio/frontend/dist) from a small
 *      local static server, injecting the backend's chosen port so the page can reach it,
 *   4. opens a window once the backend's /api/health check passes.
 *
 * Requires Python 3.11+ on PATH (see README.md) — this shell does not bundle a Python runtime.
 * If it's missing, or the backend's own dependencies aren't installed, the window shows a plain
 * error/instructions screen instead of a silent failure.
 */
const { app, BrowserWindow, shell } = require("electron");
const { spawn, spawnSync } = require("child_process");
const crypto = require("crypto");
const fs = require("fs");
const http = require("http");
const net = require("net");
const path = require("path");

const STATE = { backend: null, mongo: null, backendPort: null, staticPort: null, window: null };

function resourceDir(name) {
  // Dev: `electron .` run from this folder — sibling ../frontend/dist and ../backend.
  // Packaged: electron-builder copied them into resourcesPath via `extraResources` (package.json).
  return app.isPackaged
    ? path.join(process.resourcesPath, name)
    : path.join(__dirname, "..", name === "backend" ? "backend" : "frontend/dist");
}

function getFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

function loadOrCreateSecrets() {
  const file = path.join(app.getPath("userData"), "secrets.json");
  if (fs.existsSync(file)) {
    try {
      return JSON.parse(fs.readFileSync(file, "utf8"));
    } catch {
      // fall through to regenerate — a corrupt file must not brick the app
    }
  }
  const secrets = {
    jwtSecret: crypto.randomBytes(32).toString("hex"),
    adminPassword: crypto.randomBytes(12).toString("base64url"),
  };
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(secrets, null, 2), { mode: 0o600 });
  return secrets;
}

function findPython() {
  for (const cmd of ["python3", "python"]) {
    const r = spawnSync(cmd, ["--version"]);
    if (r.status === 0) return cmd;
  }
  return null;
}

/** Best-effort dependency install — makes first launch work without a manual `pip install` step
 * when pip has network access; a no-op (fast) on every later launch once packages are present. */
function ensureBackendDeps(pythonCmd, backendDir, onLog) {
  const reqs = ["requirements.txt", "requirements-devstudio.txt"].filter((f) =>
    fs.existsSync(path.join(backendDir, f)),
  );
  if (!reqs.length) return { ok: true };
  const args = ["-m", "pip", "install", "--disable-pip-version-check", "-q"];
  for (const f of reqs) args.push("-r", f);
  const r = spawnSync(pythonCmd, args, { cwd: backendDir, encoding: "utf8" });
  onLog?.(r.stdout, r.stderr);
  return { ok: r.status === 0, stderr: r.stderr };
}

async function waitForHealth(port, timeoutMs = 60000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const ok = await new Promise((resolve) => {
      const req = http.get({ host: "127.0.0.1", port, path: "/api/health", timeout: 1500 }, (res) => {
        res.resume();
        resolve(res.statusCode === 200);
      });
      req.on("error", () => resolve(false));
      req.on("timeout", () => { req.destroy(); resolve(false); });
    });
    if (ok) return true;
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

const MIME = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css",
  ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png",
  ".woff2": "font/woff2", ".ico": "image/x-icon" };

/** Tiny static file server for the pre-built frontend — same-origin for the app, with the
 * backend's actual port injected into index.html so the page can reach it on a different port. */
function startStaticServer(frontendDir, backendPort) {
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      let reqPath = decodeURIComponent(req.url.split("?")[0]);
      if (reqPath === "/") reqPath = "/index.html";
      let filePath = path.join(frontendDir, reqPath);
      if (!filePath.startsWith(frontendDir)) { res.writeHead(403); res.end(); return; } // no traversal
      if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
        filePath = path.join(frontendDir, "index.html"); // SPA fallback
      }
      const ext = path.extname(filePath);
      if (filePath.endsWith("index.html")) {
        let html = fs.readFileSync(filePath, "utf8");
        const inject = `<script>window.__DESKTOP_API_BASE__=${JSON.stringify(`http://127.0.0.1:${backendPort}/api`)};</script>`;
        html = html.includes("</head>") ? html.replace("</head>", `${inject}</head>`) : inject + html;
        res.writeHead(200, { "Content-Type": "text/html" });
        res.end(html);
        return;
      }
      fs.readFile(filePath, (err, data) => {
        if (err) { res.writeHead(404); res.end(); return; }
        res.writeHead(200, { "Content-Type": MIME[ext] || "application/octet-stream" });
        res.end(data);
      });
    });
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

function killTree(child) {
  if (!child || child.killed) return;
  try {
    if (process.platform === "win32") spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"]);
    else child.kill("SIGTERM");
  } catch { /* best effort — the OS reclaims an orphaned child on app exit regardless */ }
}

/** The whole non-UI startup sequence, isolated from BrowserWindow so it can be exercised (and
 * was, for this change) by a plain Node script without a display — see desktop/test-startup.js. */
async function startBackendStack(onStatus = () => {}) {
  onStatus("Starting local database…");
  const { MongoMemoryServer } = require("mongodb-memory-server");
  const dbPath = path.join(app.getPath("userData"), "mongodb-data");
  fs.mkdirSync(dbPath, { recursive: true });
  const mongo = await MongoMemoryServer.create({ instance: { dbPath, storageEngine: "wiredTiger" } });
  STATE.mongo = mongo;

  onStatus("Checking Python…");
  const pythonCmd = findPython();
  if (!pythonCmd) {
    throw new Error(
      "Python 3.11+ was not found on PATH. Zanelvo Dev Studio's backend runs on Python — " +
      "install it from python.org (check \"Add to PATH\" during install) and relaunch."
    );
  }

  const backendDir = resourceDir("backend");
  onStatus("Installing backend dependencies (first launch only)…");
  const deps = ensureBackendDeps(pythonCmd, backendDir);
  if (!deps.ok) {
    throw new Error(
      "Could not install the backend's Python dependencies automatically:\n\n" +
      `${(deps.stderr || "").slice(-800)}\n\n` +
      `Try running manually: ${pythonCmd} -m pip install -r requirements.txt -r requirements-devstudio.txt\n` +
      `(from ${backendDir})`
    );
  }

  // Backend port and static-server port are both determined before either process starts: the
  // backend's CORS_ORIGINS needs the static server's real (OS-assigned) port, and the static
  // server's index.html injection needs the backend's port — starting them in the wrong order
  // (or re-probing a "placeholder" port that a second listen() call might not actually get) was
  // an earlier bug here; this ordering removes that race entirely.
  const backendPort = await getFreePort();
  onStatus("Starting local web server…");
  const frontendDir = resourceDir("frontend");
  const staticServer = await startStaticServer(frontendDir, backendPort);
  const staticPort = staticServer.address().port;
  STATE.staticPort = staticPort;
  STATE.backendPort = backendPort;

  onStatus("Starting backend…");
  const secrets = loadOrCreateSecrets();
  const env = {
    ...process.env,
    MONGO_URL: mongo.getUri(),
    DB_NAME: "zanelvo_devstudio_desktop",
    JWT_SECRET: secrets.jwtSecret,
    ADMIN_PASSWORD: secrets.adminPassword,
    CORS_ORIGINS: `http://127.0.0.1:${staticPort}`,
  };
  const backend = spawn(pythonCmd, ["-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", String(backendPort)],
    { cwd: backendDir, env });
  STATE.backend = backend;
  backend.stdout?.on("data", (d) => onStatus(undefined, d.toString()));
  backend.stderr?.on("data", (d) => onStatus(undefined, d.toString()));

  onStatus("Waiting for backend to become ready…");
  const healthy = await waitForHealth(backendPort);
  if (!healthy) {
    throw new Error(
      "The backend did not become ready in time. Check the logs in the app's log window for the " +
      "actual Python error (missing dependency, port conflict, etc.)."
    );
  }

  return { staticPort, backendPort };
}

async function cleanup() {
  killTree(STATE.backend);
  if (STATE.mongo) await STATE.mongo.stop().catch(() => {});
}

async function createWindow() {
  const win = new BrowserWindow({
    width: 1440,
    height: 900,
    title: "Zanelvo Dev Studio",
    webPreferences: { preload: path.join(__dirname, "preload.js"), contextIsolation: true, nodeIntegration: false },
  });
  STATE.window = win;
  win.webContents.setWindowOpenHandler(({ url }) => { shell.openExternal(url); return { action: "deny" }; });

  try {
    const { staticPort } = await startBackendStack((status, log) => {
      if (status) win.webContents.send?.("startup-status", status);
      if (log) console.log(log);
    });
    await win.loadURL(`http://127.0.0.1:${staticPort}/`);
  } catch (err) {
    const escaped = String(err.message || err).replace(/&/g, "&amp;").replace(/</g, "&lt;");
    await win.loadURL(
      "data:text/html," + encodeURIComponent(
        `<body style="font:14px system-ui;padding:32px;white-space:pre-wrap;background:#0B0A16;color:#fff">` +
        `<h2>Zanelvo Dev Studio couldn't start</h2><pre>${escaped}</pre></body>`
      )
    );
  }
}

app.whenReady().then(createWindow);
app.on("window-all-closed", async () => { await cleanup(); if (process.platform !== "darwin") app.quit(); });
app.on("before-quit", cleanup);
app.on("activate", () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });

// Belt-and-suspenders against an orphaned backend/mongod: `before-quit`/`window-all-closed` cover
// a normal quit, but killTree() is synchronous (safe to call from a signal handler) so it also
// runs here for the case those Electron events don't fire — e.g. the OS sending SIGTERM/SIGINT
// directly to this process (killed externally, not via a window close) rather than app.quit().
process.on("SIGINT", () => { killTree(STATE.backend); process.exit(0); });
process.on("SIGTERM", () => { killTree(STATE.backend); process.exit(0); });

module.exports = { startBackendStack, cleanup, resourceDir, getFreePort };
