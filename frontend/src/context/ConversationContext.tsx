"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useRef,
  useCallback,
  ReactNode,
} from "react";
import type { ChatMessage, SourceRef } from "@/lib/api";
import { loadJSON, saveJSON, STORAGE_KEYS } from "@/lib/storage";

export interface Conversation {
  id: string;
  title: string;
  sessionId: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
}

interface ConversationContextValue {
  conversations: Conversation[];
  activeId: string | null;
  hydrated: boolean;
  getConversation: (id: string) => Conversation | undefined;
  newConversation: () => Conversation;
  ensureConversation: (sessionId: string) => Conversation;
  selectConversation: (id: string) => void;
  deleteConversation: (id: string) => void;
  appendMessage: (id: string, message: ChatMessage) => void;
  updateMessage: (
    id: string,
    messageId: string,
    patch: Partial<ChatMessage>
  ) => void;
  truncateMessagesFrom: (id: string, messageId: string) => void;
  setSources: (id: string, messageId: string, sources: SourceRef[]) => void;
  renameFromFirstMessage: (id: string) => void;
  renameConversation: (id: string, title: string) => void;
  /** Find a conversation whose first user message overlaps significantly with `query`. */
  findSimilarConversation: (query: string, excludeId?: string) => Conversation | undefined;
}

const ConversationContext = createContext<ConversationContextValue | undefined>(
  undefined
);

function uuid(): string {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }
  return `id-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function makeConversation(): Conversation {
  const now = Date.now();
  return {
    id: uuid(),
    title: "New Chat",
    sessionId: uuid(),
    messages: [],
    createdAt: now,
    updatedAt: now,
  };
}

function deriveTitle(messages: ChatMessage[]): string {
  const firstUser = messages.find((m) => m.role === "user" && m.content.trim());
  if (!firstUser) return "New Chat";
  const text = firstUser.content.trim().replace(/\s+/g, " ");
  return text.length > 42 ? `${text.slice(0, 42)}…` : text;
}

export function ConversationProvider({ children }: { children: ReactNode }) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Ref mirror of conversations — lets callbacks read current state without
  // closing over a stale value, preventing dependency-chain re-render loops.
  const conversationsRef = useRef<Conversation[]>([]);

  // Keep ref in sync with state so callbacks always have fresh data.
  useEffect(() => {
    conversationsRef.current = conversations;
  }, [conversations]);

  // Hydrate once on mount.
  useEffect(() => {
    let stored = loadJSON<Conversation[]>(STORAGE_KEYS.conversations, []);
    
    // Auto-cleanup: remove leftover empty "New Inquiry" sessions except the most recent one
    const nonEmpty = stored.filter(c => c.messages.length > 0);
    const firstEmpty = stored.find(c => c.messages.length === 0);
    stored = firstEmpty ? [firstEmpty, ...nonEmpty] : nonEmpty;

    const storedActive = loadJSON<string | null>(
      STORAGE_KEYS.activeConversation,
      null
    );
    if (stored.length > 0) {
      conversationsRef.current = stored;
      setConversations(stored);
      setActiveId(
        storedActive && stored.some((c) => c.id === storedActive)
          ? storedActive
          : stored[0].id
      );
    }
    setHydrated(true);
  }, []);

  // Debounced persistence whenever conversations or active selection change.
  useEffect(() => {
    if (!hydrated) return;
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      saveJSON(STORAGE_KEYS.conversations, conversations);
      saveJSON(STORAGE_KEYS.activeConversation, activeId);
    }, 250);
    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
    };
  }, [conversations, activeId, hydrated]);

  const getConversation = useCallback(
    (id: string) => conversations.find((c) => c.id === id),
    [conversations]
  );

  const newConversation = useCallback(() => {
    let newOrExisting: Conversation | undefined = undefined;
    setConversations((prev) => {
      if (prev.length > 0 && prev[0].messages.length === 0) {
        newOrExisting = prev[0];
        setActiveId(newOrExisting.id);
        return prev;
      }
      newOrExisting = makeConversation();
      setActiveId(newOrExisting.id);
      return [newOrExisting, ...prev];
    });
    
    // Fallback if setConversations is deferred (React 18 concurrent mode)
    if (!newOrExisting) newOrExisting = makeConversation();
    return newOrExisting;
  }, []);

  // Find by id OR sessionId; create if a deep-linked id is unknown.
  // Uses conversationsRef so the callback is stable (no conversations dep),
  // preventing the chat page useEffect from re-running on every state change.
  const ensureConversation = useCallback(
    (idOrSession: string) => {
      const existing = conversationsRef.current.find(
        (c) => c.id === idOrSession || c.sessionId === idOrSession
      );
      if (existing) {
        setActiveId(existing.id);
        return existing;
      }
      const now = Date.now();
      const conv: Conversation = {
        id: idOrSession,
        title: "New Chat",
        sessionId: idOrSession,
        messages: [],
        createdAt: now,
        updatedAt: now,
      };
      setConversations((prev) => {
        // Guard: don't add a duplicate if it already exists
        if (prev.some((c) => c.id === idOrSession || c.sessionId === idOrSession)) {
          return prev;
        }
        return [conv, ...prev];
      });
      setActiveId(conv.id);
      return conv;
    },
    [] // stable — reads fresh state via conversationsRef
  );

  const selectConversation = useCallback((id: string) => setActiveId(id), []);

  const deleteConversation = useCallback(
    (id: string) => {
      setConversations((prev) => {
        const next = prev.filter((c) => c.id !== id);
        setActiveId((curr) =>
          curr === id ? (next.length ? next[0].id : null) : curr
        );
        return next;
      });
    },
    []
  );

  const touch = (conv: Conversation): Conversation => ({
    ...conv,
    updatedAt: Date.now(),
  });

  const appendMessage = useCallback(
    (id: string, message: ChatMessage) => {
      setConversations((prev) =>
        prev.map((c) =>
          c.id === id
            ? touch({ ...c, messages: [...c.messages, message] })
            : c
        )
      );
    },
    []
  );

  const updateMessage = useCallback(
    (id: string, messageId: string, patch: Partial<ChatMessage>) => {
      setConversations((prev) =>
        prev.map((c) =>
          c.id === id
            ? touch({
                ...c,
                messages: c.messages.map((m) =>
                  m.id === messageId ? { ...m, ...patch } : m
                ),
              })
            : c
        )
      );
    },
    []
  );

  const truncateMessagesFrom = useCallback(
    (id: string, messageId: string) => {
      setConversations((prev) =>
        prev.map((c) => {
          if (c.id !== id) return c;
          const index = c.messages.findIndex((m) => m.id === messageId);
          if (index === -1) return c;
          return touch({ ...c, messages: c.messages.slice(0, index) });
        })
      );
    },
    []
  );

  const setSources = useCallback(
    (id: string, messageId: string, sources: SourceRef[]) => {
      updateMessage(id, messageId, { sources });
    },
    [updateMessage]
  );

  const renameFromFirstMessage = useCallback((id: string) => {
    setConversations((prev) =>
      prev.map((c) =>
        c.id === id ? { ...c, title: deriveTitle(c.messages) } : c
      )
    );
  }, []);

  const renameConversation = useCallback((id: string, title: string) => {
    const clean = title.trim();
    if (!clean) return;
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, title: clean.slice(0, 80) } : c))
    );
  }, []);

  const findSimilarConversation = useCallback(
    (query: string, excludeId?: string) => {
      const qWords = new Set(query.toLowerCase().replace(/[?.,!]/g, "").split(/\s+/).filter((w) => w.length > 2));
      if (qWords.size < 3) return undefined; // too short to match meaningfully
      let best: Conversation | undefined;
      let bestScore = 0;
      for (const c of conversationsRef.current) {
        if (c.id === excludeId) continue;
        const firstUser = c.messages.find((m) => m.role === "user" && m.content.trim());
        if (!firstUser) continue;
        const cWords = firstUser.content.trim().toLowerCase().replace(/[?.,!]/g, "").split(/\s+/);
        const shared = cWords.filter((w) => qWords.has(w)).length;
        const score = shared / Math.max(qWords.size, cWords.length);
        if (score > 0.5 && score > bestScore) {
          bestScore = score;
          best = c;
        }
      }
      return bestScore >= 0.6 ? best : undefined;
    },
    [],
  );

  return (
    <ConversationContext.Provider
      value={{
        conversations,
        activeId,
        hydrated,
        getConversation,
        newConversation,
        ensureConversation,
        selectConversation,
        deleteConversation,
        appendMessage,
        updateMessage,
        truncateMessagesFrom,
        setSources,
        renameFromFirstMessage,
        renameConversation,
        findSimilarConversation,
      }}
    >
      {children}
    </ConversationContext.Provider>
  );
}

export function useConversations(): ConversationContextValue {
  const ctx = useContext(ConversationContext);
  if (!ctx)
    throw new Error(
      "useConversations must be used within <ConversationProvider>"
    );
  return ctx;
}
