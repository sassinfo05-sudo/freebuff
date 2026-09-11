/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Surface layers, darkest to lightest — replaces ad-hoc #0B0A16/#0F0E1B/#14131F literals
        // scattered across the app with a single named scale.
        surface: {
          0: "#0A0912",
          1: "#0F0E1A",
          2: "#151420",
          3: "#1B1A29",
          4: "#232130",
        },
        brand: {
          indigo: "#6366F1",
          fuchsia: "#D946EF",
          amber: "#F5A623",
        },
      },
      fontFamily: {
        sans: [
          "Inter Variable",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "Helvetica",
          "Arial",
          "sans-serif",
        ],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "Liberation Mono",
          "monospace",
        ],
      },
      boxShadow: {
        soft: "0 1px 2px 0 rgb(0 0 0 / 0.4), 0 1px 1px 0 rgb(0 0 0 / 0.3)",
        panel: "0 4px 24px -4px rgb(0 0 0 / 0.5), 0 0 0 1px rgb(255 255 255 / 0.04)",
        glow: "0 0 0 1px rgb(99 102 241 / 0.4), 0 0 24px -4px rgb(99 102 241 / 0.35)",
      },
      keyframes: {
        "fade-in": { from: { opacity: 0 }, to: { opacity: 1 } },
        "fade-up": {
          from: { opacity: 0, transform: "translateY(4px)" },
          to: { opacity: 1, transform: "translateY(0)" },
        },
        "scale-in": {
          from: { opacity: 0, transform: "scale(0.97)" },
          to: { opacity: 1, transform: "scale(1)" },
        },
        "slide-in-right": {
          from: { opacity: 0, transform: "translateX(12px)" },
          to: { opacity: 1, transform: "translateX(0)" },
        },
        shimmer: {
          from: { backgroundPosition: "200% 0" },
          to: { backgroundPosition: "-200% 0" },
        },
        "pulse-ring": {
          "0%, 100%": { opacity: 1 },
          "50%": { opacity: 0.4 },
        },
      },
      animation: {
        "fade-in": "fade-in 0.15s ease-out",
        "fade-up": "fade-up 0.2s ease-out",
        "scale-in": "scale-in 0.15s cubic-bezier(0.16, 1, 0.3, 1)",
        "slide-in-right": "slide-in-right 0.2s cubic-bezier(0.16, 1, 0.3, 1)",
        shimmer: "shimmer 2s linear infinite",
        "pulse-ring": "pulse-ring 1.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
