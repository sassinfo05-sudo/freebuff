import { AuthProvider, useAuth } from "@/context/AuthContext";
import Login from "@/pages/Login";
import DevStudioApp from "@/pages/DevStudioApp";
import { Toaster } from "@/lib/toast";

function Gate() {
  const { authenticated, loading } = useAuth();
  if (loading) {
    return <div className="min-h-screen grid place-items-center bg-[#0B0A16] text-white/40 text-sm">Loading…</div>;
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
