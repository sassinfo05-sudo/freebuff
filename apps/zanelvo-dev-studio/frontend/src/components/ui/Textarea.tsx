import { type TextareaHTMLAttributes, forwardRef } from "react";

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className = "", ...props }, ref) => (
    <textarea
      ref={ref}
      className={`w-full rounded-lg bg-white/[0.04] border border-white/10 px-2.5 py-2 text-xs text-white placeholder:text-white/30 outline-none resize-none transition-colors duration-150 focus:border-indigo-400/50 focus:bg-white/[0.06] ${className}`}
      {...props}
    />
  ),
);
Textarea.displayName = "Textarea";
