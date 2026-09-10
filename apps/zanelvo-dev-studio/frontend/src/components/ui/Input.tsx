import { type InputHTMLAttributes, forwardRef } from "react";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className = "", ...props }, ref) => (
    <input
      ref={ref}
      className={`h-8 w-full rounded-lg bg-white/5 border border-white/10 px-2.5 text-xs text-white placeholder:text-white/30 outline-none focus:border-indigo-400/50 ${className}`}
      {...props}
    />
  ),
);
Input.displayName = "Input";
