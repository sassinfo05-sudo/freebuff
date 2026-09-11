import { type InputHTMLAttributes, forwardRef } from "react";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
}

export const Input = forwardRef<HTMLInputElement, Props>(
  ({ className = "", invalid = false, ...props }, ref) => (
    <input
      ref={ref}
      className={`h-8 w-full rounded-lg bg-white/[0.04] border px-2.5 text-xs text-white placeholder:text-white/30 outline-none transition-colors duration-150 ${
        invalid
          ? "border-red-500/50 focus:border-red-400/70"
          : "border-white/10 focus:border-indigo-400/50 focus:bg-white/[0.06]"
      } ${className}`}
      {...props}
    />
  ),
);
Input.displayName = "Input";
