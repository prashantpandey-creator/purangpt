"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from "react";
import { loadJSON, saveJSON, STORAGE_KEYS } from "@/lib/storage";

type Theme = "dark" | "light";

interface UIState {
  sidebarOpen: boolean;       // mobile: drawer slid in/out
  sidebarCollapsed: boolean;  // desktop: drawer collapsed to a 72px icon rail
  theme: Theme;
}

interface UIPreferencesContextValue extends UIState {
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebarCollapsed: () => void;
  setTheme: (theme: Theme) => void;
}

const DEFAULT_UI: UIState = { sidebarOpen: false, sidebarCollapsed: false, theme: "dark" };

const UIPreferencesContext = createContext<
  UIPreferencesContextValue | undefined
>(undefined);

export function UIPreferencesProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<UIState>(DEFAULT_UI);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setState(loadJSON<UIState>(STORAGE_KEYS.ui, DEFAULT_UI));
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    saveJSON(STORAGE_KEYS.ui, state);
  }, [state, hydrated]);

  const setSidebarOpen = useCallback(
    (open: boolean) => setState((s) => ({ ...s, sidebarOpen: open })),
    []
  );
  const toggleSidebar = useCallback(
    () => setState((s) => ({ ...s, sidebarOpen: !s.sidebarOpen })),
    []
  );
  const setSidebarCollapsed = useCallback(
    (collapsed: boolean) => setState((s) => ({ ...s, sidebarCollapsed: collapsed })),
    []
  );
  const toggleSidebarCollapsed = useCallback(
    () => setState((s) => ({ ...s, sidebarCollapsed: !s.sidebarCollapsed })),
    []
  );
  const setTheme = useCallback(
    (theme: Theme) => setState((s) => ({ ...s, theme })),
    []
  );

  return (
    <UIPreferencesContext.Provider
      value={{ ...state, setSidebarOpen, toggleSidebar, setSidebarCollapsed, toggleSidebarCollapsed, setTheme }}
    >
      {children}
    </UIPreferencesContext.Provider>
  );
}

export function useUI(): UIPreferencesContextValue {
  const ctx = useContext(UIPreferencesContext);
  if (!ctx)
    throw new Error("useUI must be used within <UIPreferencesProvider>");
  return ctx;
}
