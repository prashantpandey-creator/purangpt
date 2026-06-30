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

export type Verbosity = "concise" | "balanced" | "detailed";
export type TextSize = "compact" | "normal" | "large";

/**
 * Per-user chat + accessibility preferences. Persisted to localStorage so they
 * survive reloads; the chat send path reads these and forwards temperature,
 * verbosity and addressAs to the backend on every request.
 */
export interface ChatPrefsState {
  // How the assistant addresses the seeker (woven into the system prompt).
  addressAs: string;
  // Creativity of responses (backend clamps 0.0–1.5; 0.3 default).
  temperature: number;
  // Response length register.
  verbosity: Verbosity;
  // Accessibility: applied as a root font-scale.
  textSize: TextSize;
  // Chat behavior toggles.
  autoScroll: boolean;
  enterToSend: boolean;
}

interface ChatPreferencesContextValue extends ChatPrefsState {
  setAddressAs: (v: string) => void;
  setTemperature: (v: number) => void;
  setVerbosity: (v: Verbosity) => void;
  setTextSize: (v: TextSize) => void;
  setAutoScroll: (v: boolean) => void;
  setEnterToSend: (v: boolean) => void;
  reset: () => void;
}

const DEFAULT_PREFS: ChatPrefsState = {
  addressAs: "",
  temperature: 0.3,
  verbosity: "balanced",
  textSize: "normal",
  autoScroll: true,
  enterToSend: true,
};

export const TEXT_SIZE_SCALE: Record<TextSize, string> = {
  compact: "0.94",
  normal: "1",
  large: "1.12",
};

const ChatPreferencesContext = createContext<
  ChatPreferencesContextValue | undefined
>(undefined);

export function ChatPreferencesProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ChatPrefsState>(DEFAULT_PREFS);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setState({ ...DEFAULT_PREFS, ...loadJSON<Partial<ChatPrefsState>>(STORAGE_KEYS.chatPrefs, {}) });
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    saveJSON(STORAGE_KEYS.chatPrefs, state);
  }, [state, hydrated]);

  // Apply text-size accessibility scale to the document root so it affects the
  // whole app (rem-based sizing). Guarded for SSR.
  useEffect(() => {
    if (!hydrated || typeof document === "undefined") return;
    document.documentElement.style.setProperty(
      "--app-font-scale",
      TEXT_SIZE_SCALE[state.textSize]
    );
  }, [state.textSize, hydrated]);

  const setAddressAs = useCallback((v: string) => setState((s) => ({ ...s, addressAs: v.slice(0, 60) })), []);
  const setTemperature = useCallback((v: number) => setState((s) => ({ ...s, temperature: Math.max(0, Math.min(1.5, v)) })), []);
  const setVerbosity = useCallback((v: Verbosity) => setState((s) => ({ ...s, verbosity: v })), []);
  const setTextSize = useCallback((v: TextSize) => setState((s) => ({ ...s, textSize: v })), []);
  const setAutoScroll = useCallback((v: boolean) => setState((s) => ({ ...s, autoScroll: v })), []);
  const setEnterToSend = useCallback((v: boolean) => setState((s) => ({ ...s, enterToSend: v })), []);
  const reset = useCallback(() => setState(DEFAULT_PREFS), []);

  return (
    <ChatPreferencesContext.Provider
      value={{
        ...state,
        setAddressAs,
        setTemperature,
        setVerbosity,
        setTextSize,
        setAutoScroll,
        setEnterToSend,
        reset,
      }}
    >
      {children}
    </ChatPreferencesContext.Provider>
  );
}

export function useChatPreferences(): ChatPreferencesContextValue {
  const ctx = useContext(ChatPreferencesContext);
  if (!ctx)
    throw new Error(
      "useChatPreferences must be used within <ChatPreferencesProvider>"
    );
  return ctx;
}
