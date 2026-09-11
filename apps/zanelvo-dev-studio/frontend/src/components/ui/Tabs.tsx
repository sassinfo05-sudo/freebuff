import { createContext, useContext, useState, type ReactNode } from "react";

interface TabsCtx {
  value: string;
  setValue: (v: string) => void;
}
const Ctx = createContext<TabsCtx | null>(null);

export function Tabs({
  defaultValue,
  className = "",
  children,
}: {
  defaultValue: string;
  className?: string;
  children: ReactNode;
}) {
  const [value, setValue] = useState(defaultValue);
  return (
    <Ctx.Provider value={{ value, setValue }}>
      <div className={className}>{children}</div>
    </Ctx.Provider>
  );
}

export function TabsList({ className = "", children }: { className?: string; children: ReactNode }) {
  return <div className={`flex gap-0.5 rounded-lg bg-white/[0.04] border border-white/[0.06] p-0.5 ${className}`}>{children}</div>;
}

export function TabsTrigger({ value, children }: { value: string; children: ReactNode }) {
  const ctx = useContext(Ctx)!;
  const active = ctx.value === value;
  return (
    <button
      onClick={() => ctx.setValue(value)}
      className={`flex-1 rounded-md px-2 py-1 text-[11px] capitalize transition-colors duration-150 ${
        active ? "bg-white/[0.12] text-white shadow-soft" : "text-white/45 hover:text-white/75"
      }`}
    >
      {children}
    </button>
  );
}

export function TabsContent({
  value,
  className = "",
  children,
}: {
  value: string;
  className?: string;
  children: ReactNode;
}) {
  const ctx = useContext(Ctx)!;
  if (ctx.value !== value) return null;
  return <div className={`animate-fade-in ${className}`}>{children}</div>;
}
