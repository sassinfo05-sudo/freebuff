import { useEffect, useState } from "react";

type Kind = "success" | "error" | "info";
interface ToastItem {
  id: number;
  text: string;
  kind: Kind;
}

let items: ToastItem[] = [];
let nextId = 1;
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

function push(text: string, kind: Kind) {
  const id = nextId++;
  items = [...items, { id, text, kind }];
  emit();
  setTimeout(() => {
    items = items.filter((t) => t.id !== id);
    emit();
  }, 3500);
}

export const toast = {
  success: (text: string) => push(text, "success"),
  error: (text: string) => push(text, "error"),
  info: (text: string) => push(text, "info"),
};

const kindClasses: Record<Kind, string> = {
  success: "border-emerald-500/40 bg-emerald-500/10 text-emerald-200",
  error: "border-red-500/40 bg-red-500/10 text-red-200",
  info: "border-white/20 bg-white/10 text-white/80",
};

export function Toaster() {
  const [, setTick] = useState(0);
  useEffect(() => {
    const l = () => setTick((t) => t + 1);
    listeners.add(l);
    return () => {
      listeners.delete(l);
    };
  }, []);
  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2">
      {items.map((t) => (
        <div key={t.id} className={`rounded-lg border px-3 py-2 text-xs shadow-lg ${kindClasses[t.kind]}`}>
          {t.text}
        </div>
      ))}
    </div>
  );
}
