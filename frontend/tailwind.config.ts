import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eff6ff",
          100: "#dbeafe",
          200: "#bfdbfe",
          300: "#93c5fd",
          400: "#60a5fa",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
          800: "#1e40af",
          900: "#1e3a8a",
        },
        "risk-high": {
          DEFAULT: "#ef4444",
          light: "#fca5a5",
          dark: "#b91c1c",
        },
        "risk-medium": {
          DEFAULT: "#f59e0b",
          light: "#fcd34d",
          dark: "#b45309",
        },
        "risk-low": {
          DEFAULT: "#22c55e",
          light: "#86efac",
          dark: "#15803d",
        },
        drift: {
          DEFAULT: "#a855f7",
          light: "#d8b4fe",
          dark: "#7e22ce",
        },
      },
    },
  },
  plugins: [],
};

export default config;
