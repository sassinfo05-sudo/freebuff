import { useEffect, type ReactNode } from "react";
import { X } from "lucide-react";

type Size = "sm" | "md" | "lg";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children?: ReactNode;
  footer?: ReactNode;
  size?: Size;
}

const sizeClasses: Record<Size, string> = {
  sm: "max-w-sm",
  md: "max-w-md",
  lg: "max-w-lg",
};

export function Dialog({ open, onOpenChange, title, description, children, footer, size = "md" }: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onOpenChange(false);
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, onOpenChange]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={title}>
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm animate-fade-in"
        onClick={() => onOpenChange(false)}
      />
      <div
        className={`relative w-full ${sizeClasses[size]} rounded-xl bg-surface-2 border border-white/10 text-white shadow-panel animate-scale-in`}
      >
        <div className="flex items-start justify-between gap-3 px-4 py-3.5 border-b border-white/10">
          <div className="min-w-0">
            <h2 className="text-sm font-medium">{title}</h2>
            {description && <p className="text-[11px] text-white/40 mt-0.5">{description}</p>}
          </div>
          <button
            onClick={() => onOpenChange(false)}
            className="text-white/40 hover:text-white hover:bg-white/10 rounded-md p-1 -m-1 transition-colors flex-shrink-0"
            aria-label="Close dialog"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        {children && <div className="p-4 space-y-2.5 max-h-[70vh] overflow-y-auto">{children}</div>}
        {footer && <div className="flex justify-end gap-2 px-4 py-3 border-t border-white/10">{footer}</div>}
      </div>
    </div>
  );
}
