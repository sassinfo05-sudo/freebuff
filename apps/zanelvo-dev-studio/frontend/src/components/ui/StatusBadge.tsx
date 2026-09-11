import { Badge } from "./Badge";
import { statusTone, formatStatusLabel, isActiveStatus } from "@/lib/status";

export function StatusBadge({ status, className = "" }: { status: string | null | undefined; className?: string }) {
  if (!status) return null;
  return (
    <Badge tone={statusTone(status)} dot pulse={isActiveStatus(status)} className={`capitalize ${className}`}>
      {formatStatusLabel(status)}
    </Badge>
  );
}
