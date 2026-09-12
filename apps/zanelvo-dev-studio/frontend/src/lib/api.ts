import axios from "axios";

declare global {
  interface Window {
    // Injected only by the desktop (Electron) shell's static server — see
    // apps/zanelvo-dev-studio/desktop/main.js. Absent in the normal web deployment, where the
    // page and API share an origin and the relative "/api" default below is correct as-is.
    __DESKTOP_API_BASE__?: string;
  }
}

const API_BASE = window.__DESKTOP_API_BASE__ || "/api";

// Same-origin in both dev (Vite proxies /api to the backend) and prod (served behind one
// reverse proxy) — see README for the reverse-proxy setup — OR the desktop shell's injected
// absolute URL when the page and backend run on different local ports. Auth is a plain HttpOnly
// cookie, so axios just needs withCredentials; there is no token to manage in JS.
const api = axios.create({ baseURL: API_BASE, withCredentials: true });

// The origin API calls actually resolve against — window.location.origin in the normal web
// deployment (page and API share it), or the desktop shell's backend origin when they don't.
// EventSource has no baseURL concept of its own, so devstudio.eventsUrl() needs this directly.
export const API_ORIGIN = window.__DESKTOP_API_BASE__
  ? new URL(window.__DESKTOP_API_BASE__).origin
  : window.location.origin;

export default api;
