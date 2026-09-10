import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import api from "@/lib/api";

interface AuthState {
  authenticated: boolean | null; // null = not yet checked
  loading: boolean;
  login: (password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);

  async function check() {
    try {
      await api.get("/auth/me");
      setAuthenticated(true);
    } catch {
      setAuthenticated(false);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    check();
  }, []);

  async function login(password: string) {
    await api.post("/auth/login", { password });
    setAuthenticated(true);
  }

  async function logout() {
    await api.post("/auth/logout");
    setAuthenticated(false);
  }

  return (
    <AuthContext.Provider value={{ authenticated, loading, login, logout }}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
