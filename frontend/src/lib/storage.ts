const PREFIX = "purangpt:";

/** SSR-safe JSON read from localStorage. Returns fallback on any failure. */
export function loadJSON<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(PREFIX + key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

/** SSR-safe JSON write to localStorage. Silently no-ops on failure. */
export function saveJSON<T>(key: string, value: T): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(PREFIX + key, JSON.stringify(value));
  } catch {
    /* quota / privacy mode — ignore */
  }
}

/** SSR-safe remove. */
export function removeKey(key: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(PREFIX + key);
  } catch {
    /* ignore */
  }
}

export const STORAGE_KEYS = {
  conversations: "conversations",
  activeConversation: "activeConversation",
  ui: "ui",
  chatPrefs: "chatPrefs",
} as const;
