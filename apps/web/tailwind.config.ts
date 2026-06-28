import type { Config } from "tailwindcss";

// LU design language: Webull-style dark, high-density, professional.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: "#0B0E11", // app background
        panel: "#141A1F", // cards / panels
        "panel-2": "#1B232B", // raised surfaces
        line: "#222A31", // borders / dividers
        ink: "#E6EDF3", // primary text
        "ink-dim": "#8B98A5", // secondary text
        "ink-faint": "#5B6672", // tertiary / labels
        accent: "#21D0C3", // brand teal (interactive)
        up: "#22C55E", // gains (default green-up)
        down: "#EF4444", // losses
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      borderRadius: { lg: "10px", xl: "14px" },
    },
  },
  plugins: [],
};

export default config;
