import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    path.join(__dirname, "index.html"),
    path.join(__dirname, "src/**/*.{ts,tsx}"),
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "rgb(7 9 13 / <alpha-value>)",
          900: "rgb(11 15 23 / <alpha-value>)",
          800: "rgb(17 23 36 / <alpha-value>)",
          700: "rgb(26 34 48 / <alpha-value>)",
          600: "rgb(36 45 60 / <alpha-value>)",
          500: "rgb(58 70 90 / <alpha-value>)",
          400: "rgb(93 107 126 / <alpha-value>)",
          300: "rgb(137 148 163 / <alpha-value>)",
          200: "rgb(184 192 204 / <alpha-value>)",
          100: "rgb(227 231 238 / <alpha-value>)",
        },
        accent: {
          emerald: "rgb(16 185 129 / <alpha-value>)",
          emeraldDark: "rgb(6 78 59 / <alpha-value>)",
          amber: "rgb(245 158 11 / <alpha-value>)",
          amberDark: "rgb(120 53 15 / <alpha-value>)",
          rose: "rgb(244 63 94 / <alpha-value>)",
          roseDark: "rgb(127 29 29 / <alpha-value>)",
          sky: "rgb(56 189 248 / <alpha-value>)",
          skyDark: "rgb(12 74 110 / <alpha-value>)",
          violet: "rgb(167 139 250 / <alpha-value>)",
          violetDark: "rgb(76 29 149 / <alpha-value>)",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        "inset-hi": "inset 0 1px 0 rgba(255,255,255,0.06)",
        glow: "0 0 0 1px rgba(56,189,248,0.25), 0 0 20px rgba(56,189,248,0.15)",
      },
      keyframes: {
        pulseDot: {
          "0%, 100%": { opacity: "0.6", transform: "scale(1)" },
          "50%": { opacity: "1", transform: "scale(1.25)" },
        },
      },
      animation: {
        pulseDot: "pulseDot 1.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
