"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  ReactNode,
} from "react";
import { useAuth } from "@/context/AuthContext";

// How many messages a guest may send before being nudged to sign in.
// The backend remains the authoritative hard limit (HTTP 429) regardless.
const GUEST_SOFT_LIMIT = Number(process.env.NEXT_PUBLIC_GUEST_SOFT_LIMIT) || Infinity;

const STORAGE_KEY = "purangpt:usage";

function today(): string {
  return new Date().toISOString().slice(0, 10); // YYYY-MM-DD
}

function readCount(): number {
  if (typeof window === "undefined") return 0;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return 0;
    const { date, count } = JSON.parse(raw) as { date: string; count: number };
    return date === today() ? count : 0;
  } catch {
    return 0;
  }
}

function writeCount(count: number) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ date: today(), count }));
  } catch {
    /* storage unavailable */
  }
}

interface UsageContextType {
  /** Call before sending. Returns true if the message may proceed. */
  attemptSend: () => boolean;
  /** Record a message that was actually sent (drives the guest gate). */
  recordMessage: () => void;
  /** Update token usage from the backend done event after a response completes. */
  updateUsage: (tokensUsed: number, tokenLimit: number | null) => void;
  /** Total tokens consumed today (null = not yet loaded from backend). */
  tokensUsed: number | null;
  /** Daily token limit for this user (null = unlimited / Pro). */
  tokenLimit: number | null;
  /** Tokens remaining (null = unlimited or not yet loaded). */
  tokensRemaining: number | null;
  /** Percentage of daily token budget used (null = unlimited or not loaded). */
  usagePct: number | null;
}

const UsageContext = createContext<UsageContextType>({
  attemptSend: () => true,
  recordMessage: () => {},
  updateUsage: () => {},
  tokensUsed: null,
  tokenLimit: null,
  tokensRemaining: null,
  usagePct: null,
});

export function UsageProvider({ children }: { children: ReactNode }) {
  const { user, initialized, openSignInModal } = useAuth();

  const [messagesToday, setMessagesToday] = useState(0);
  const [tokensUsed, setTokensUsed] = useState<number | null>(null);
  const [tokenLimit, setTokenLimit] = useState<number | null>(null);

  useEffect(() => {
    setMessagesToday(readCount());
  }, []);

  const isGuest = initialized && !user;

  const recordMessage = useCallback(() => {
    setMessagesToday((prev) => {
      const next = prev + 1;
      writeCount(next);
      return next;
    });
  }, []);

  const attemptSend = useCallback((): boolean => {
    if (isGuest && messagesToday >= GUEST_SOFT_LIMIT) {
      // Open the shared SignInModal from AuthContext — no duplicate modal instance.
      openSignInModal();
      return false;
    }
    return true;
  }, [isGuest, messagesToday, openSignInModal]);

  const updateUsage = useCallback((used: number, limit: number | null) => {
    setTokensUsed(used);
    setTokenLimit(limit);
  }, []);

  const tokensRemaining =
    tokenLimit !== null && tokensUsed !== null
      ? Math.max(0, tokenLimit - tokensUsed)
      : null;

  const usagePct =
    tokenLimit !== null && tokenLimit > 0 && tokensUsed !== null
      ? Math.min(100, Math.round((tokensUsed / tokenLimit) * 100))
      : null;

  return (
    <UsageContext.Provider
      value={{ attemptSend, recordMessage, updateUsage, tokensUsed, tokenLimit, tokensRemaining, usagePct }}
    >
      {children}
      {/* SignInModal instance removed — the single instance lives in AuthProvider */}
    </UsageContext.Provider>
  );
}

export function useUsage() {
  return useContext(UsageContext);
}
