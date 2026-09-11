import { type ButtonHTMLAttributes, forwardRef } from "react";
import { Loader2 } from "lucide-react";

type Variant = "primary" | "secondary" | "outline" | "ghost" | "danger";
type Size = "sm" | "md" | "icon";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

const variantClasses: Record<Variant, string> = {
  primary:
    "bg-gradient-to-b from-indigo-400 to-indigo-500 hover:from-indigo-300 hover:to-indigo-400 text-white shadow-soft",
  secondary: "bg-white/10 hover:bg-white/[0.16] text-white",
  outline: "border border-white/15 text-white/80 hover:border-white/25 hover:bg-white/[0.06] bg-transparent",
  ghost: "text-white/60 hover:text-white hover:bg-white/[0.07] bg-transparent",
  danger: "bg-red-500/90 hover:bg-red-500 text-white shadow-soft",
};

const sizeClasses: Record<Size, string> = {
  sm: "h-7 px-2.5 text-[11px] gap-1.5",
  md: "h-8 px-3 text-xs gap-1.5",
  icon: "h-8 w-8 p-0",
};

export const Button = forwardRef<HTMLButtonElement, Props>(
  ({ className = "", variant = "primary", size = "md", loading = false, disabled, children, ...props }, ref) => (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center rounded-lg font-medium transition-all duration-150 active:scale-[0.97] disabled:opacity-40 disabled:pointer-events-none disabled:active:scale-100 ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      {...props}
    >
      {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
      {children}
    </button>
  ),
);
Button.displayName = "Button";
