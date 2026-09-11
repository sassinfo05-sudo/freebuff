import { useState, type FormEvent } from "react";
import { Lock, AlertCircle } from "lucide-react";
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
    <div className="min-h-screen grid place-items-center bg-surface-0 text-white relative overflow-hidden px-4">
      <div
        className="pointer-events-none absolute -top-1/3 left-1/2 -translate-x-1/2 w-[560px] h-[560px] rounded-full opacity-[0.15] blur-3xl"
        style={{ background: "radial-gradient(circle, #6366F1, #D946EF 60%, transparent 75%)" }}
      />
      <form
        onSubmit={onSubmit}
        className="relative w-full max-w-sm space-y-5 rounded-2xl border border-white/10 bg-surface-2/80 backdrop-blur-xl p-7 shadow-panel animate-fade-up"
      >
        <div className="text-center">
          <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 via-fuchsia-500 to-amber-400 shadow-glow">
            <Lock className="h-[18px] w-[18px]" strokeWidth={2} />
          </div>
          <div className="text-base font-semibold tracking-tight">Zanelvo Dev Studio</div>
          <div className="text-xs text-white/40 mt-1">Private workspace — sign in to continue</div>
        </div>
        <div>
          <Input
            type="password"
            autoFocus
            invalid={!!error}
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              if (error) setError(null);
            }}
            placeholder="Password"
            className="h-10 text-sm"
          />
          {error && (
            <div className="flex items-center gap-1.5 text-[11px] text-red-400 mt-2 animate-fade-in">
              <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
              {error}
            </div>
          )}
        </div>
        <Button type="submit" loading={busy} disabled={!password} className="w-full h-10 text-sm">
          {busy ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </div>
  );
}
