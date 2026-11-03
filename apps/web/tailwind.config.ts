import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        canvas: {
          DEFAULT: "#0c0d10",
          subtle: "#0f1116",
        },
        surface: {
          DEFAULT: "#13151b",
          hover: "#181b23",
          elevated: "#1a1d26",
          inset: "#090a0d",
          border: "#232630",
          "border-subtle": "rgba(255, 255, 255, 0.07)",
        },
        dark: {
          50: "#1e2129",
          100: "#181b22",
          200: "#13151b",
          300: "#0f1116",
          400: "#0c0d10",
          border: "#232630",
          muted: "#7d8594",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "Fira Code", "Courier New", "monospace"],
      },
      boxShadow: {
        subtle: "0 1px 2px 0 rgba(0, 0, 0, 0.35)",
        card: "0 1px 3px 0 rgba(0, 0, 0, 0.4), 0 1px 2px -1px rgba(0, 0, 0, 0.4)",
        elevated: "0 8px 24px -4px rgba(0, 0, 0, 0.5), 0 2px 6px -2px rgba(0, 0, 0, 0.4)",
      },
    },
  },
  plugins: [],
};

export default config;
