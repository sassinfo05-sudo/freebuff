"use strict";
// Intentionally minimal: the renderer is the existing web frontend, which talks to the backend
// over plain HTTP (see main.js's injected window.__DESKTOP_API_BASE__) and needs no Node/Electron
// APIs exposed to it. Kept as a real preload (contextIsolation: true, nodeIntegration: false in
// main.js) rather than omitted, so a future feature needing a safe main<->renderer bridge
// (contextBridge.exposeInMainWorld) has a place to add it without touching the security model.
