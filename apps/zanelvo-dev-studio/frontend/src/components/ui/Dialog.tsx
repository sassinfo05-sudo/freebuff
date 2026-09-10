import type { ReactNode } from "react";
import { X } from "lucide-react";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
}

export function Dialog({ open, onOpenChange, title, children, footer }: Props) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60" onClick={() => onOpenChange(false)} />
      <div className="relative w-full max-w-md rounded-xl bg-[#14131F] border border-white/10 text-white shadow-2xl">
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
          <h2 className="text-sm font-medium">{title}</h2>
          <button onClick={() => onOpenChange(false)} className="text-white/50 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-4 space-y-2">{children}</div>
        {footer && <div className="flex justify-end gap-2 px-4 py-3 border-t border-white/10">{footer}</div>}
      </div>
    </div>
  );
}
