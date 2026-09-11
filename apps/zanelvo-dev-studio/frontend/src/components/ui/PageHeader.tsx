import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export function PageHeader({
  icon: Icon,
  title,
  description,
  actions,
}: {
  icon?: LucideIcon;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="h-14 flex items-center gap-2.5 px-4 border-b border-white/10 flex-shrink-0">
      {Icon && (
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/[0.05] border border-white/10 flex-shrink-0">
          <Icon className="w-3.5 h-3.5 text-white/60" />
        </div>
      )}
      <div className="min-w-0">
        <div className="text-sm font-medium leading-tight">{title}</div>
        {description && <div className="text-[11px] text-white/40 truncate">{description}</div>}
      </div>
      {actions && <div className="ml-auto flex items-center gap-1.5 flex-shrink-0">{actions}</div>}
    </div>
  );
}
