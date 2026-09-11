import { type SelectHTMLAttributes, forwardRef } from "react";
import { ChevronDown } from "lucide-react";

interface Props extends SelectHTMLAttributes<HTMLSelectElement> {
  options: { value: string; label: string }[];
  placeholder?: string;
}

export const Select = forwardRef<HTMLSelectElement, Props>(
  ({ className = "", options, placeholder, disabled, ...props }, ref) => (
    <div className={`relative ${disabled ? "opacity-40" : ""}`}>
      <select
        ref={ref}
        disabled={disabled}
        className={`h-8 w-full appearance-none rounded-lg bg-white/[0.04] border border-white/10 pl-2.5 pr-7 text-xs text-white outline-none transition-colors duration-150 focus:border-indigo-400/50 focus:bg-white/[0.06] disabled:pointer-events-none ${className}`}
        {...props}
      >
        {placeholder && (
          <option value="" disabled hidden>
            {placeholder}
          </option>
        )}
        {options.map((o) => (
          <option key={o.value} value={o.value} className="bg-[#151420]">
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-white/40" />
    </div>
  ),
);
Select.displayName = "Select";
