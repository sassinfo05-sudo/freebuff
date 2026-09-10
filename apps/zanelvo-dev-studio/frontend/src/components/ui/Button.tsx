import { type ButtonHTMLAttributes, forwardRef } from "react";

type Variant = "primary" | "secondary" | "outline" | "ghost";
type Size = "sm" | "md" | "icon";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const variantClasses: Record<Variant, string> = {
  primary: "bg-indigo-500 hover:bg-indigo-400 text-white",
  secondary: "bg-white/15 hover:bg-white/25 text-white",
  outline: "border border-white/20 text-white/80 hover:bg-white/10 bg-transparent",
  ghost: "text-white/70 hover:bg-white/10 bg-transparent",
};

const sizeClasses: Record<Size, string> = {
  sm: "h-7 px-2.5 text-[11px]",
  md: "h-8 px-3 text-xs",
  icon: "h-8 w-8 p-0",
};

export const Button = forwardRef<HTMLButtonElement, Props>(
  ({ className = "", variant = "primary", size = "md", ...props }, ref) => (
    <button
      ref={ref}
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition disabled:opacity-40 disabled:pointer-events-none ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      {...props}
    />
  ),
);
Button.displayName = "Button";
