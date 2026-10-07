import type { Config } from "tailwindcss"

// DESIGN.md §3 — every value here is a direct transcription of that
// spec's tokens, not a design choice. Colors reference CSS variables
// defined once in src/index.css so there's a single source of truth.
// Tailwind's default spacing scale (0.5=2px step) and radius scale
// (rounded=4px, rounded-md=6px, rounded-lg=8px) already match §3.3
// exactly, so neither is overridden here.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "var(--brand-50)",
          100: "var(--brand-100)",
          600: "var(--brand-600)",
          700: "var(--brand-700)",
          800: "var(--brand-800)",
          900: "var(--brand-900)",
        },
        canvas: "var(--canvas)",
        surface: {
          DEFAULT: "var(--surface)",
          sunken: "var(--surface-sunken)",
          hover: "var(--surface-hover)",
        },
        border: {
          DEFAULT: "var(--border)",
          strong: "var(--border-strong)",
          danger: "var(--border-danger)",
        },
        text: {
          primary: "var(--text-primary)",
          secondary: "var(--text-secondary)",
          tertiary: "var(--text-tertiary)",
          disabled: "var(--text-disabled)",
          inverse: "var(--text-inverse)",
          danger: "var(--text-danger)",
          warning: "var(--text-warning)",
          info: "var(--text-info)",
        },
        danger: { 50: "var(--danger-50)", 700: "var(--danger-700)" },
        warning: { 50: "var(--warning-50)" },
        info: { 50: "var(--info-50)" },
        // Status pill backgrounds (DESIGN.md §3.1's status table) — one
        // shared set of five semantic pairs plus the one-off "dropped"
        // muted-brown pair, reused across deal/document/task pills.
        pill: {
          "neutral-bg": "#EEF0EE",
          "neutral-text": "#4A514C",
          "info-bg": "#E8F0FA",
          "info-text": "#1E5AA8",
          "success-bg": "#E5F4E1",
          "success-text": "#177A01",
          "warning-bg": "#FDF3DC",
          "warning-text": "#8A5A00",
          "danger-bg": "#FBE9E7",
          "danger-text": "#B42318",
          "dropped-bg": "#F3EFEA",
          "dropped-text": "#6B5A48",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      maxWidth: {
        content: "1400px",
      },
      fontSize: {
        // DESIGN.md §3.2 — [size, { lineHeight, fontWeight }]
        "title-page": ["20px", { lineHeight: "28px", fontWeight: "600" }],
        "title-section": ["15px", { lineHeight: "22px", fontWeight: "600" }],
        "title-task": ["18px", { lineHeight: "26px", fontWeight: "600" }],
        body: ["14px", { lineHeight: "20px", fontWeight: "400" }],
        "body-strong": ["14px", { lineHeight: "20px", fontWeight: "500" }],
        table: ["13px", { lineHeight: "20px", fontWeight: "400" }],
        meta: ["12px", { lineHeight: "16px", fontWeight: "400" }],
        label: ["12px", { lineHeight: "16px", fontWeight: "500" }],
        pill: ["12px", { lineHeight: "16px", fontWeight: "500" }],
      },
      transitionDuration: {
        DEFAULT: "120ms", // DESIGN.md §3.3 — hover/menus
      },
    },
  },
  plugins: [],
} satisfies Config
