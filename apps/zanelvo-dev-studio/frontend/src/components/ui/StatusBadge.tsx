import { Badge } from "./Badge";
import { statusTone, formatStatusLabel } from "@/lib/status";

export function StatusBadge({ status, className = "" }: { status: string | null | undefined; className?: string }) {
  if (!status) return null;
  return (
    <Badge tone={statusTone(status)} dot className={`capitalize ${className}`}>
      {formatStatusLabel(status)}
    </Badge>
  );
}
