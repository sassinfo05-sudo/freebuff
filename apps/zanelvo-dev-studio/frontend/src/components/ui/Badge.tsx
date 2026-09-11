import type { HTMLAttributes } from "react";

type Tone = "neutral" | "success" | "warning" | "danger" | "info" | "brand";

interface Props extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
  dot?: boolean;
  pulse?: boolean;
}

const toneClasses: Record<Tone, string> = {
  neutral: "border-white/15 text-white/60 bg-white/[0.03]",
  success: "border-emerald-500/30 text-emerald-300 bg-emerald-500/10",
  warning: "border-amber-500/30 text-amber-300 bg-amber-500/10",
  danger: "border-red-500/30 text-red-300 bg-red-500/10",
  info: "border-sky-500/30 text-sky-300 bg-sky-500/10",
  brand: "border-indigo-500/30 text-indigo-300 bg-indigo-500/10",
};

const dotClasses: Record<Tone, string> = {
  neutral: "bg-white/40",
  success: "bg-emerald-400",
  warning: "bg-amber-400",
  danger: "bg-red-400",
  info: "bg-sky-400",
  brand: "bg-indigo-400",
};

export function Badge({ className = "", tone, dot = false, pulse = false, children, ...props }: Props) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-medium leading-none whitespace-nowrap ${
        tone ? toneClasses[tone] : "border-white/20"
      } ${className}`}
      {...props}
    >
      {dot && tone && (
        <span className={`h-1.5 w-1.5 rounded-full flex-shrink-0 ${dotClasses[tone]} ${pulse ? "animate-pulse-ring" : ""}`} />
      )}
      {children}
    </span>
  );
}
