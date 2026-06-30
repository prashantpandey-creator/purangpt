import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Deep electric indigo — primary brand accent. Mirrors globals.css tokens.
        saffron: "#e8b63f",
        primary: {
          50: "#f5f3ff",
          100: "#ede9fe",
          200: "#ddd6fe",
          300: "#c4b5fd",
          400: "#a78bfa",
          500: "#8b5cf6",
          600: "#7c3aed",
          700: "#6d28d9",
          800: "#5b21b6",
          900: "#4c1d95",
        },
        // Electric blue — secondary accent
        accent: {
          50: "#eef2ff",
          100: "#e0e7ff",
          200: "#c7d2fe",
          300: "#a5b4fc",
          400: "#818cf8",
          500: "#6366f1",
          600: "#4f46e5",
          700: "#4338ca",
          800: "#3730a3",
          900: "#312e81",
        },
        // Gold — candlelit flame accent
        gold: {
          50: "#fefce8",
          100: "#fef9c3",
          200: "#fef08a",
          300: "#fde047",
          400: "#f6d27a",
          500: "#e8b63f",
          600: "#d4a82e",
          700: "#b8893b",
          800: "#9a6d2c",
          900: "#7c541f",
        },
        // Legacy warm bronze — heritage touch, used sparingly
        legacy: {
          400: "#c9a86c",
          500: "#b8945a",
          600: "#a07d3e",
        },
        dark: {
          50: "#f8f8f8",
          100: "#f0f0f0",
          200: "#e8e8e8",
          300: "#d0d0d0",
          400: "#a0a0a0",
          500: "#686868",
          600: "#505050",
          700: "#383838",
          800: "#171514",
          900: "#0c0a09",
        },
      },
      fontSize: {
        xs: ["12px", { lineHeight: "16px" }],
        sm: ["14px", { lineHeight: "20px" }],
        base: ["16px", { lineHeight: "24px" }],
        lg: ["18px", { lineHeight: "28px" }],
        xl: ["20px", { lineHeight: "28px" }],
        "2xl": ["24px", { lineHeight: "32px" }],
        "3xl": ["30px", { lineHeight: "36px" }],
        "4xl": ["36px", { lineHeight: "40px" }],
        "5xl": ["48px", { lineHeight: "56px" }],
        "6xl": ["60px", { lineHeight: "72px" }],
      },
      fontFamily: {
        // Marcellus is the project's temple-inscription display face. The legacy
        // `font-cinzel` token is kept (used across 20+ files) but resolves to
        // Marcellus — `--font-cinzel` was never defined, so this also fixes the
        // headings that were silently falling back to the default serif.
        cinzel: "var(--font-marcellus)",
        marcellus: "var(--font-marcellus)",
        inter: "var(--font-inter)",
        devanagari: "var(--font-devanagari)",
      },
      animation: {
        "fade-in": "fadeIn 0.5s ease-in-out",
        "slide-up": "slideUp 0.5s ease-out",
        "slide-down": "slideDown 0.3s ease-out",
        "pulse-soft": "pulseSoft 3s ease-in-out infinite",
        "shimmer": "shimmer 2s infinite",
        "bounce-soft": "bounceSoft 2s ease-in-out infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { transform: "translateY(20px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        slideDown: {
          "0%": { transform: "translateY(-10px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        pulseSoft: {
          "0%": { opacity: "1" },
          "50%": { opacity: "0.5" },
          "100%": { opacity: "1" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-1000px 0" },
          "100%": { backgroundPosition: "1000px 0" },
        },
        bounceSoft: {
          "0%, 100%": { transform: "translateY(-2px)" },
          "50%": { transform: "translateY(2px)" },
        },
      },
      boxShadow: {
        "glow-sm": "0 0 16px rgba(99, 102, 241, 0.08)",
        "glow-md": "0 0 24px rgba(99, 102, 241, 0.12)",
        "glow-lg": "0 0 40px rgba(99, 102, 241, 0.18)",
        "glass": "0 8px 32px 0 rgba(15, 15, 40, 0.2)",
      },
      backdropFilter: {
        glass: "blur(10px) brightness(1.1)",
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "gradient-radial-to-r": "radial-gradient(circle at 0% 50%, var(--tw-gradient-stops))",
      },
    },
  },
  plugins: [
    require("@tailwindcss/forms"),
  ],
  darkMode: "class",
};

export default config;
