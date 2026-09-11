import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  compact = false,
}: {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
  compact?: boolean;
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center animate-fade-in ${
        compact ? "py-8 px-4" : "py-16 px-6"
      }`}
    >
      {Icon && (
        <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-white/[0.04] border border-white/10">
          <Icon className="w-4 h-4 text-white/30" strokeWidth={1.75} />
        </div>
      )}
      <div className="text-xs font-medium text-white/60">{title}</div>
      {description && <div className="text-[11px] text-white/35 mt-1 max-w-xs">{description}</div>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}
