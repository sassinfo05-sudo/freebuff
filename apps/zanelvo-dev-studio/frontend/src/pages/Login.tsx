import { useState, type FormEvent } from "react";
import { Lock } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

export default function Login() {
  const { login } = useAuth();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(password);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Sign in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen grid place-items-center bg-[#0B0A16] text-white">
      <form onSubmit={onSubmit} className="w-80 space-y-4 rounded-xl border border-white/10 bg-white/5 p-6">
        <div className="text-center">
          <div className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 via-fuchsia-500 to-amber-400">
            <Lock className="h-4 w-4" />
          </div>
          <div className="text-sm font-medium">Zanelvo Dev Studio</div>
          <div className="text-[11px] text-white/40">Private — sign in to continue</div>
        </div>
        <Input
          type="password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
        />
        {error && <div className="text-[11px] text-red-400">{error}</div>}
        <Button type="submit" disabled={busy || !password} className="w-full">
          {busy ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </div>
  );
}
