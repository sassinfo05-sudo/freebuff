import { type SelectHTMLAttributes, forwardRef } from "react";

interface Props extends SelectHTMLAttributes<HTMLSelectElement> {
  options: { value: string; label: string }[];
  placeholder?: string;
}

export const Select = forwardRef<HTMLSelectElement, Props>(
  ({ className = "", options, placeholder, ...props }, ref) => (
    <select
      ref={ref}
      className={`h-8 w-full rounded-lg bg-white/5 border border-white/10 px-2 text-xs text-white outline-none focus:border-indigo-400/50 ${className}`}
      {...props}
    >
      {placeholder && (
        <option value="" disabled hidden>
          {placeholder}
        </option>
      )}
      {options.map((o) => (
        <option key={o.value} value={o.value} className="bg-[#14131F]">
          {o.label}
        </option>
      ))}
    </select>
  ),
);
Select.displayName = "Select";
