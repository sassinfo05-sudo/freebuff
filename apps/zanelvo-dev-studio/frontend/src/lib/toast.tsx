import { useEffect, useState } from "react";
import { CheckCircle2, XCircle, Info, X } from "lucide-react";

type Kind = "success" | "error" | "info";
interface ToastItem {
  id: number;
  text: string;
  kind: Kind;
}

const DURATION_MS = 4000;
const MAX_VISIBLE = 4;

let items: ToastItem[] = [];
let nextId = 1;
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

function dismiss(id: number) {
  items = items.filter((t) => t.id !== id);
  emit();
}

function push(text: string, kind: Kind) {
  const id = nextId++;
  items = [...items, { id, text, kind }].slice(-MAX_VISIBLE);
  emit();
  setTimeout(() => dismiss(id), DURATION_MS);
}

export const toast = {
  success: (text: string) => push(text, "success"),
  error: (text: string) => push(text, "error"),
  info: (text: string) => push(text, "info"),
};

const KIND_META: Record<Kind, { icon: typeof CheckCircle2; classes: string; iconClass: string }> = {
  success: {
    icon: CheckCircle2,
    classes: "border-emerald-500/30 bg-emerald-500/10 text-emerald-100",
    iconClass: "text-emerald-400",
  },
  error: {
    icon: XCircle,
    classes: "border-red-500/30 bg-red-500/10 text-red-100",
    iconClass: "text-red-400",
  },
  info: {
    icon: Info,
    classes: "border-white/15 bg-white/[0.07] text-white/90",
    iconClass: "text-white/50",
  },
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
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 w-80 max-w-[calc(100vw-2rem)]">
      {items.map((t) => {
        const meta = KIND_META[t.kind];
        const Icon = meta.icon;
        return (
          <div
            key={t.id}
            className={`group flex items-start gap-2 rounded-lg border px-3 py-2.5 text-xs shadow-panel backdrop-blur-sm animate-slide-in-right ${meta.classes}`}
          >
            <Icon className={`w-4 h-4 flex-shrink-0 mt-0.5 ${meta.iconClass}`} />
            <span className="flex-1 min-w-0 leading-snug">{t.text}</span>
            <button
              onClick={() => dismiss(t.id)}
              className="flex-shrink-0 opacity-0 group-hover:opacity-70 hover:!opacity-100 transition-opacity"
              aria-label="Dismiss"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
