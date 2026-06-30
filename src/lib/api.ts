import { getAccessToken } from "./auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

/** Chat modes dispatched to the backend.
 *  "chat" — the LLM self-selects its register per query (Guru / Scholar).
 *  "darshan" — spoken register for voice-to-voice (the DARSHAN_SYSTEM prompt).
 *  "deep" — standalone Deep Research pipeline (web-grounded, separate page). */
export type QueryMode = "chat" | "darshan" | "deep" | "guide" | "research";

/** Source passage shape returned by the FastAPI backend (to_frontend_dict). */
export interface SourceRef {
  text_id: string;
  text_name: string;
  purana: string;
  reference: string;
  chapter?: string | number | null;
  verse_range: string;
  text: string;
  language: string;
  edition?: string;
  tradition?: string;
  bias?: string;
  score?: number;
  line_num?: number;
  chunk_id?: string;
}

/** Query expansion returned by the backend query processor LLM. */
export interface QueryExpansion {
  detected_lang: string;
  is_sanskrit: boolean;
  canonical: string;
  synonyms: string[];
  devanagari: string;
  english_gloss: string;
  /** LLM-decided: "full" | "brief" | "redirect" */
  engagement: string;
  /** LLM-assessed emotional register: "warm" | "curious" | "heavy" | "sharp" | "distant" */
  mood: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: SourceRef[];
  timestamp?: number;
  pending?: boolean;
  error?: boolean;
  /** Reasoning tokens from DeepSeek-R1 / thinking models */
  reasoning?: string;
  /** Query expansion for this message */
  queryExpansion?: QueryExpansion;
  /** Provenance (from the `done` event) */
  groundingQuality?: string;
  sourcesUsed?: string[];
  gurujiVoiceUsed?: boolean;
  usageTokens?: number;
  usageTokenLimit?: number | null;
}

export interface ChatRequest {
  query: string;
  mode?: QueryMode;
  session_id?: string;
  top_k?: number;
  model?: string;
  language?: string;
  temperature?: number;
  verbosity?: "concise" | "balanced" | "detailed";
  address_as?: string;
  socratic?: boolean;
}

/** Morphic form names emitted by the visual SSE event. */
export type MorphicFormName = "bindu" | "chakra" | "yantra" | "nada" | "om" | "prana" | "kala" | "yuga";

/** Discrete SSE events emitted by /api/chat. */
export type ChatEvent =
  | { type: "sources"; sources: SourceRef[] }
  | { type: "token"; content: string }
  | { type: "reasoning"; content: string }
  | { type: "info"; message: string }
  | { type: "status"; message: string }
  | { type: "error"; message: string }
  | { type: "visual"; form: MorphicFormName }
  | { type: "latent_state"; vector: number[] }
  | ({ type: "query_expanded" } & QueryExpansion)
  | {
      type: "done";
      session_id?: string;
      grounding_quality?: string;
      total_sources_found?: number;
      sources_used?: string[];
      guruji_voice_used?: boolean;
      usage_tokens?: number;
      usage_token_limit?: number | null;
    };


/**
 * Thrown when the backend returns 429 — the user has exhausted their free
 * message quota. Callers can detect this (vs. a transient network error) to
 * trigger the upgrade paywall instead of a "Try again" retry prompt.
 */
export class LimitReachedError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "LimitReachedError";
  }
}

export async function authHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  try {
    const token = await getAccessToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  } catch {
    /* unauthenticated guest — backend allows with rate limit */
  }

  // Attach Device ID for guest tracking if in browser
  if (typeof window !== "undefined") {
    let deviceId = localStorage.getItem("purangpt_device_id");
    if (!deviceId) {
      deviceId = typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 15);
      localStorage.setItem("purangpt_device_id", deviceId);
    }
    headers["X-Device-ID"] = deviceId;
  }

  return headers;
}

/**
 * Stream a chat completion from the FastAPI SSE endpoint.
 * Yields typed ChatEvent objects as they arrive.
 */
export async function* streamChat(
  req: ChatRequest,
  signal?: AbortSignal
): AsyncGenerator<ChatEvent> {
  const response = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({
      query: req.query,
      mode: req.mode ?? "chat",
      session_id: req.session_id ?? "default",
      top_k: req.top_k ?? 10,
      model: req.model ?? "auto",
      stream: true,
    }),
    signal,
  });

  if (response.status === 429) {
    throw new LimitReachedError(
      "You've reached the message limit. Please sign in or upgrade to continue."
    );
  }
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const j = await response.json();
      detail = j.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (!response.body) throw new Error("No response stream from server.");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line (handles both \n\n and \r\n\r\n).
    const frames = buffer.split(/\r?\n\r?\n/);
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      const dataLines = frame
        .split(/\r?\n/)
        .filter((l) => l.startsWith("data:"))
        .map((l) => l.slice(5).trim());
      if (dataLines.length === 0) continue;
      const payload = dataLines.join("");
      if (!payload || payload === "[DONE]") continue;
      try {
        yield JSON.parse(payload) as ChatEvent;
      } catch {
        /* skip malformed frame */
      }
    }
  }
}

export const systemAPI = {
  async getStatus() {
    const res = await fetch(`${API_URL}/api/status`);
    if (!res.ok) throw new Error("Status check failed");
    return res.json();
  },
  async getPuranas() {
    const res = await fetch(`${API_URL}/api/puranas`);
    if (!res.ok) throw new Error("Failed to load texts");
    return res.json();
  },
  async getUserLimits() {
    const res = await fetch(`${API_URL}/api/limits`, {
      headers: await authHeaders(),
    });
    if (!res.ok) throw new Error("Failed to load limits");
    return res.json();
  },
};

export const searchAPI = {
  async search(query: string, topK = 20): Promise<SourceRef[]> {
    const res = await fetch(`${API_URL}/api/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, top_k: topK }),
    });
    if (!res.ok) throw new Error("Search failed");
    return res.json();
  },
  async searchVerses(query: string, topK = 36): Promise<SourceRef[]> {
    return this.search(query, topK);
  },
};

/** Illuminate chapter — SSE stream from GET /api/illuminate/{text_id}/{chapter} */
export async function* streamIlluminate(
  textId: string,
  chapter: number,
  language: string = "en",
  signal?: AbortSignal,
): AsyncGenerator<{ type: string; message?: string; content?: string }> {
  const response = await fetch(`${API_URL}/api/illuminate/${encodeURIComponent(textId)}/${chapter}?lang=${encodeURIComponent(language)}`, {
    headers: await authHeaders(),
    signal,
  });

  if (!response.ok) {
    let detail = `Illuminate request failed (${response.status})`;
    try { const j = await response.json(); detail = j.detail || detail; } catch { /* ignore */ }
    throw new Error(detail);
  }
  if (!response.body) throw new Error("No response stream from server.");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split(/\r?\n\r?\n/);
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const dataLines = frame.split(/\r?\n/).filter((l) => l.startsWith("data:")).map((l) => l.slice(5).trim());
      if (dataLines.length === 0) continue;
      const payload = dataLines.join("");
      if (!payload || payload === "[DONE]") continue;
      try { yield JSON.parse(payload) as { type: string; message?: string; content?: string }; } catch { /* skip malformed frame */ }
    }
  }
}

/** Workspace document review — SSE stream from POST /api/workspace/docs/{doc_id}/review */
export async function* streamReview(
  docId: string,
  language: string = "en",
  signal?: AbortSignal,
): AsyncGenerator<{ type: string; message?: string; content?: string }> {
  const response = await fetch(`${API_URL}/api/workspace/docs/${encodeURIComponent(docId)}/review?lang=${encodeURIComponent(language)}`, {
    method: "POST",
    headers: await authHeaders(),
    signal,
  });

  if (!response.ok) {
    let detail = `Review request failed (${response.status})`;
    try { const j = await response.json(); detail = j.detail || detail; } catch { /* ignore */ }
    throw new Error(detail);
  }
  if (!response.body) throw new Error("No response stream from server.");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split(/\r?\n\r?\n/);
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const dataLines = frame.split(/\r?\n/).filter((l) => l.startsWith("data:")).map((l) => l.slice(5).trim());
      if (dataLines.length === 0) continue;
      const payload = dataLines.join("");
      if (!payload || payload === "[DONE]") continue;
      try { yield JSON.parse(payload) as { type: string; message?: string; content?: string }; } catch { /* skip malformed frame */ }
    }
  }
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "An unknown error occurred";
}

/** Human-readable reference line for a source card. */
export function formatSourceRef(s: SourceRef): string {
  if (s.reference) return s.reference;
  const parts: string[] = [];
  if (s.chapter != null && s.chapter !== "") parts.push(`Ch. ${s.chapter}`);
  if (s.verse_range) parts.push(s.verse_range);
  return parts.join(" · ");
}
