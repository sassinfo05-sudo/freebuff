import { AuthProvider, useAuth } from "@/context/AuthContext";
import Login from "@/pages/Login";
import DevStudioApp from "@/pages/DevStudioApp";
import { Toaster } from "@/lib/toast";

function Gate() {
  const { authenticated, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen grid place-items-center bg-surface-0 text-white/40 text-sm">
        <div className="flex items-center gap-2 animate-fade-in">
          <div className="w-4 h-4 rounded-full border-2 border-white/20 border-t-white/60 animate-spin" />
          Loading…
        </div>
      </div>
    );
  }
  return authenticated ? <DevStudioApp /> : <Login />;
}

export default function App() {
  return (
    <AuthProvider>
      <Gate />
      <Toaster />
    </AuthProvider>
  );
}
