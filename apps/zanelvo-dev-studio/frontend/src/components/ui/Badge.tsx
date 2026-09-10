import type { HTMLAttributes } from "react";

export function Badge({ className = "", ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-1.5 py-0.5 text-[10px] font-medium leading-none ${className}`}
      {...props}
    />
  );
}
