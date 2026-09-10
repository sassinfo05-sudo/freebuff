import axios from "axios";

// Same-origin in both dev (Vite proxies /api to the backend) and prod (served behind one
// reverse proxy) — see README for the reverse-proxy setup. Auth is a plain HttpOnly cookie, so
// axios just needs withCredentials; there is no token to manage in JS.
const api = axios.create({ baseURL: "/api", withCredentials: true });

export default api;
