import { useEffect, useMemo, useRef, useState, type ComponentType } from "react";
import { Search } from "lucide-react";

export interface CommandItem {
  id: string;
  label: string;
  sublabel?: string;
  icon?: ComponentType<{ className?: string }>;
  onSelect: () => void;
}

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  items: CommandItem[];
}

/** Cmd/Ctrl+K quick nav — jump to any chat or panel without touching the sidebar. Reuses the
 * same overlay/backdrop/animation conventions as Dialog.tsx rather than that component itself,
 * since a search-first palette (input focused immediately, no title bar) has different chrome. */
export function CommandPalette({ open, onOpenChange, items }: Props) {
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (i) => i.label.toLowerCase().includes(q) || i.sublabel?.toLowerCase().includes(q),
    );
  }, [items, query]);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActiveIndex(0);
    const t = setTimeout(() => inputRef.current?.focus(), 0);
    return () => clearTimeout(t);
  }, [open]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onOpenChange(false);
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIndex((i) => Math.min(i + 1, filtered.length - 1));
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIndex((i) => Math.max(i - 1, 0));
      }
      if (e.key === "Enter") {
        e.preventDefault();
        const item = filtered[activeIndex];
        if (item) {
          onOpenChange(false);
          item.onSelect();
        }
      }
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, filtered, activeIndex, onOpenChange]);

  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-[60] flex items-start justify-center pt-[15vh] p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
    >
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm animate-fade-in" onClick={() => onOpenChange(false)} />
      <div className="relative w-full max-w-lg rounded-xl bg-surface-2 border border-white/10 text-white shadow-panel animate-scale-in overflow-hidden">
        <div className="flex items-center gap-2 px-3.5 py-3 border-b border-white/10">
          <Search className="w-4 h-4 text-white/40 flex-shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Jump to a chat, or switch panels…"
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-white/30"
          />
          <kbd className="text-[10px] text-white/30 border border-white/15 rounded px-1 py-0.5 flex-shrink-0">Esc</kbd>
        </div>
        <div className="max-h-[50vh] overflow-y-auto py-1.5">
          {filtered.map((item, i) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                onClick={() => {
                  onOpenChange(false);
                  item.onSelect();
                }}
                onMouseEnter={() => setActiveIndex(i)}
                className={`w-full flex items-center gap-2.5 px-3.5 py-2 text-xs text-left transition-colors ${
                  i === activeIndex ? "bg-white/[0.08] text-white" : "text-white/70"
                }`}
              >
                {Icon && <Icon className="w-3.5 h-3.5 flex-shrink-0 text-white/50" />}
                <span className="flex-1 min-w-0">
                  <div className="truncate">{item.label}</div>
                  {item.sublabel && <div className="text-[10px] text-white/35 truncate">{item.sublabel}</div>}
                </span>
              </button>
            );
          })}
          {!filtered.length && <div className="px-3.5 py-6 text-center text-xs text-white/30">No matches</div>}
        </div>
      </div>
    </div>
  );
}
