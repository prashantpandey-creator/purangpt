"use client";

import { createTheme, ThemeProvider, CssBaseline } from "@mui/material";

const appTheme = createTheme({
  palette: {
    mode: "dark",
    primary: {
      main: "#a78bfa",    // indigo-400
      light: "#a5b4fc",   // indigo-300
      dark: "#8b5cf6",    // indigo-500
    },
    secondary: {
      main: "#60a5fa",    // blue-400
      light: "#93bbfd",   // blue-300
      dark: "#3b82f6",    // blue-500
    },
    background: {
      default: "#000000", // true OLED black
      paper: "#0a0a14",   // deep navy-black surface
    },
    text: {
      primary: "#e2e8f0",   // slate-200
      secondary: "#94a3b8", // slate-400
    },
    divider: "rgba(139,92,246,0.12)",
    action: {
      hover: "rgba(129,140,248,0.08)",
      selected: "rgba(129,140,248,0.12)",
    },
  },
  typography: {
    fontFamily: "var(--font-body), Inter, sans-serif",
    h1: { fontFamily: "var(--font-display), Marcellus, serif" },
    h2: { fontFamily: "var(--font-display), Marcellus, serif" },
    h3: { fontFamily: "var(--font-display), Marcellus, serif" },
    body1: { color: "#e2e8f0" },
    body2: { color: "#94a3b8" },
  },
  shape: { borderRadius: 12 },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: "#000000",
          color: "#e2e8f0",
        },
      },
    },
  },
});

export function AppThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider theme={appTheme}>
      <CssBaseline />
      {children}
    </ThemeProvider>
  );
}

export { appTheme };
export default appTheme;
