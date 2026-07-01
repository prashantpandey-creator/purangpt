"use client";

import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { YantraLoader } from "./YantraLoader";
import { motion, AnimatePresence, useReducedMotion, useMotionValue, useSpring } from "framer-motion";
import { transitionSoft, tap, EASE_OUT_SOFT } from "@/lib/motion";
import {
  Square,
  ChevronDown,
  RefreshCw,
  ArrowUp,
  Copy,
  Check,
  ThumbsUp,
  ThumbsDown,
  Sparkles,
  BookOpen,
  Mic,
} from "lucide-react";
import { useSpeechToText } from "@/hooks/useSpeechToText";
import { MicWaveform } from "./MicWaveform";
import { SignupNudge } from "@/components/chat/SignupNudge";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { streamChat, LimitReachedError, authHeaders, type ChatMessage, type SourceRef, type QueryMode, type QueryExpansion } from "@/lib/api";
import { VoiceEngine } from "@/lib/voiceEngine";
import { prewarmVoice, prewarmVoiceSynth } from "@/lib/ttsBase";
import { Capacitor } from "@capacitor/core";
import { useConversations } from "@/context/ConversationContext";
import { usePaywall } from "@/context/PaywallContext";
import { useUsage } from "@/context/UsageContext";
import { useToast } from "@/context/ToastContext";
import { SanskritTermCard } from './SanskritTermCard';
import { linkifyTerms, getTerm, type GlossaryEntry } from "@/lib/sanskritGlossary";
import { useAuth } from "@/context/AuthContext";
import { useChatPreferences } from "@/context/ChatPreferencesContext";
import { useLanguage } from "@/context/LanguageContext";
import { getTranslation } from "@/lib/i18n";
import { useSound } from "@/hooks/useSound";
import { requestHumBoot, setHumEnabled, getHumEnabled, triggerHumCompletion } from "@/lib/humControl";
import { setIntelligence } from "@/lib/binduPulse";

const MIN_TEXTAREA_HEIGHT = 44;


/** A quiet line under each answer naming what grounded it — the scripture cited
 *  in the cards and, when present, Guruji's own darshan. Answers the seeker's
 *  "how much is scripture vs Guruji" without breaking the first-person voice. */
function ProvenanceLine({
  texts,
  gurujiVoice,
  quality,
}: {
  texts?: string[];
  gurujiVoice?: boolean;
  quality?: string;
}) {
  if (quality === "ungrounded") return null;
  const clean = Array.from(
    new Set((texts ?? []).map((t) => (t || "").trim()).filter(Boolean))
  );
  if (clean.length === 0 && !gurujiVoice) return null;
  const grounded =
    clean.length > 0 ? `Grounded in ${clean.join(" · ")}` : "From Guruji's own words";
  const suffix = clean.length > 0 && gurujiVoice ? " · with Guruji's commentary" : "";
  return (
    <p
      className="mt-2 px-1 text-[11px] leading-relaxed"
      style={{ fontFamily: "var(--font-ui)", color: "#a38d7c", opacity: 0.85 }}
    >
      {grounded}
      {suffix}
    </p>
  );
}

/** Inline collapsible source-list for assistant messages. */
function SourcesBlock({
  sources,
  onSourceClick,
  msgId,
}: {
  sources: SourceRef[];
  onSourceClick?: (msgId: string, idx: number) => void;
  msgId: string;
}) {
  const [open, setOpen] = useState(false);
  if (sources.length === 0) return null;
  return (
    <div
      className="mt-3 overflow-hidden rounded-xl border"
      style={{ borderColor: 'rgba(124,58,237,0.18)', background: 'rgba(124,58,237,0.05)' }}
    >
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-4 py-2 text-left transition-colors hover:bg-[#7c3aed]/[0.06]"
      >
        <span className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em]" style={{ fontFamily: 'var(--font-ui)', color: '#7c3aed' }}>
          <BookOpen className="h-3 w-3" />
          {sources.length} Source{sources.length !== 1 ? 's' : ''}
        </span>
        <ChevronDown className={`h-4 w-4 text-[#7c3aed] transition-transform duration-300 ${open ? 'rotate-180' : ''}`} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="divide-y" style={{ borderColor: 'rgba(124,58,237,0.1)' }}>
              {sources.map((s, i) => (
                <button
                  key={i}
                  onClick={() => onSourceClick?.(msgId, i)}
                  className="flex w-full items-start gap-2.5 px-4 py-2.5 text-left transition-colors hover:bg-[#7c3aed]/[0.06]"
                >
                  <span className="mt-0.5 flex h-4 min-w-[1rem] flex-shrink-0 items-center justify-center rounded-full px-1 text-[9px] font-bold" style={{ background: 'rgba(124,58,237,0.14)', border: '1px solid rgba(124,58,237,0.35)', color: '#7c3aed' }}>
                    {i + 1}
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-[11px] uppercase tracking-wide text-[#7c3aed]" style={{ fontFamily: 'var(--font-ui)' }}>
                      {s.text_name || s.purana}
                    </p>
                    <p className="mt-0.5 truncate text-[11px] text-[#a38d7c]" style={{ fontFamily: 'var(--font-ui)' }}>
                      {s.reference || s.verse_range}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function QueryExpansionPanel({ expansion }: { expansion: QueryExpansion }) {
  const [open, setOpen] = useState(true);
  return (
    <div
      className="mt-2 mb-3 overflow-hidden rounded-lg border border-[#7c3aed]/20 bg-[#141416]/60"
    >
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-3 py-2 text-left"
      >
        <span className="text-[10px] uppercase tracking-widest text-[#7c3aed]/60">Sanskrit Analysis</span>
        <ChevronDown className={`h-3 w-3 text-[#7c3aed]/40 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="px-3 pb-2 text-[11px] text-[#7c3aed]/70 font-mono space-y-0.5">
          <div><span className="text-[#7c3aed]/50">canonical:</span> {expansion.canonical}</div>
          {expansion.devanagari && <div><span className="text-[#7c3aed]/50">devanagari:</span> {expansion.devanagari}</div>}
          {expansion.english_gloss && <div><span className="text-[#7c3aed]/50">gloss:</span> {expansion.english_gloss}</div>}
          {expansion.synonyms.length > 0 && <div><span className="text-[#7c3aed]/50">synonyms:</span> {expansion.synonyms.join(', ')}</div>}
        </div>
      )}
    </div>
  );
}

/** Ouroboros (snake eating its tail) — Ananta Shesha, the cosmic serpent of
 *  eternal cycle. Used in place of a generic icon for the follow-up pills. */
function OuroborosIcon({ size = 12, style }: { size?: number; style?: React.CSSProperties }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" aria-hidden="true" style={style}>
      {/* Main circular snake body — almost full circle */}
      <path d="M10 2a8 8 0 1 0 5.66 13.66" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"/>
      {/* Tail approaching head */}
      <path d="M10 2C11.4 0.8 13.4 1.1 14.9 2.4" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round"/>
      {/* Head — filled ellipse rotated toward tail */}
      <ellipse cx="16.3" cy="4.1" rx="2.1" ry="1.55" transform="rotate(-30 16.3 4.1)" fill="currentColor"/>
      {/* Eye — blinks every few seconds so the serpent reads as alive */}
      <ellipse cx="16.95" cy="3.45" rx="0.5" ry="0.5" fill="rgba(0,0,0,0.78)">
        <animate
          attributeName="ry"
          dur="3.6s"
          repeatCount="indefinite"
          keyTimes="0;0.9;0.94;0.98;1"
          values="0.5;0.5;0.04;0.5;0.5"
          calcMode="spline"
          keySplines="0.4 0 0.6 1;0.4 0 0.6 1;0.4 0 0.6 1;0.4 0 0.6 1"
        />
      </ellipse>
      {/* Forked tongue */}
      <path d="M15.3 5.6L14.4 6.85M15.3 5.6L16.1 6.9" stroke="currentColor" strokeWidth="0.65" strokeLinecap="round"/>
    </svg>
  );
}

/**
 * Contextual "what to ask next" pills shown under the latest answer. `items` is
 * `null` while the suggestions are still being generated (renders a soft
 * shimmer), an array once ready, or `[]` (renders nothing).
 * Each item has a short `label` shown on the pill and a richer `query` sent on click.
 */
function FollowupPills({
  items,
  onPick,
  label,
}: {
  items: {label: string; query: string}[] | null;
  onPick: (q: string) => void;
  label: string;
}) {
  if (items !== null && items.length === 0) return null;
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className="mt-3.5 flex flex-col gap-2"
    >
      <span
        className="flex items-center gap-1.5 px-0.5 text-[10px] uppercase tracking-[0.22em]"
        style={{ fontFamily: 'var(--font-ui)', color: '#7c3aed' }}
      >
        <OuroborosIcon size={12} style={{ color: '#7c3aed' }} />
        {label}
      </span>
      <div className="flex flex-wrap gap-2">
        {items === null
          ? [0, 1, 2].map((i) => (
              <span
                key={i}
                className="h-8 animate-pulse rounded-full"
                style={{
                  width: [96, 120, 80][i],
                  background: 'rgba(124,58,237,0.07)',
                  border: '1px solid rgba(124,58,237,0.12)',
                }}
              />
            ))
          : items.map((item, i) => (
              <motion.button
                key={i}
                initial={{ opacity: 0, scale: 0.94 }}
                animate={{ opacity: 1, scale: 1 }}
                whileTap={tap}
                transition={{ delay: i * 0.06, duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
                onClick={() => onPick(item.query)}
                title={item.query}
                className="inline-flex items-center rounded-full px-3.5 py-2 text-left text-[12.5px] leading-snug transition-all duration-200 hover:-translate-y-0.5 hover:bg-[#7c3aed]/[0.14] active:scale-[0.97]"
                style={{
                  background: 'rgba(124,58,237,0.06)',
                  border: '1px solid rgba(124,58,237,0.24)',
                  color: '#a78bfa',
                  fontFamily: 'var(--font-body)',
                }}
              >
                {item.label}
              </motion.button>
            ))}
      </div>
    </motion.div>
  );
}

interface ChatInterfaceProps {
  conversationId: string;
  initialQuery?: string;
  defaultMode?: QueryMode;
  onModeChange?: (mode: QueryMode) => void;
  onSourcesChange?: (sources: SourceRef[], messageId?: string) => void;
  onSourceClick?: (messageId: string, sourceIndex?: number) => void;
  /** Internal — set by the deep-research page. No mode selector is shown. */
  _deepResearch?: boolean;
}

export function ChatInterface({ conversationId, initialQuery, defaultMode, onModeChange, onSourcesChange, onSourceClick, _deepResearch }: ChatInterfaceProps) {
  const reducedMotion = useReducedMotion();
  const mode = defaultMode ?? "guide";
  const { user, profile, openSignInModal } = useAuth();
  const chatPrefs = useChatPreferences();
  const router = useRouter();
  const { openPaywall } = usePaywall();
  const { attemptSend, recordMessage, updateUsage, tokensUsed, tokenLimit, tokensRemaining, usagePct } = useUsage();
  const { toast } = useToast();
  const { language } = useLanguage();
  const { playClick, playAccepted, playThinking, stopThinking } = useSound();
  const {
    conversations,
    getConversation,
    appendMessage,
    updateMessage,
    truncateMessagesFrom,
    setSources,
    renameFromFirstMessage,
    findSimilarConversation,
  } = useConversations();

  const isPro = ["pro", "scholar", "admin"].includes(profile?.plan || "free");

  const [input, setInput] = useState("");
  const [socraticMode, setSocraticMode] = useState(false);
  const [textsMenuOpen, setTextsMenuOpen] = useState(false);
  const [docUploading, setDocUploading] = useState(false);

  const [isStreaming, setIsStreaming] = useState(false);
  const [yantraPhase, setYantraPhase] = useState<string>("default");
  const [selectedModel, setSelectedModel] = useState<string>("auto");
  const [commandHistory, setCommandHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState<number>(-1);
  const [lastQuery, setLastQuery] = useState<string>("");
  const [isInputFocused, setIsInputFocused] = useState(false);
  const [visualViewportHeight, setVisualViewportHeight] = useState<number | null>(null);
  // ("Jump to latest" pill retired — reading is now top-anchored, not tail-chasing.)
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Record<string, "up" | "down">>({});
  // Contextual "what to ask next" pills, generated per assistant message after
  // its answer completes. Keyed by assistant message id. `null` = still loading.
  const [followups, setFollowups] = useState<Record<string, {label: string; query: string}[] | null>>({});
  // The Sanskrit term whose dictionary card is currently open (null = closed).
  const [activeTerm, setActiveTerm] = useState<GlossaryEntry | null>(null);
  // Older exchanges collapse to just their ghost-echo question; the latest is
  // always expanded. This set holds the assistant-message ids the seeker has
  // manually re-expanded by tapping a collapsed question.
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const toggleExpanded = useCallback((assistantId: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(assistantId)) next.delete(assistantId);
      else next.add(assistantId);
      return next;
    });
  }, []);

  // Guru mode dynamic suggestions
  interface GuruSuggestion { topic: string; prompt: string; color: 'saffron' | 'gold' | 'blue'; }
  const [guruSuggestions, setGuruSuggestions] = useState<GuruSuggestion[]>([
    { topic: "Feeling lost", prompt: "I feel a bit lost right now. How can I find my purpose?", color: "saffron" },
    { topic: "Dealing with stress", prompt: "How can I find peace when everything around me feels chaotic?", color: "gold" },
    { topic: "Overcoming fear", prompt: "I'm struggling with anxiety. How can I build inner strength?", color: "blue" },
  ]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [personalized, setPersonalized] = useState(false);
  const firstTokenRef = useRef(false);
  const isThinkingRef = useRef(false);
  const hasTriggeredInitial = useRef(false);

  const abortControllerRef = useRef<AbortController | null>(null);
  const voiceEngineRef = useRef<VoiceEngine | null>(null);
  // Ref mirror of isStreaming — the STT onTranscript callback captures a stale
  // closure value; reading the ref instead of the state gives the live value.
  const isStreamingRef = useRef(false);
  isStreamingRef.current = isStreaming;
  // ── Speculative voice execution ─────────────────────────────────────────
  // When the seeker speaks, interim transcripts fire an early LLM call so the
  // response is already streaming by the time they finish their sentence.
  // The LLM think time (1-3s) overlaps with the remaining speech, giving a
  // near-instant response feel. On final: if the query matches → continue the
  // speculative stream; if mismatched → abort + restart with the final text.
  const speculativeAbortRef = useRef<AbortController | null>(null);
  const speculativeQueryRef = useRef("");
  const speculativeMsgIdRef = useRef<string | null>(null);
  const speculativeActiveRef = useRef(false);
  const lastSpeculativeTimeRef = useRef(0);
  // Refs for callbacks defined later (resolves TDZ — onTranscript references
  // them before their useCallback definitions).
  const handleSpeculativeSendRef = useRef<(q: string) => Promise<void>>(async () => {});
  const abortSpeculativeRef = useRef<() => void>(() => {});
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  // What the seeker is currently dictating (interim transcript) — shown live in
  // the voice overlay so they SEE their words being heard, distinct from the bar.
  const [liveTranscript, setLiveTranscript] = useState("");
  // Streaming buffer — tokens accumulate here; rAF flushes to React state at 60fps
  const streamBufferRef = useRef("");
  const streamReasoningRef = useRef("");
  const streamQueryExpansionRef = useRef<QueryExpansion | null>(null);
  const streamMsgIdRef = useRef<string | null>(null);
  const rafIdRef = useRef<number | null>(null);
  // How much of the stream buffer has been gracefully "inscribed" so far. The
  // flush loop advances this toward the buffer length at a calm, even cadence so
  // the verse appears like divine text being written — not dumped in bursts.
  const revealedLenRef = useRef(0);

  // Auto-trigger if initialQuery is provided
  useEffect(() => {
    if (initialQuery && !hasTriggeredInitial.current) {
      hasTriggeredInitial.current = true;
      handleSendMessage(initialQuery);
    }
  }, [initialQuery]);

  // Recent themes the user has actually explored — drawn from their saved
  // conversations (titles + first user turn), de-duplicated and capped. Used to
  // personalize Pro suggestions so the chips reflect their real journey.
  const recentThemes = useCallback((): string[] => {
    const seen = new Set<string>();
    const out: string[] = [];
    for (const c of [...conversations].sort((a, b) => b.updatedAt - a.updatedAt)) {
      const firstUser = c.messages.find((m) => m.role === "user" && m.content.trim());
      const theme = (firstUser?.content || c.title || "").trim().replace(/\s+/g, " ");
      const key = theme.toLowerCase().slice(0, 80);
      if (theme && theme !== "New Chat" && !seen.has(key)) {
        seen.add(key);
        out.push(theme.slice(0, 160));
      }
      if (out.length >= 8) break;
    }
    return out;
  }, [conversations]);

  // Fetch Guru suggestions. Pro users with history get personalized chips via a
  // POST that carries their recent themes; everyone else gets cached "trending".
  const fetchGuruSuggestions = useCallback(async (force = false) => {
    setSuggestionsLoading(true);
    const themes = recentThemes();
    // Full moment-context for EVERYONE (not just Pro): the seeker's recent
    // themes, UI language, IANA timezone (our region signal) + local hour/date.
    // The route composes context-aware chips from these and degrades gracefully
    // if any are absent.
    let timezone = "";
    let localHour: number | null = null;
    let localDate = "";
    try {
      timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
      const now = new Date();
      localHour = now.getHours();
      localDate = now.toDateString();
    } catch {
      /* env without Intl — server falls back to its own time */
    }
    try {
      const res = await fetch(`/api/guru-suggestions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ themes, language, timezone, localHour, localDate, refresh: force }),
      });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.suggestions) && data.suggestions.length > 0) {
          setGuruSuggestions(data.suggestions);
          setPersonalized(!!data.personalized);
        }
      }
    } catch {
      /* keep current fallback */
    } finally {
      setSuggestionsLoading(false);
    }
  }, [language, recentThemes]);

  // Load guru suggestions on mount + whenever Pro status resolves.
  useEffect(() => {
    fetchGuruSuggestions();
  }, [fetchGuruSuggestions]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const docInputRef = useRef<HTMLInputElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  // Top-anchored reading (mirrors the native iOS ChatView): the newest question
  // glides to the top of the view and its answer unspools beneath it. We hold a
  // ref to the latest user turn and the id of the turn we last anchored.
  const lastUserMsgRef = useRef<HTMLDivElement>(null);
  const lastTurnIdRef = useRef<string | null>(null);

  // ── Speech-to-text. The mic dictates into the input; partial results replace
  // the live dictation tail (everything typed before we started is preserved).
  const dictationBaseRef = useRef("");
  const speech = useSpeechToText({
    lang: ({ en: "en-US", hi: "hi-IN", ru: "ru-RU", sa: "hi-IN" } as Record<string, string>)[String(language)] ?? "en-US",
    onError: (msg) => setVoiceError(msg),
    onTranscript: (text, isFinal) => {
      const base = dictationBaseRef.current;
      const composed = base && text ? `${base} ${text}` : base + text;
      setInput(composed);
      // Surface the live words in the voice overlay (cleared on final / stop).
      setLiveTranscript(text);
      if (isFinal) {
        const q = composed.trim();
        dictationBaseRef.current = "";
        setLiveTranscript("");
        if (!q || isStreamingRef.current) return;
        // ── Speculative check ──────────────────────────────────────────
        // If a speculative call is already streaming for a closely-matching
        // query, let it continue — the response is already arriving. The
        // match is prefix-based: if the final query starts with what was
        // sent speculatively (or vice-versa), the response is on-topic.
        if (speculativeActiveRef.current) {
          const specQ = speculativeQueryRef.current;
          const close =
            q.startsWith(specQ) || specQ.startsWith(q) ||
            // Levenshtein-ish: share at least 70% of words
            (() => {
              const qWords = new Set(q.toLowerCase().split(/\s+/));
              const sWords = specQ.toLowerCase().split(/\s+/);
              const shared = sWords.filter((w) => qWords.has(w)).length;
              return shared >= sWords.length * 0.7;
            })();
          if (close) {
            // Speculative response is good — let it finish naturally.
            // The stream is already running; just mark it as confirmed.
            setInput("");
            speculativeActiveRef.current = false;
            speculativeQueryRef.current = "";
            // Transfer ownership: the speculative message becomes the
            // confirmed message. No abort needed.
            return;
          }
          // Mismatch — abort the speculative stream and send fresh.
          abortSpeculativeRef.current();
        }
        setInput("");
        void handleSendMessage(q, undefined, true); // fromVoice — skip consume flight
      } else {
        // ── Interim: maybe fire speculative send ────────────────────────
        const q = composed.trim();
        if (
          q.length >= 30 &&
          !speculativeActiveRef.current &&
          !isStreamingRef.current &&
          Date.now() - lastSpeculativeTimeRef.current > 2000
        ) {
          lastSpeculativeTimeRef.current = Date.now();
          speculativeQueryRef.current = q;
          void handleSpeculativeSendRef.current(q);
        }
      }
    },
  });
  const toggleDictation = useCallback(() => {
    if (speech.listening) {
      void speech.stop();
    } else {
      setVoiceError(null);
      dictationBaseRef.current = input.trim();
      void speech.start();
    }
  }, [speech, input]);

  // Top-anchored reading: we deliberately do NOT chase the streaming tail to the
  // bottom. The question stays pinned at the top while its answer fills beneath.
  const followStream = () => {};

  // ── Speculative voice send ───────────────────────────────────────────────
  // Fires an early LLM call from an interim transcript while the seeker is still
  // speaking. Creates a real assistant message + stream; on final we either
  // confirm it (final ≈ speculative) or abort + replace (final diverged).
  const handleSpeculativeSend = useCallback(async (query: string) => {
    if (speculativeActiveRef.current || isStreamingRef.current) return;
    speculativeActiveRef.current = true;
    speculativeQueryRef.current = query;

    // Re-use the core send logic but with a separate abort controller so we can
    // cancel the speculative stream independently of the main one.
    const abortCtrl = new AbortController();
    speculativeAbortRef.current = abortCtrl;

    const assistantId = crypto.randomUUID();
    speculativeMsgIdRef.current = assistantId;
    appendMessage(conversationId, {
      id: assistantId,
      role: "assistant",
      content: "",
      pending: true,
      timestamp: Date.now(),
    });

    // Local buffers for the speculative stream (separate from the main ones)
    const specBuf = { text: "", reasoning: "" };
    let specRafId: number | null = null;

    const flushSpec = () => {
      const target = specBuf.text.length;
      if (!speculativeMsgIdRef.current) return;
      // Fast reveal: the speculative response should feel immediate
      updateMessage(conversationId, speculativeMsgIdRef.current, {
        content: specBuf.text,
        reasoning: specBuf.reasoning || undefined,
        pending: true,
      });
      followStream();
      specRafId = requestAnimationFrame(flushSpec);
    };
    specRafId = requestAnimationFrame(flushSpec);

    try {
      for await (const event of streamChat(
        { query, mode: "chat", model: selectedModel, language },
        abortCtrl.signal,
      )) {
        if (!speculativeActiveRef.current) break; // cancelled by final
        if (event.type === "query_expanded") {
          setYantraPhase("search");
        } else if (event.type === "latent_state") {
          setYantraPhase("latent");
        } else if (event.type === "sources") {
          setYantraPhase("respond");
        } else if (event.type === "token") {
          setYantraPhase("respond");
          specBuf.text += event.content;
          if (voiceEnabled) voiceEngineRef.current?.pushToken(event.content);
        } else if (event.type === "reasoning") {
          specBuf.reasoning += event.content;
        } else if (event.type === "done") {
          if (!speculativeActiveRef.current) break;
          updateMessage(conversationId, assistantId, {
            content: specBuf.text,
            reasoning: specBuf.reasoning || undefined,
            pending: false,
            groundingQuality: event.grounding_quality,
            sourcesUsed: event.sources_used,
          });
          if (voiceEnabled) voiceEngineRef.current?.flushFinal();
        } else if (event.type === "error") {
          updateMessage(conversationId, assistantId, {
            error: true, pending: false,
            content: `__RETRY__${event.message || "Temporary error"}`,
          });
        }
      }
    } catch {
      // Aborted — the final transcript will handle it
    } finally {
      if (specRafId) cancelAnimationFrame(specRafId);
      speculativeActiveRef.current = false;
      speculativeMsgIdRef.current = null;
      speculativeAbortRef.current = null;
    }
  }, [conversationId, selectedModel, language, voiceEnabled, appendMessage, updateMessage, followStream]);
  handleSpeculativeSendRef.current = handleSpeculativeSend;

  const abortSpeculative = useCallback(() => {
    speculativeActiveRef.current = false;
    try { speculativeAbortRef.current?.abort(); } catch {}
    speculativeAbortRef.current = null;
    // Mark the speculative message as superseded — a fresh one will be created
    // by the final send. The user sees both: the cancelled speculative response
    // (partial) and the correct full response below it.
    if (speculativeMsgIdRef.current) {
      updateMessage(conversationId, speculativeMsgIdRef.current, {
        content: (streamBufferRef.current || "") + "\n\n*[voice rephrased — fresh answer below]*",
        pending: false,
      });
      speculativeMsgIdRef.current = null;
    }
    speculativeQueryRef.current = "";
  }, [conversationId, updateMessage]);
  abortSpeculativeRef.current = abortSpeculative;

  // Cancel the voice session: stop listening and DISCARD the dictated words,
  // restoring the input to whatever was typed before the mic was opened.
  const cancelDictation = useCallback(() => {
    void speech.stop();
    setInput(dictationBaseRef.current);
    dictationBaseRef.current = "";
    setLiveTranscript("");
  }, [speech]);

  // When listening ends for any reason (final, manual stop, error), drop the
  // live transcript so the voice overlay never lingers with stale words.
  useEffect(() => {
    if (!speech.listening) setLiveTranscript("");
  }, [speech.listening]);

  // Pre-warm the Modal voice GPU AS EARLY AS POSSIBLE — the instant the chat
  // surface mounts, before the seeker even toggles voice. Its ~30s cold start
  // then runs entirely under the time they spend reading, typing, and waiting
  // on the first reply, so his voice is ready the moment it's first needed.
  // Throttled (1/4min) + scale-to-zero, so idle still costs nothing.
  useEffect(() => { prewarmVoice(); }, []);

  // Disable VoiceEngine on unmount so no orphaned AudioContext plays after
  // the component is gone (e.g. navigating away mid-stream).
  useEffect(() => () => { voiceEngineRef.current?.disable(); }, []);

  // Switching conversations should stop STT and clear the live transcript.
  useEffect(() => {
    void speech.stop();
    setLiveTranscript("");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId]);

  const toggleVoice = useCallback(() => {
    setVoiceEnabled(prev => {
      const next = !prev;
      if (next) {
        if (!voiceEngineRef.current) voiceEngineRef.current = new VoiceEngine({
          elevenlabsKey: process.env.NEXT_PUBLIC_ELEVENLABS_API_KEY || "",
          elevenlabsVoiceId: process.env.NEXT_PUBLIC_ELEVENLABS_VOICE_ID || "",
        });
        voiceEngineRef.current.enable();
        // Deep-warm now — toggling voice on is strong intent. A throwaway synth
        // wakes the GPU AND runs RVC's first-load, so the clone is fully ready
        // before the next answer streams; its warm-up hides in the LLM think time.
        prewarmVoiceSynth();
      } else {
        voiceEngineRef.current?.disable();
      }
      return next;
    });
  }, []);


  const conversation = getConversation(conversationId);
  const messages = conversation?.messages ?? [];

  // The newest user turn — the question we anchor to the top of the reading view.
  const lastUserId = [...messages].reverse().find((m) => m.role === "user")?.id;

  // True while the user is reading near the bottom. When they scroll up to
  // re-read, streaming stops yanking them back down.
  const stickToBottomRef = useRef(true);

  const isNearBottom = () => {
    const el = scrollContainerRef.current;
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight < 120;
  };

  const scrollToBottom = (smooth = true) => {
    const el = scrollContainerRef.current;
    if (!el) return;
    if (smooth) {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    } else {
      el.scrollTop = el.scrollHeight;
    }
  };

  // Anti-gravity: newest question floats to the top of the viewport with spring
  const scrollQuestionToTop = (smooth = true) => {
    const el = scrollContainerRef.current;
    const target = lastUserMsgRef.current;
    if (!el || !target) return;
    const targetTop = target.offsetTop - 16; // 16px breathing room
    if (smooth) {
      el.scrollTo({ top: targetTop, behavior: "smooth" });
    } else {
      el.scrollTop = targetTop;
    }
  };

  // When a fresh question is asked, glide it to the top once (on the next frame,
  // after its node mounts). Streaming content updates do not re-scroll, so the
  // reader stays anchored to the question they just asked.
  useEffect(() => {
    if (lastUserId && lastUserId !== lastTurnIdRef.current) {
      lastTurnIdRef.current = lastUserId;
      requestAnimationFrame(() => scrollQuestionToTop(true));
    }
  }, [lastUserId]);

  // Track whether the reader is pinned to the bottom (drives followStream and
  // the floating "jump to latest" pill).
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const onScroll = () => {
      stickToBottomRef.current = isNearBottom();
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  // ── Smooth scroll via native CSS + spring-based stick-to-bottom ──────────
  const smoothScrollY = useMotionValue(0);
  const springY = useSpring(smoothScrollY, { stiffness: 170, damping: 26 });

  // Track velocity for anti-gravity feel — decelerating into position
  const scrollVelocity = useRef(0);
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    let lastY = el.scrollTop;
    let lastTime = performance.now();
    const onScroll = () => {
      const now = performance.now();
      const dt = Math.max(16, now - lastTime);
      scrollVelocity.current = (el.scrollTop - lastY) / dt;
      lastY = el.scrollTop;
      lastTime = now;
      stickToBottomRef.current = isNearBottom();
      smoothScrollY.set(el.scrollTop);
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [smoothScrollY]);

  // VisualViewport API — tracks keyboard height on mobile so input bar rises cleanly
  useEffect(() => {
    if (typeof window === 'undefined' || !window.visualViewport) return;
    const vv = window.visualViewport!;
    const onResize = () => setVisualViewportHeight(vv.height);
    vv.addEventListener('resize', onResize);
    return () => vv.removeEventListener('resize', onResize);
  }, []);

  // Phone-web flag. The empty-state Bindu orb (its three revolving "minds") is a
  // desktop/tablet flourish; on a narrow phone browser the three read as crude
  // blobs crowding the hero, so below 640px we drop the orb and collapse the
  // space it held. The native immersive path keeps its full-bleed orb stage.
  const [isPhoneWeb, setIsPhoneWeb] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined") return;
    const check = () => setIsPhoneWeb(window.innerWidth < 640);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  // Auto-resize textarea. Measured on the NEXT frame (after the flex row has its
  // final width) and re-fit on font load + viewport change. Measuring synchronously
  // on mount could catch the placeholder mid-wrap in a not-yet-laid-out row, lock
  // the box at its 200px max, and bury the answer behind a giant empty composer.
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    const fit = () => {
      // Empty composer is always exactly one row. A squeezed mobile width can
      // wrap the placeholder, and some WebKit builds count that wrap in
      // scrollHeight — which used to inflate the empty box to two rows and
      // shove the send/mic buttons down with it. Pin to the rows=1 default
      // whenever there is no actual value; only real typed text may grow it.
      if (!ta.value) { ta.style.height = ""; return; }
      ta.style.height = "auto";
      ta.style.height = Math.min(ta.scrollHeight, 200) + "px";
    };
    const raf = requestAnimationFrame(fit);
    let cancelled = false;
    if (typeof document !== "undefined" && (document as any).fonts?.ready) {
      (document as any).fonts.ready.then(() => { if (!cancelled) fit(); }).catch(() => {});
    }
    window.addEventListener("resize", fit);
    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", fit);
    };
  }, [input]);

  // Generate contextual follow-up pills for a finished answer. Fire-and-forget:
  // marks the message as loading (skeleton pills), then fills in 3 suggestions.
  const fetchFollowups = useCallback(
    async (assistantId: string, question: string, answer: string) => {
      // Strip internal markup (citations/suggestions/myth tags) before sending.
      const clean = (answer || "")
        .replace(/__RETRY__/g, "")
        .replace(/<MythBuster\s+[^>]*\/>/g, "")
        .split("[SUGGESTIONS]")[0]
        .trim();
      if (!clean || clean.startsWith("__")) return; // skip errors / upgrade prompts
      setFollowups((prev) => ({ ...prev, [assistantId]: null }));
      // Carry the thread's arc + the moment so follow-ups advance forward and
      // can tint to season/festival/time-of-day. All optional — the route
      // degrades gracefully without them.
      const priorTurns = (conversation?.messages || [])
        .filter((m) => m.role === "user" && m.content.trim() && m.content.trim() !== question.trim())
        .map((m) => m.content.trim().slice(0, 160))
        .slice(-5);
      let timezone = "";
      let localHour: number | null = null;
      let localDate = "";
      try {
        timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
        const now = new Date();
        localHour = now.getHours();
        localDate = now.toDateString();
      } catch {
        /* env without Intl — server falls back to its own time */
      }
      try {
        const res = await fetch("/api/followup-suggestions", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question, answer: clean, mode, language, priorTurns, timezone, localHour, localDate }),
        });
        const data = await res.json();
        const list = Array.isArray(data?.suggestions)
          ? data.suggestions
              .filter(
                (s: unknown): s is { label: string; query: string } =>
                  typeof s === "object" &&
                  s !== null &&
                  typeof (s as any).label === "string" &&
                  (s as any).label.trim().length > 0 &&
                  typeof (s as any).query === "string" &&
                  (s as any).query.trim().length > 0
              )
              .map((s: any) => ({ label: s.label.trim(), query: s.query.trim() }))
              .slice(0, 3)
          : [];
        setFollowups((prev) => ({ ...prev, [assistantId]: list }));
      } catch {
        setFollowups((prev) => ({ ...prev, [assistantId]: [] }));
      }
    },
    [mode, language, conversation]
  );

  // Upload a document straight from the composer → it lands in the seeker's
  // Workspace via the live /api/workspace/upload, then we route there so they can
  // watch it ingest and open it to read. (The deeper "Guru reads it inline in this
  // chat" — Saṅgati — is the next step; this v1 reuses the shipped Workspace.)
  const handleDocUpload = async (file: File) => {
    setTextsMenuOpen(false);
    setDocUploading(true);
    try {
      const headers = await authHeaders();
      delete headers["Content-Type"];
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ""}/api/workspace/upload`, {
        method: "POST",
        headers,
        body: form,
      });
      if (res.ok) router.push("/workspace");
    } catch {
      // swallow — the composer stays usable; the Workspace page surfaces real errors
    } finally {
      setDocUploading(false);
    }
  };

  const handleSendMessage = async (forcedQuery?: string, _opts?: unknown, fromVoice = false) => {
    const messageText = (forcedQuery || input).trim();
    if (!messageText || isStreaming) return;

    // Stop any in-progress dictation so the recognizer doesn't keep the mic open
    // after the message has been sent.
    if (speech.listening) void speech.stop();

    // Guests get a silent allowance, then a login gate. Returns false (and
    // opens the sign-in modal) once the soft limit is hit — abort the send.
    if (!attemptSend()) return;
    recordMessage();


    playClick();
    requestHumBoot();
    setLastQuery(messageText);
    // A fresh send always re-pins the reader to the bottom.
    stickToBottomRef.current = true;

    if (!forcedQuery) {
      setInput("");
      setCommandHistory(prev => [messageText, ...prev]);
      setHistoryIndex(-1);
    }
    const wasSocratic = socraticMode;
    setSocraticMode(false);
    setIsStreaming(true);
    setYantraPhase("expand");
    firstTokenRef.current = false;
    // Start thinking pulse while waiting for first token
    if (!isThinkingRef.current) {
      isThinkingRef.current = true;
      playThinking();
      // ── Nada hum: auto-play during LLM processing ──────────
      // Only if the seeker already had it on. Never force.
      const _humWasOn = getHumEnabled();
      (window as any).__purangpt_humWasOn = _humWasOn;
      if (_humWasOn) requestHumBoot();
    }

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: messageText,
      timestamp: Date.now(),
    };
    appendMessage(conversationId, userMsg);
    // Rename from the first message IMMEDIATELY so the sidebar title updates
    // as soon as the seeker sends — not only when the stream completes.
    renameFromFirstMessage(conversationId);

    const assistantId = crypto.randomUUID();

    // For signed-in users: check if a very similar conversation already exists.
    if (user) {
      const similar = findSimilarConversation(messageText, conversationId);
      if (similar) {
        toast(`Similar: "${similar.title}". Tap to continue there instead.`, "info");
      }
    }
    appendMessage(conversationId, {
      id: assistantId,
      role: "assistant",
      content: "",
      pending: true,
      timestamp: Date.now(),
    });
    // The new-turn effect glides this question to the top; no bottom-scroll here.

    abortControllerRef.current = new AbortController();
    streamBufferRef.current = "";
    streamReasoningRef.current = "";
    streamMsgIdRef.current = assistantId;
    revealedLenRef.current = 0;

    const flushBuffer = () => {
      // Inscribe the buffer gracefully: each frame the revealed length eases
      // toward what's arrived. A gentle floor keeps a steady hand even on a
      // slow trickle; the proportional term quietly catches up after a burst so
      // the text never lags far behind the stream — divine, deliberate, calm.
      const target = streamBufferRef.current.length;
      if (revealedLenRef.current < target) {
        const remaining = target - revealedLenRef.current;
        const step = Math.max(2, Math.ceil(remaining * 0.09));
        revealedLenRef.current = Math.min(target, revealedLenRef.current + step);
      }
      const content = streamBufferRef.current.slice(0, revealedLenRef.current);
      const reasoning = streamReasoningRef.current;
      if (streamMsgIdRef.current) {
        updateMessage(conversationId, streamMsgIdRef.current, {
          content,
          reasoning: reasoning || undefined,
          pending: true,
        });
        followStream();
      }
      rafIdRef.current = requestAnimationFrame(flushBuffer);
    };
    rafIdRef.current = requestAnimationFrame(flushBuffer);

    try {
      for await (const event of streamChat(
        {
          query: messageText,
          mode: _deepResearch ? "deep" : "chat",
          model: selectedModel,
          session_id: conversation?.sessionId,
          language: language,
          temperature: chatPrefs.temperature,
          verbosity: chatPrefs.verbosity,
          address_as: chatPrefs.addressAs || undefined,
          ...(wasSocratic ? { socratic: true } : {}),
        },
        abortControllerRef.current.signal
      )) {
        if (event.type === "query_expanded") {
          setYantraPhase("search");
          updateMessage(conversationId, assistantId, {
            content: streamBufferRef.current,
            reasoning: streamReasoningRef.current || undefined,
            pending: true,
          });
        } else if (event.type === "latent_state") {
          setYantraPhase("latent");
          // Pass the AI's thought vector (embeddings) to the WebGL shader
          setLatentVector(event.vector);
        } else if (event.type === "sources") {
          setYantraPhase("respond");
          // The LLM self-selects its register — surface sources whenever the
          // backend returns them (knowledge-seeking register includes citations).
          if (event.sources?.length) {
            setSources(conversationId, assistantId, event.sources);
            onSourcesChange?.(event.sources, assistantId);
          }
        } else if (event.type === "reasoning") {
          streamReasoningRef.current += event.content;
        } else if (event.type === "token") {
          // Play "accepted" tick on first token received
          if (!firstTokenRef.current) {
            firstTokenRef.current = true;
            playAccepted();
            // Stop thinking pulse when first real token arrives
            if (isThinkingRef.current) {
              stopThinking();
              isThinkingRef.current = false;
              // Restore prior hum preference — answer has begun
              if (!(window as any).__purangpt_humWasOn) {
                triggerHumCompletion();
                setHumEnabled(false);
              }
              delete (window as any).__purangpt_humWasOn;
            }
          }
          streamBufferRef.current += event.content;
          if (voiceEnabled) voiceEngineRef.current?.pushToken(event.content);
        } else if (event.type === "status") {
          // Deep-research progress updates (searching the web, synthesizing…)
          /* status suppressed */
        } else if (event.type === "error") {
          if (rafIdRef.current) { cancelAnimationFrame(rafIdRef.current); rafIdRef.current = null; }
          const errorMsg = event.message || "All AI providers are temporarily unavailable.";
          updateMessage(conversationId, assistantId, {
            error: true,
            pending: false,
            content: `__RETRY__${errorMsg}`,
            reasoning: streamReasoningRef.current || undefined,
          });
          // Terminal: stop consuming the stream so a late `done`/stray token
          // can't overwrite the error message with partial content.
          break;
        } else if (event.type === "done") {
          if (rafIdRef.current) { cancelAnimationFrame(rafIdRef.current); rafIdRef.current = null; }
          updateMessage(conversationId, assistantId, {
            content: streamBufferRef.current,
            reasoning: streamReasoningRef.current || undefined,
            pending: false,
            groundingQuality: event.grounding_quality,
            sourcesUsed: event.sources_used,
            gurujiVoiceUsed: event.guruji_voice_used,
          });
          renameFromFirstMessage(conversationId);
          if (voiceEnabled) voiceEngineRef.current?.flushFinal();
          // Sync free-tier token meter from backend authoritative values.
          if (event.usage_tokens !== undefined) {
            updateUsage(event.usage_tokens, event.usage_token_limit ?? null);
          }
          // Offer contextual next questions so the seeker can continue with a tap.
          fetchFollowups(assistantId, messageText, streamBufferRef.current);
        }
      }
    } catch (error: any) {
      if (rafIdRef.current) { cancelAnimationFrame(rafIdRef.current); rafIdRef.current = null; }
      if (error.name === "AbortError") {
        updateMessage(conversationId, assistantId, {
          content: streamBufferRef.current,
          reasoning: streamReasoningRef.current || undefined,
          pending: false,
        });
      } else if (error instanceof LimitReachedError || error.name === "LimitReachedError") {
        updateMessage(conversationId, assistantId, {
          error: true,
          pending: false,
          content: `__UPGRADE__${error.message}`,
          reasoning: streamReasoningRef.current || undefined,
        });
        if (Capacitor.isNativePlatform()) openPaywall();
      } else {
        updateMessage(conversationId, assistantId, {
          error: true,
          pending: false,
          content: `__RETRY__${error.message || "Connection error — please try again."}`,
          reasoning: streamReasoningRef.current || undefined,
        });
      }
    } finally {
      if (rafIdRef.current) { cancelAnimationFrame(rafIdRef.current); rafIdRef.current = null; }
      streamMsgIdRef.current = null;
      setIsStreaming(false);
      setYantraPhase("default");
      abortControllerRef.current = null;
      if (isThinkingRef.current) {
        stopThinking();
        isThinkingRef.current = false;
      }
      // Restore prior hum preference — processing ended
      if (!(window as any).__purangpt_humWasOn) {
        triggerHumCompletion();
      }
      delete (window as any).__purangpt_humWasOn;
      // Stay anchored to the question — no jump to the bottom when the answer ends.
    }
  };

  const handleRetry = () => {
    if (lastQuery) handleSendMessage(lastQuery);
  };

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  // Strip our internal citation/suggestion/myth markup before copying.
  const plainText = (raw: string) =>
    raw
      .replace(/__RETRY__/g, "")
      .replace(/<MythBuster\s+[^>]*\/>/g, "")
      .split("[SUGGESTIONS]")[0]
      .trim();

  const handleCopy = async (msg: ChatMessage) => {
    try {
      await navigator.clipboard.writeText(plainText(msg.content || ""));
      playAccepted();
      setCopiedId(msg.id);
      setTimeout(() => setCopiedId((id) => (id === msg.id ? null : id)), 1600);
    } catch {
      toast("Couldn't copy to clipboard", "error");
    }
  };

  // Regenerate: re-ask the user turn that immediately precedes this answer.
  const handleRegenerate = (assistantId: string) => {
    if (isStreaming) return;
    const idx = messages.findIndex((m) => m.id === assistantId);
    for (let i = idx - 1; i >= 0; i--) {
      if (messages[i].role === "user" && messages[i].content.trim()) {
        handleSendMessage(messages[i].content);
        return;
      }
    }
  };

  const handleFeedback = (id: string, value: "up" | "down") => {
    playClick();
    setFeedback((prev) => {
      const next = { ...prev };
      if (next[id] === value) delete next[id];
      else next[id] = value;
      return next;
    });
  };

  // ── The shared intelligence signal ───────────────────────────────────────
  // One value drives BOTH the void/Bindu visuals and the cosmic hum: when the
  // mind is thinking, light brightens and sound deepens in lockstep (binduPulse).
  const mindAwake =
    isStreaming || (suggestionsLoading && messages.length === 0);
  useEffect(() => {
    setIntelligence(mindAwake ? 1 : 0);
  }, [mindAwake]);

  // ── Exchange collapse ───────────────────────────────────────────────────
  // The latest answer is always expanded; older answers collapse to just their
  // ghost-echo question until the seeker taps to re-open them.

  // Depth for the 3D crawl: newest user message = 0, each older one increments.
  const userDepths = useMemo(() => {
    const um = messages.filter(m => m.role === 'user');
    return new Map(um.map((m, i) => [m.id, um.length - 1 - i]));
  }, [messages]);

  const latestAssistantId = (() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant") return messages[i].id;
    }
    return undefined;
  })();
  const isAnswerCollapsed = (assistantId: string) =>
    assistantId !== latestAssistantId && !expandedIds.has(assistantId);

  // ── The Deep Field — immersive orb-background mode ───────────────────────
  // Now enabled universally to keep the app, WebOS, and iOS uniform.
  // The ?immersive=0 query param can force it off for low-power devices.
  const [immersive, setImmersive] = useState(true);
  const [latentVector, setLatentVector] = useState<number[] | null>(null);
  useEffect(() => {
    try {
      const qp = new URLSearchParams(window.location.search).get("immersive");
      if (qp === "0") { window.localStorage.setItem("immersive", "0"); setImmersive(false); return; }
      if (qp === "1") { window.localStorage.removeItem("immersive"); }
      else if (window.localStorage.getItem("immersive") === "0") { setImmersive(false); return; }
    } catch {
      /* ignore */
    }
  }, []);

  // Center the Bindu vertically in the empty state. Place its center at ~35% of
  // the content area height so it reads as a hero, not a header logo.
  // visualViewportHeight covers mobile (keyboard-aware); window.innerHeight covers
  // desktop. Both minus ~60px for the topbar gives the usable content height.
  // The empty-state Bindu must YIELD on short viewports, or the orb + its top
  // padding shove the title + lineage line down behind the input composer
  // (the "intro hidden between the chips" fault). Shrink it and raise it as the
  // screen shortens; tall screens keep the full ceremonial presence.
  const emptyBinduSize = useMemo(() => {
    const vph =
      visualViewportHeight ??
      (typeof window !== "undefined" ? window.innerHeight : 750);
    // Scale the orb to the viewport height so the title + lineage + input +
    // chips always clear it. Short screens (a phone, or a half-height browser
    // window) get a small orb; tall screens keep the full ceremonial presence.
    // A dedicated mid band (680–820) shrinks the orb harder so the intro never
    // gets clipped behind the composer on laptops. (overlap fix 2026-06-28)
    if (vph < 680) return Math.round(Math.max(104, vph * 0.17));
    if (vph < 820) return Math.round(Math.max(132, vph * 0.20));
    return Math.round(Math.min(224, vph * 0.23));
  }, [visualViewportHeight]);

  const emptyBinduPaddingTop = useMemo(() => {
    const vph =
      visualViewportHeight ??
      (typeof window !== "undefined" ? window.innerHeight : 750);
    const contentH = Math.max(360, vph - 60);
    // Centre the orb higher as the screen shortens so the stack below has room;
    // subtract the ACTUAL half-height so the orb's centre lands on the ratio.
    const ratio = vph < 680 ? 0.13 : vph < 820 ? 0.22 : 0.32;
    return Math.max(16, Math.round(contentH * ratio - emptyBinduSize / 2));
  }, [visualViewportHeight, emptyBinduSize]);

  return (
    <div className="relative h-full w-full overflow-hidden">
      <div
        className="relative z-10 flex h-full flex-col overflow-hidden"
        style={{
          height: visualViewportHeight != null &&
            typeof window !== 'undefined' &&
            window.innerWidth < 768
              ? visualViewportHeight
              : undefined,
        }}
    >

      <div
        ref={scrollContainerRef}
        className="relative z-10 flex-1 min-h-0 overflow-y-auto px-4 sm:px-6 md:px-8 pb-6"
        style={{ scrollbarWidth: "thin", scrollbarColor: "rgba(129,140,248,0.25) transparent", WebkitOverflowScrolling: "touch", scrollBehavior: "smooth", overscrollBehaviorY: "contain" }}
      >
        {/* Soft radial scrim behind conversation text — pure CSS, no blur, no card.
            Keeps the void visible as atmosphere but gives text a dark anchor. */}
        {messages.length > 0 && (
          <div
            aria-hidden="true"
            className="pointer-events-none fixed inset-0 z-0"
            style={{
              background: "radial-gradient(ellipse 68% 90% at 50% 55%, rgba(4,3,8,0.58) 0%, rgba(4,3,8,0.30) 60%, transparent 100%)",
            }}
          />
        )}
        {messages.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="mx-auto flex w-full max-w-xl flex-col items-center text-center pt-2" style={{ marginTop: '18vh' }}
          >
            <h1
              className="bg-gradient-to-b from-[#a78bfa] via-[#a78bfa] to-[#7c3aed] bg-clip-text font-normal leading-[1.12] tracking-[0.005em] text-transparent"
              style={{
                fontFamily: "var(--font-display)",
                fontSize: "clamp(2rem, 7.2vw, 3rem)",
                filter: "drop-shadow(0 0 16px rgba(124,58,237,0.22))",
              }}
            >
              {getTranslation(language, "ui.begin_inquiry")}
            </h1>

            {/* Sacred dedication — a danda-flanked hairline, then the lineage line. */}
            <div className="mt-5 flex items-center justify-center gap-3" aria-hidden>
              <span className="h-px w-10 bg-gradient-to-r from-transparent to-[#7c3aed]/45" />
              <span className="text-sm leading-none text-[#7c3aed]/75">॥</span>
              <span className="h-px w-10 bg-gradient-to-l from-transparent to-[#7c3aed]/45" />
            </div>
            <p
              className="mt-3 text-[12.5px] tracking-[0.07em] sm:text-[13.5px]"
              style={{ fontFamily: "var(--font-display)", color: "#7c3aed" }}
            >
              {getTranslation(language, "ui.welcome_hint")}
            </p>
          </motion.div>
        ) : (
          <div
            className="mx-auto flex w-full max-w-4xl flex-col gap-5 transform-gpu will-change-transform"
            role="log"
            aria-live="polite"
            aria-relevant="additions text"
            aria-busy={isStreaming}
            style={{ transform: "translateZ(0)", backfaceVisibility: "hidden" }}
          >
            <AnimatePresence mode="popLayout">
            {messages.map((msg, i) => {
              if (msg.role === 'user') {
                const answer = messages.slice(i + 1).find((m) => m.role === 'assistant');
                const togglable = !!answer && answer.id !== latestAssistantId;
                const collapsed = !!answer && isAnswerCollapsed(answer.id);
                const isNewest = msg.id === lastUserId;
                const depth = userDepths.get(msg.id) ?? 0;
                return (
                  <motion.div
                    key={msg.id}
                    ref={msg.id === lastUserId ? lastUserMsgRef : undefined}
                    layout
                    initial={{ opacity: 0, y: 24, scale: 0.96 }}
                    animate={{
                      opacity: Math.max(0.4, 1 - depth * 0.18),
                      y: 0,
                      scale: 1,
                    }}
                    exit={{ opacity: 0, y: -12, scale: 0.96, transition: { duration: 0.2 } }}
                    transition={{
                      type: "spring",
                      stiffness: 280,
                      damping: 28,
                      mass: 0.6,
                    }}
                    className="msg-group flex w-full justify-center py-2"
                  >
                    {togglable ? (
                      <button
                        type="button"
                        onClick={() => toggleExpanded(answer!.id)}
                        aria-expanded={!collapsed}
                        className="group question-chip flex max-w-[85%] flex-col items-center gap-1.5 text-center"
                        style={{ opacity: collapsed ? 0.45 : 0.9, transition: 'opacity 0.4s ease' }}
                      >
                        <span
                          className="text-balance"
                          style={{
                            fontFamily: 'var(--font-display)',
                            fontSize: '1.125rem',
                            color: '#e7cd84',
                            lineHeight: 1.55,
                            letterSpacing: '0.008em',
                            whiteSpace: 'pre-wrap',
                            opacity: 0.92,
                            textShadow: '0 0 12px rgba(232,182,63,0.28), 0 0 24px rgba(232,182,63,0.10)',
                          }}
                        >
                          {msg.content}
                        </span>
                        <ChevronDown
                          className={`h-3.5 w-3.5 text-[#7c3aed]/50 transition-transform duration-300 ${collapsed ? '' : 'rotate-180'}`}
                          aria-hidden="true"
                        />
                      </button>
                    ) : (
                      <span
                        className="text-balance max-w-[85%] text-center"
                        style={{
                          fontFamily: 'var(--font-display)',
                          fontSize: '1.125rem',
                          color: '#e7cd84',
                          lineHeight: 1.55,
                          letterSpacing: '0.008em',
                          whiteSpace: 'pre-wrap',
                          opacity: 0.92,
                          textShadow: '0 0 12px rgba(232,182,63,0.32), 0 0 28px rgba(232,182,63,0.12)',
                        }}
                      >
                        {msg.content}
                      </span>
                    )}
                  </motion.div>
                );
              }

              const sources = msg.sources ?? [];
              // Older answers collapse to just their question; render nothing here.
              if (isAnswerCollapsed(msg.id)) return null;
              return (
                <motion.div
                  key={msg.id}
                  layout
                  initial={{ opacity: 0, y: reducedMotion ? 0 : 16, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ type: "spring", stiffness: 260, damping: 28, mass: 0.5 }}
                  className="msg-group flex w-full flex-col items-center gap-3"
                >
                  {/* The glass is born on send — breathing triad first, then the
                      stream cross-dissolves in on the same envelope. */}
                  <div className="flex w-full max-w-4xl flex-col items-center gap-3">
                    <div
                      className="answer-manifest answer-glass w-full px-4 py-4 sm:px-6 sm:py-5"
                      style={{ color: msg.error ? '#f87171' : '#e8e1d4' }}
                    >
                    {msg.pending && !msg.content ? (
                      <div className="flex w-full justify-center py-2">
                        <YantraLoader phase={yantraPhase} />
                      </div>
                    ) : (
                      (() => {
                        let mainText = msg.content || "";
                        let suggestions: string[] = [];
                        if (mainText.includes("[SUGGESTIONS]")) {
                          const parts = mainText.split("[SUGGESTIONS]");
                          mainText = parts[0].trim();
                          suggestions = parts[1]
                            .split("\n")
                            .map((line) => line.replace(/^\d+\.\s*/, "").trim())
                            .filter((line) => line.length > 0);
                        }

                        let mythBuster = null;
                        const mythMatch = mainText.match(/<MythBuster\s+common="([^"]+)"\s+source="([^"]+)"\s*\/>/);
                        if (mythMatch) {
                          mythBuster = { common: mythMatch[1], source: mythMatch[2] };
                          mainText = mainText.replace(mythMatch[0], "").trim();
                        }

                        return msg.content ? (
                          <>
                            {msg.content.startsWith('__UPGRADE__') ? (
                              <div className="flex flex-col gap-3">
                                <div className="flex items-center gap-2" style={{ color: '#7c3aed' }}>
                                  <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3l2.5 6L12 5l4.5 4L19 3v12a2 2 0 01-2 2H7a2 2 0 01-2-2V3z" /></svg>
                                  <span className="text-sm" style={{ fontFamily: 'Geist, monospace', color: '#e2e8f0' }}>
                                    {msg.content.replace('__UPGRADE__', '')}
                                  </span>
                                </div>
                                <button
                                  onClick={openPaywall}
                                  className="self-start flex items-center gap-2 px-4 py-2 rounded-full text-sm font-semibold transition-all"
                                  style={{ background: 'linear-gradient(135deg, #7c3aed, #a78bfa)', color: '#000000', fontFamily: 'Geist, monospace', boxShadow: '0 0 20px rgba(124,58,237,0.4)' }}
                                >
                                  <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24"><path d="M5 3l2.5 6L12 5l4.5 4L19 3v12a2 2 0 01-2 2H7a2 2 0 01-2-2V3z" /></svg>
                                  Upgrade to Pro
                                </button>
                              </div>
                            ) : msg.content.startsWith('__RETRY__') ? (
                              <div className="flex flex-col gap-3">
                                <div className="flex items-center gap-2" style={{ color: '#f87171' }}>
                                  <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" /></svg>
                                  <span className="text-sm" style={{ fontFamily: 'var(--font-ui)' }}>
                                    {msg.content.replace('__RETRY__', '')}
                                  </span>
                                </div>
                                <button
                                  onClick={handleRetry}
                                  disabled={isStreaming}
                                  className="self-start flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all disabled:opacity-40"
                                  style={{ background: 'rgba(124,58,237,0.12)', border: '1px solid rgba(124,58,237,0.3)', color: '#7c3aed', fontFamily: 'var(--font-ui)' }}
                                >
                                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                                  Try again
                                </button>
                              </div>
                            ) : (
                              <>
                                {mythBuster && (
                                  <div className="mb-6 rounded-2xl border p-4 shadow-sm" style={{ borderColor: 'rgba(124,58,237,0.2)', background: 'rgba(124,58,237,0.05)' }}>
                                    <div className="flex items-center gap-2 mb-3">
                                      <div className="flex items-center justify-center w-5 h-5 rounded-full bg-[#7c3aed]/20 text-[#7c3aed]">
                                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                                      </div>
                                      <span className="text-[11px] uppercase tracking-widest font-bold" style={{ fontFamily: 'var(--font-ui)', color: '#7c3aed' }}>Misconception Addressed</span>
                                    </div>
                                    <div className="space-y-3" style={{ fontFamily: 'var(--font-body)' }}>
                                      <div>
                                        <span className="text-xs font-semibold uppercase tracking-wider text-[#a38d7c] block mb-1">Common Belief</span>
                                        <p className="text-sm text-[#e5e2e1] opacity-80 italic">"{mythBuster.common}"</p>
                                      </div>
                                      <div>
                                        <span className="text-xs font-semibold uppercase tracking-wider text-[#7c3aed] block mb-1">What the Source Says</span>
                                        <p className="text-sm text-[#e5e2e1] leading-relaxed">{mythBuster.source}</p>
                                      </div>
                                    </div>
                                  </div>
                                )}
                                <div
                                  className={`prose-puran max-w-none ${msg.pending ? 'stream-live' : ''}`}
                                  style={{ fontFamily: 'var(--font-body)', lineHeight: 1.7 }}
                                >
                                  <ReactMarkdown
                                    remarkPlugins={[remarkGfm]}
                                    components={{
                                      a: ({ node, href, children, ...props }) => {
                                        if (href?.startsWith('term:')) {
                                          const entry = getTerm(href.slice('term:'.length));
                                          if (!entry) return <>{children}</>;
                                          return (
                                            <span
                                              role="button"
                                              tabIndex={0}
                                              onClick={(e) => {
                                                e.preventDefault();
                                                e.stopPropagation();
                                                playClick();
                                                setActiveTerm(entry);
                                              }}
                                              onKeyDown={(e) => {
                                                if (e.key === 'Enter' || e.key === ' ') {
                                                  e.preventDefault();
                                                  playClick();
                                                  setActiveTerm(entry);
                                                }
                                              }}
                                              className="sanskrit-term"
                                              aria-label={`${entry.term} — ${entry.translation}. Open dictionary.`}
                                            >
                                              {children}
                                            </span>
                                          );
                                        }
                                        if (href?.startsWith('citation:')) {
                                          const index = parseInt(href.replace('citation:', ''), 10);
                                          const source = sources[index - 1];
                                          return (
                                            <span className="relative group inline-block align-super mx-0.5 z-10">
                                              <button
                                                onClick={(e) => {
                                                  e.preventDefault();
                                                  e.stopPropagation();
                                                  onSourceClick?.(msg.id, index - 1);
                                                }}
                                                className="citation-badge inline-flex items-center justify-center min-w-[1.15rem] h-[1.15rem] px-1 text-[10px] font-bold rounded-full bg-[#7c3aed]/20 text-[#7c3aed] hover:bg-[#7c3aed]/40 transition-colors cursor-pointer border border-[#7c3aed]/30"
                                                aria-label={source ? `View source ${index}: ${source.text_name || source.purana}` : `View source ${index}`}
                                              >
                                                {index}
                                              </button>
                                              {source && (
                                                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50 pointer-events-none text-left"
                                                     style={{ background: '#141414', border: '1px solid rgba(124,58,237,0.3)' }}>
                                                  <div className="text-[10px] uppercase tracking-widest text-[#7c3aed] mb-1.5" style={{ fontFamily: 'var(--font-ui)' }}>
                                                    {source.text_name || source.purana} {source.reference ? `• ${source.reference}` : ''}
                                                  </div>
                                                  <div className="text-xs text-[#e5e2e1] opacity-90 line-clamp-4 leading-relaxed italic" style={{ fontFamily: 'var(--font-body)' }}>
                                                    "{source.text}"
                                                  </div>
                                                </div>
                                              )}
                                            </span>
                                          );
                                        }
                                        return <a href={href} className="text-[#7c3aed] hover:underline" target="_blank" rel="noopener noreferrer" {...props}>{children}</a>;
                                      }
                                    }}
                                  >
                                    {(() => {
                                      const withCitations = sources.length > 0
                                        ? (mainText || "").replace(/\[(\d+)\]/g, (full, n) => {
                                            const idx = parseInt(n, 10);
                                            return idx >= 1 && idx <= sources.length
                                              ? `[${n}](citation:${n})`
                                              : full;
                                          })
                                        : (mainText || "");
                                      // Only linkify Sanskrit terms once the answer
                                      // is settled, so we don't underline half-typed
                                      // words while the text is still streaming in.
                                      return msg.pending ? withCitations : linkifyTerms(withCitations);
                                    })()}
                                  </ReactMarkdown>
                                  {msg.pending && mainText && <span className="stream-caret" aria-hidden="true" />}
                                </div>

                                {suggestions.length > 0 && !msg.pending && !isInputFocused && (
                                  <div className="mt-5 flex flex-col gap-2">
                                    <p className="mb-1 text-[10px] uppercase tracking-[0.22em] text-[#a38d7c]" style={{ fontFamily: 'var(--font-ui)' }}>{getTranslation(language, "ui.follow_up")}</p>
                                    {suggestions.map((s, idx) => (
                                      <button
                                        key={idx}
                                        onClick={() => handleSendMessage(s)}
                                        className="rounded-2xl px-4 py-2.5 text-left text-sm transition-colors hover:bg-[#7c3aed]/10"
                                        style={{
                                          border: '1px solid rgba(124,58,237,0.3)',
                                          color: '#7c3aed',
                                          fontFamily: 'var(--font-body)'
                                        }}
                                      >
                                        {s}
                                      </button>
                                    ))}
                                  </div>
                                )}
                              </>
                            )}
                          </>
                        ) : msg.pending ? (
                          msg.reasoning ? (
                            // R1 is thinking aloud before the answer begins.
                            <>
                              {msg.queryExpansion && (
                                <QueryExpansionPanel expansion={msg.queryExpansion} />
                              )}
                              <div className="mb-3 rounded-lg border border-[#7c3aed]/20 bg-[#141416]/60 px-4 py-3 text-xs text-[#7c3aed]/70 font-mono leading-relaxed max-h-40 overflow-y-auto">
                                <span className="block text-[#7c3aed]/50 mb-1 uppercase tracking-widest text-[10px]">Reasoning…</span>
                                {msg.reasoning}
                              </div>
                              <div className="flex w-full justify-center py-4">
                                <span className="flex gap-1.5" aria-label="Guruji is concentrating">
                                  <span className="h-1.5 w-1.5 rounded-full bg-[#7c3aed]/70 animate-pulse" />
                                  <span className="h-1.5 w-1.5 rounded-full bg-[#7c3aed]/70 animate-pulse" style={{ animationDelay: '0.15s' }} />
                                  <span className="h-1.5 w-1.5 rounded-full bg-[#7c3aed]/70 animate-pulse" style={{ animationDelay: '0.3s' }} />
                                </span>
                              </div>
                            </>
                          ) : (
                            <>
                              {msg.queryExpansion && (
                                <QueryExpansionPanel expansion={msg.queryExpansion} />
                              )}
                              <div className="flex w-full justify-center py-4">
                                <span className="flex gap-1.5" aria-label="Guruji is concentrating">
                                  <span className="h-1.5 w-1.5 rounded-full bg-[#7c3aed]/70 animate-pulse" />
                                  <span className="h-1.5 w-1.5 rounded-full bg-[#7c3aed]/70 animate-pulse" style={{ animationDelay: '0.15s' }} />
                                  <span className="h-1.5 w-1.5 rounded-full bg-[#7c3aed]/70 animate-pulse" style={{ animationDelay: '0.3s' }} />
                                </span>
                              </div>
                            </>
                          )
                        ) : (
                          <div className="flex flex-col items-start gap-2">
                            <span className="text-sm" style={{ color: msg.error ? '#ef4444' : '#a38d7c' }}>
                              {msg.error ? "Response failed." : "Response stopped."}
                            </span>
                            <button 
                              onClick={() => handleSendMessage(msg.content)} 
                              className="px-3 py-1 rounded-full text-xs transition-colors hover:bg-white/10"
                              style={{ border: '1px solid rgba(124,58,237,0.4)', color: '#7c3aed' }}
                            >
                              Retry
                            </button>
                          </div>
                        );
                      })()
                    )}

                      {!msg.pending && !msg.error && msg.content && !msg.content.startsWith('__RETRY__') && (
                        <div className="mt-3 flex items-center justify-between gap-3">
                          <div className="msg-actions flex items-center gap-1.5">
                            <button
                              className="msg-action"
                              onClick={() => handleCopy(msg)}
                              aria-label="Copy answer"
                            >
                              {copiedId === msg.id ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                              {copiedId === msg.id ? 'Copied' : 'Copy'}
                            </button>
                            <button
                              className="msg-action"
                              onClick={() => handleRegenerate(msg.id)}
                              disabled={isStreaming}
                              aria-label="Regenerate answer"
                            >
                              <RefreshCw className="h-3 w-3" />
                              <span className="hidden sm:inline">Regenerate</span>
                            </button>
                            <button
                              className="msg-action"
                              data-active={feedback[msg.id] === 'up'}
                              onClick={() => handleFeedback(msg.id, 'up')}
                              aria-label="Helpful"
                              aria-pressed={feedback[msg.id] === 'up'}
                            >
                              <ThumbsUp className="h-3 w-3" />
                            </button>
                            <button
                              className="msg-action"
                              data-active={feedback[msg.id] === 'down'}
                              onClick={() => handleFeedback(msg.id, 'down')}
                              aria-label="Not helpful"
                              aria-pressed={feedback[msg.id] === 'down'}
                            >
                              <ThumbsDown className="h-3 w-3" />
                            </button>
                          </div>
                          <span
                            className="flex-shrink-0 text-[10px] uppercase tracking-widest opacity-40"
                            style={{ fontFamily: 'var(--font-ui)', color: '#7c3aed' }}
                          >
                            {new Date(msg.timestamp || Date.now()).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>
                      )}
                    </div>

                    {!msg.pending && (
                      <ProvenanceLine
                        texts={msg.sourcesUsed}
                        gurujiVoice={msg.gurujiVoiceUsed}
                        quality={msg.groundingQuality}
                      />
                    )}

                    {sources.length > 0 && (
                      <SourcesBlock sources={sources} onSourceClick={onSourceClick} msgId={msg.id} />
                    )}

                    {/* Contextual follow-up pills — only under the freshest answer,
                        so the seeker can continue with one tap (never a dead end). */}
                    {!msg.pending &&
                      !isStreaming &&
                      msg.id === messages[messages.length - 1]?.id &&
                      msg.id in followups && (
                        <FollowupPills
                          items={followups[msg.id]}
                          onPick={(q) => handleSendMessage(q)}
                          label={getTranslation(language, "ui.follow_up")}
                        />
                      )}
                  </div>
                </motion.div>
              );
            })}
            </AnimatePresence>

            {/* Trailing breath — enough room for the newest question to glide up
                without stranding a short answer over a half-screen of empty void
                (the jarring "scroll-up" format). Was 70vh; eased to 34vh so the
                answer card stays seated in view. (owner direction 2026-06-28) */}
            {messages.length > 0 && (
              <div aria-hidden="true" style={{ height: "34vh" }} />
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* "Jump to latest" pill retired — reading is now top-anchored, not
          tail-chasing. The newest question rests at the top; the answer flows
          down beneath it. */}

      <div
        className="chat-input-bar relative z-20 flex flex-shrink-0 flex-col items-center px-4 sm:px-6"
        style={{
          // Empty state: the footer is part of the centred group, so it needs no
          // scrim or keyboard padding. Conversation view: bottom-pinned, so fade
          // the content scrolling behind it and track the keyboard on mobile.
          background: messages.length === 0
            ? 'transparent'
            : 'linear-gradient(to top, rgba(0,0,0,0.92) 45%, rgba(0,0,0,0.55) 78%, transparent)',
          paddingTop: messages.length === 0 ? 6 : 12,
          paddingBottom: messages.length > 0 && visualViewportHeight != null && typeof window !== 'undefined' && window.innerWidth < 768
            ? Math.max(20, (window.innerHeight - visualViewportHeight) + 20)
            : messages.length === 0 ? 10 : 32,
        }}
      >
        <div className="relative mx-auto flex w-full max-w-4xl flex-col gap-3">

          {/* Free-tier usage meter — hidden for Pro and guests */}
          {user && !isPro && profile?.plan === 'free' && (
            <div className="flex flex-col gap-1 px-1">
              <div className="flex items-center justify-between">
                <span
                  className="text-[11px]"
                  style={{
                    color: usagePct !== null && usagePct >= 90 ? '#7c3aed' : '#6b5a36',
                    fontFamily: 'var(--font-ui)',
                  }}
                >
                  {usagePct !== null
                    ? usagePct >= 100
                      ? 'Daily limit reached'
                      : `${usagePct}% of daily limit used`
                    : 'Free plan'}
                </span>
                <button
                  onClick={openPaywall}
                  className="text-[11px] text-[#7c3aed] hover:text-[#a78bfa] transition-colors"
                  style={{ fontFamily: 'var(--font-ui)' }}
                >
                  Upgrade for unlimited →
                </button>
              </div>
              {usagePct !== null && usagePct > 0 && (
                <div className="h-0.5 rounded-full overflow-hidden" style={{ background: 'rgba(124,58,237,0.1)' }}>
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{
                      width: `${usagePct}%`,
                      background: usagePct >= 90 ? '#7c3aed' : 'rgba(124,58,237,0.45)',
                    }}
                  />
                </div>
              )}
            </div>
          )}

          {/* Sign-up nudge — visible to logged-out users after 3 assistant replies */}
          {!user && (
            <SignupNudge
              messageCount={messages.filter(m => m.role === 'assistant' && !m.pending && m.content && !m.content.startsWith('__RETRY__')).length}
              threshold={3}
              onSignIn={() => openSignInModal()}
            />
          )}

          {/* Voice listening overlay — the seeker SEES the mind is hearing them:
              a breathing indicator, the status line, the live transcript of their
              words (both in the display font), and a Cancel that discards it. */}
          {speech.listening && (
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-2 flex items-center gap-3 rounded-2xl px-4 py-3"
              style={{
                background: 'linear-gradient(180deg, rgba(124,58,237,0.09), rgba(124,58,237,0.04))',
                border: '1px solid rgba(124,58,237,0.30)',
                boxShadow: '0 0 26px rgba(124,58,237,0.12), inset 0 1px 0 rgba(255,255,255,0.04)',
              }}
              role="status"
            >
              <div style={{ flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5 }}>
                <motion.span
                  aria-hidden
                  style={{
                    width: liveTranscript ? 13 : 11,
                    height: liveTranscript ? 13 : 11,
                    borderRadius: '9999px',
                    background: '#7c3aed',
                    boxShadow: liveTranscript ? '0 0 14px rgba(124,58,237,0.8)' : '0 0 10px rgba(124,58,237,0.6)',
                  }}
                  animate={reducedMotion ? {} : { scale: [1, 1.55, 1], opacity: [1, 0.45, 1] }}
                  transition={{ duration: liveTranscript ? 0.9 : 1.4, repeat: Infinity, ease: 'easeInOut' }}
                />
                {/* Bars driven by the seeker's ACTUAL voice amplitude (Web Audio
                    AnalyserNode). On native iOS (WKWebView, where getUserMedia
                    can't coexist with SFSpeechRecognizer) MicWaveform degrades to
                    a sine-timer shimmer. Suppressed under reduced-motion — the
                    live transcript text is the voice-activity cue there. */}
                <MicWaveform active={!!liveTranscript && !reducedMotion} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                {/* Only the stable two-state label is announced. The live
                    transcript below changes many times a second; left in the
                    live region it floods the screen reader, so it's aria-hidden
                    and the label carries the single spoken cue. */}
                <div
                  aria-live="polite"
                  aria-atomic="true"
                  style={{ fontFamily: 'var(--font-display)', fontSize: '0.85rem', letterSpacing: '0.06em', color: '#7c3aed' }}
                >
                  {liveTranscript ? 'Listening…' : 'Speak now'}
                </div>
                {liveTranscript && (
                  <div
                    aria-hidden
                    style={{
                      fontFamily: 'var(--font-display)',
                      fontSize: 'clamp(1.05rem, 4vw, 1.28rem)',
                      color: '#a78bfa',
                      lineHeight: 1.4,
                      marginTop: 4,
                      textShadow: '0 0 12px rgba(124,58,237,0.20)',
                      display: '-webkit-box',
                      WebkitLineClamp: 3,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                    }}
                  >
                    {liveTranscript}
                  </div>
                )}
              </div>
              <button
                type="button"
                onClick={() => { playClick(); cancelDictation(); }}
                aria-label="Cancel voice input"
                className="flex-shrink-0 rounded-full px-3.5 py-1.5 text-[12px] transition-all hover:brightness-110"
                style={{
                  fontFamily: 'var(--font-ui)',
                  letterSpacing: '0.04em',
                  color: '#e2e8f0',
                  background: 'rgba(126,146,184,0.12)',
                  border: '1px solid rgba(126,146,184,0.32)',
                }}
              >
                Cancel
              </button>
            </motion.div>
          )}

          {voiceError && (
            <div
              className="mb-2 flex items-center gap-2 rounded-2xl px-3 py-2 text-[12px]"
              style={{ background: 'rgba(124,58,237,0.06)', border: '1px solid rgba(124,58,237,0.22)', color: '#7c3aed' }}
              role="alert"
            >
              <span style={{ flex: 1 }}>{voiceError}</span>
              <button
                type="button"
                onClick={() => setVoiceError(null)}
                aria-label="Dismiss"
                style={{ color: '#7e92b8', lineHeight: 1 }}
              >
                ✕
              </button>
            </div>
          )}

          <div
            className="relative rounded-[1.75rem] transition-all duration-200 focus-within:border-[#7c3aed]/45 focus-within:shadow-[0_0_0_1px_rgba(124,58,237,0.18),0_0_34px_rgba(124,58,237,0.16)]"
            style={{
             background: 'linear-gradient(180deg, #161618, #0d0d0f)',
             border: input.trim()
               ? '1px solid rgba(124,58,237,0.35)'
               : '1px solid rgba(124,58,237,0.20)',
             boxShadow: input.trim()
               ? '0 12px 44px rgba(0,0,0,0.5), 0 0 24px rgba(124,58,237,0.10), inset 0 1px 0 rgba(255,255,255,0.045)'
               : '0 12px 44px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.045)',
             transition: 'border-color 0.4s ease, box-shadow 0.4s ease',
            }}
          >
            <div className="flex items-end gap-1.5 p-2">

              {/* Voice playback toggle — streams TTS in sync with answer */}
              <button
                type="button"
                onClick={toggleVoice}
                title={voiceEnabled ? "Voice ON — click to mute" : "Voice OFF — click to hear the answer spoken"}
                aria-label="Toggle voice playback"
                className="hidden h-9 w-9 flex-shrink-0 items-center justify-center rounded-2xl transition-all duration-200 sm:flex"
                style={{
                  background: voiceEnabled ? 'rgba(124,58,237,0.18)' : 'transparent',
                  border: voiceEnabled ? '1px solid rgba(124,58,237,0.45)' : '1px solid transparent',
                  color: voiceEnabled ? '#7c3aed' : '#4a3a1f',
                  boxShadow: voiceEnabled ? '0 0 12px rgba(124,58,237,0.18)' : 'none',
                }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  {voiceEnabled ? (
                    <>
                      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
                      <path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
                      <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
                    </>
                  ) : (
                    <>
                      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
                      <line x1="23" y1="9" x2="17" y2="15"/>
                      <line x1="17" y1="9" x2="23" y2="15"/>
                    </>
                  )}
                </svg>
              </button>

              {/* Socratic / dialectic mode toggle — one-shot per message, auto-resets after send */}
              <button
                type="button"
                onClick={() => setSocraticMode(v => !v)}
                title={socraticMode ? "Socratic challenge ON — Guruji will question your premise" : "Activate Socratic challenge — Guruji questions your assumptions"}
                aria-label="Toggle Socratic challenge mode"
                className="hidden h-9 w-9 flex-shrink-0 items-center justify-center rounded-2xl transition-all duration-200 sm:flex"
                style={{
                  background: socraticMode ? 'rgba(124,58,237,0.18)' : 'transparent',
                  border: socraticMode ? '1px solid rgba(124,58,237,0.45)' : '1px solid transparent',
                  color: socraticMode ? '#7c3aed' : '#4a3a1f',
                  boxShadow: socraticMode ? '0 0 12px rgba(124,58,237,0.18)' : 'none',
                }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <circle cx="12" cy="12" r="10"/>
                  <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
                  <path d="M12 17h.01"/>
                </svg>
              </button>

              {/* Voice input (speech-to-text) — only shown when the browser supports it */}
              {speech.supported && (
                <button
                  type="button"
                  onClick={toggleDictation}
                  title={speech.listening ? "Listening… tap to stop" : "Speak your question"}
                  aria-label={speech.listening ? "Stop voice input" : "Start voice input"}
                  aria-pressed={speech.listening}
                  className="relative hidden h-9 w-9 flex-shrink-0 items-center justify-center rounded-2xl transition-all duration-200 sm:flex"
                  style={{
                    background: speech.listening ? 'rgba(124,58,237,0.18)' : 'transparent',
                    border: speech.listening ? '1px solid rgba(124,58,237,0.45)' : '1px solid transparent',
                    color: speech.listening ? '#7c3aed' : '#4a3a1f',
                    boxShadow: speech.listening ? '0 0 12px rgba(124,58,237,0.18)' : 'none',
                  }}
                >
                  {speech.listening && (
                    <span
                      className="absolute inset-0 rounded-2xl animate-ping"
                      style={{ background: 'rgba(124,58,237,0.18)' }}
                      aria-hidden="true"
                    />
                  )}
                  <Mic className="h-4 w-4 relative" />
                </button>
              )}

              {/* Texts shortcut — open your Workspace shelf, or add a document to read */}
              <div style={{ position: 'relative' }} className="flex-shrink-0">
                <input
                  ref={docInputRef}
                  type="file"
                  accept=".pdf,.docx"
                  style={{ display: 'none' }}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) handleDocUpload(f);
                    e.target.value = "";
                  }}
                />
                <button
                  type="button"
                  onClick={() => setTextsMenuOpen(v => !v)}
                  title="Your texts — open your shelf or add a document"
                  aria-label="Open texts menu"
                  aria-expanded={textsMenuOpen}
                  className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-2xl transition-all duration-200"
                  style={{
                    background: textsMenuOpen ? 'rgba(124,58,237,0.18)' : 'transparent',
                    border: textsMenuOpen ? '1px solid rgba(124,58,237,0.45)' : '1px solid transparent',
                    color: textsMenuOpen ? '#7c3aed' : '#4a3a1f',
                    boxShadow: textsMenuOpen ? '0 0 12px rgba(124,58,237,0.18)' : 'none',
                  }}
                >
                  {docUploading ? (
                    <svg className="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                  ) : (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
                  )}
                </button>

                {textsMenuOpen && (
                  <>
                    <div
                      onClick={() => setTextsMenuOpen(false)}
                      style={{ position: 'fixed', inset: 0, zIndex: 40 }}
                      aria-hidden="true"
                    />
                    <div
                      role="menu"
                      style={{
                        position: 'absolute', bottom: 'calc(100% + 10px)', left: 0, zIndex: 50,
                        width: 234, background: '#1b1626',
                        border: '0.5px solid rgba(184,137,59,0.35)', borderRadius: 14,
                        padding: 7, boxShadow: '0 8px 28px rgba(0,0,0,0.55)',
                      }}
                    >
                      <button
                        type="button"
                        role="menuitem"
                        onClick={() => { setTextsMenuOpen(false); router.push('/workspace'); }}
                        className="flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left transition-colors"
                        style={{ background: 'transparent' }}
                        onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(124,58,237,0.10)'; }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
                      >
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m16 6 4 14"/><path d="M12 6v14"/><path d="M8 8v12"/><path d="M4 4v16"/></svg>
                        <span style={{ lineHeight: 1.25 }}>
                          <span style={{ display: 'block', fontSize: 13, color: '#e2e8f0' }}>Open my texts</span>
                          <span style={{ display: 'block', fontSize: 11, color: '#7e92b8' }}>your uploaded shelf</span>
                        </span>
                      </button>
                      <div style={{ height: '0.5px', background: 'rgba(184,137,59,0.22)', margin: '2px 6px' }} />
                      <button
                        type="button"
                        role="menuitem"
                        onClick={() => { setTextsMenuOpen(false); docInputRef.current?.click(); }}
                        className="flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left transition-colors"
                        style={{ background: 'transparent' }}
                        onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(124,58,237,0.10)'; }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
                      >
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v5h5"/><path d="M12 11v6"/><path d="M9 14h6"/></svg>
                        <span style={{ lineHeight: 1.25 }}>
                          <span style={{ display: 'block', fontSize: 13, color: '#e2e8f0' }}>Add a document</span>
                          <span style={{ display: 'block', fontSize: 11, color: '#7e92b8' }}>PDF or Word — upload and read</span>
                        </span>
                      </button>

                      {/* Mobile-only: the secondary toggles that are hidden from
                          the inline composer below `sm` fold in here, so a phone
                          user keeps voice playback + Socratic — one tap deeper.
                          The menu stays open on toggle so the On/Off state is seen. */}
                      <div className="sm:hidden">
                        <div style={{ height: '0.5px', background: 'rgba(184,137,59,0.22)', margin: '2px 6px' }} />
                        <button
                          type="button"
                          role="menuitemcheckbox"
                          aria-checked={voiceEnabled}
                          onClick={() => toggleVoice()}
                          className="flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left transition-colors"
                          style={{ background: 'transparent' }}
                          onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(124,58,237,0.10)'; }}
                          onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
                        >
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={voiceEnabled ? '#7c3aed' : '#a78bfa'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
                          <span style={{ lineHeight: 1.25, flex: 1 }}>
                            <span style={{ display: 'block', fontSize: 13, color: '#e2e8f0' }}>Voice playback</span>
                            <span style={{ display: 'block', fontSize: 11, color: '#7e92b8' }}>{voiceEnabled ? 'On — the answer is spoken' : 'Off — hear the answer aloud'}</span>
                          </span>
                          <span style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.12em', color: voiceEnabled ? '#7c3aed' : '#7c3aed' }}>{voiceEnabled ? 'On' : 'Off'}</span>
                        </button>
                        <button
                          type="button"
                          role="menuitemcheckbox"
                          aria-checked={socraticMode}
                          onClick={() => setSocraticMode(v => !v)}
                          className="flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left transition-colors"
                          style={{ background: 'transparent' }}
                          onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(124,58,237,0.10)'; }}
                          onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
                        >
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={socraticMode ? '#7c3aed' : '#a78bfa'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/></svg>
                          <span style={{ lineHeight: 1.25, flex: 1 }}>
                            <span style={{ display: 'block', fontSize: 13, color: '#e2e8f0' }}>Socratic challenge</span>
                            <span style={{ display: 'block', fontSize: 11, color: '#7e92b8' }}>{socraticMode ? 'On — your premise is questioned' : 'Off — question my premise back'}</span>
                          </span>
                          <span style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.12em', color: socraticMode ? '#7c3aed' : '#7c3aed' }}>{socraticMode ? 'On' : 'Off'}</span>
                        </button>
                      </div>
                    </div>
                  </>
                )}
              </div>

              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onFocus={() => setIsInputFocused(true)}
                onBlur={() => {
                  setTimeout(() => setIsInputFocused(false), 200);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey && chatPrefs.enterToSend) {
                    e.preventDefault();
                    handleSendMessage();
                  } else if (e.key === "ArrowUp") {
                    if (commandHistory && commandHistory.length > 0) {
                      e.preventDefault();
                      const newIndex = historyIndex < commandHistory.length - 1 ? historyIndex + 1 : historyIndex;
                      setHistoryIndex(newIndex);
                      setInput(commandHistory[newIndex]);
                    }
                  } else if (e.key === "ArrowDown") {
                    if (historyIndex > 0) {
                      e.preventDefault();
                      const newIndex = historyIndex - 1;
                      setHistoryIndex(newIndex);
                      setInput(commandHistory[newIndex]);
                    } else if (historyIndex === 0) {
                      e.preventDefault();
                      setHistoryIndex(-1);
                      setInput("");
                    }
                  }
                }}
                placeholder={isPro ? "" : getTranslation(language, "ui.ask_anything")}
                className="flex-1 resize-none border-none bg-transparent px-1 py-2.5 text-base focus:outline-none focus:ring-0"
                style={{
                  fontFamily: 'var(--font-body)',
                  color: input.trim() ? '#a78bfa' : '#e2e8f0',
                  caretColor: '#7c3aed',
                  textShadow: input.trim() ? '0 0 8px rgba(124,58,237,0.15)' : 'none',
                  transition: 'color 0.3s ease, text-shadow 0.3s ease',
                }}
                rows={1}
              />

              {!isStreaming && (
                <motion.button
                  type="button"
                  onClick={() => {
                    playClick();
                    if (!speech.supported) {
                      setVoiceError("Voice input isn't available here. Use Chrome on http://localhost (or the app) and allow the microphone.");
                      return;
                    }
                    toggleDictation();
                  }}
                  whileTap={{ scale: 0.9 }}
                  aria-label={speech.listening ? "Stop dictation" : "Dictate"}
                  className="relative mb-0.5 flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full transition-all sm:hidden"
                  style={{
                    background: speech.listening
                      ? "linear-gradient(135deg, #a78bfa, #7c3aed)"
                      : "transparent",
                    color: speech.listening ? "#1a1206" : "#7c3aed",
                    border: speech.listening ? "none" : "1px solid rgba(124,58,237,0.28)",
                    boxShadow: speech.listening ? "0 0 14px rgba(124,58,237,0.35)" : "none",
                    opacity: speech.supported ? 1 : 0.5,
                  }}
                >
                  {speech.listening && <span className="mic-sonar" />}
                  <Mic className="h-5 w-5" strokeWidth={2.2} />
                </motion.button>
              )}

              <motion.button
                type="button"
                onClick={() => {
                  playClick();
                  isStreaming ? handleStop() : handleSendMessage();
                }}
                disabled={!isStreaming && !input.trim()}
                whileTap={{ scale: 0.9 }}
                aria-label={isStreaming ? "Stop generating" : "Send message"}
                className="mb-0.5 mr-0.5 flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full transition-all disabled:cursor-not-allowed disabled:opacity-30 disabled:shadow-none"
                style={{
                  background: isStreaming
                    ? "linear-gradient(135deg, #241a10, #15100b)"
                    : "linear-gradient(135deg, #a78bfa, #7c3aed)",
                  color: isStreaming ? "#7c3aed" : "#1a1206",
                  border: isStreaming ? "1px solid rgba(124,58,237,0.4)" : "none",
                  boxShadow: isStreaming
                    ? "none"
                    : "0 6px 18px rgba(124,58,237,0.35), 0 0 14px rgba(124,58,237,0.3)",
                }}
              >
                <AnimatePresence mode="wait" initial={false}>
                  {isStreaming ? (
                    <motion.span
                      key="stop"
                      initial={{ scale: 0.5, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      exit={{ scale: 0.5, opacity: 0 }}
                      transition={{ duration: 0.14 }}
                    >
                      <Square className="h-3.5 w-3.5 fill-current" />
                    </motion.span>
                  ) : (
                    <motion.span
                      key="send"
                      initial={{ scale: 0.5, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      exit={{ scale: 0.5, opacity: 0 }}
                      transition={{ duration: 0.14 }}
                    >
                      <ArrowUp className="h-5 w-5" strokeWidth={2.6} />
                    </motion.span>
                  )}
                </AnimatePresence>
              </motion.button>
            </div>
          </div>

          <AnimatePresence>
            {messages.length === 0 && (
              <motion.div 
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 15 }}
                transition={{ delay: 0.1, duration: 0.5 }}
                className="flex w-full flex-wrap justify-center gap-2.5 opacity-85 transition-opacity hover:opacity-100"
              >
                {/* Live suggestion pipeline — compact, topic-first cards drawn from
                    the user's own history + current trends (`/api/guru-suggestions`).
                    This is the primary empty-state element for the unified chat.
                    Pro users with history see personalized "For you" chips. */}
                  <div className="mx-auto flex w-full max-w-2xl flex-col gap-2">
                    <div className="flex items-center justify-between px-0.5">
                      <span
                        className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.22em]"
                        style={{ fontFamily: 'var(--font-ui)', color: personalized ? '#7c3aed' : '#7c3aed' }}
                      >
                        {personalized && <Sparkles className="h-3 w-3" style={{ color: '#7c3aed' }} />}
                        {getTranslation(language, personalized ? 'ui.for_you' : 'ui.trending_today')}
                      </span>
                      <button
                        onClick={() => fetchGuruSuggestions(true)}
                        disabled={suggestionsLoading}
                        className="rounded-full p-1.5 transition-colors hover:bg-white/10 disabled:opacity-40"
                        style={{ color: '#7c3aed' }}
                        aria-label="Refresh suggestions"
                        title="Refresh suggestions"
                      >
                        <RefreshCw className={`h-3.5 w-3.5 ${suggestionsLoading ? 'animate-spin' : ''}`} />
                      </button>
                    </div>

                    {(() => {
                      const cm: Record<string, { dot: string; border: string; text: string }> = {
                        saffron: { dot: '#7c3aed', border: 'rgba(124,58,237,0.22)', text: '#a78bfa' },
                        gold:    { dot: '#7c3aed', border: 'rgba(124,58,237,0.22)', text: '#e8c45a' },
                        blue:    { dot: '#7e92b8', border: 'rgba(126,146,184,0.22)', text: '#9fb2d6' },
                      };
                      return (
                        <>
                          {/* Mobile: compact chips — topic label only, all suggestions visible */}
                          <div className="flex flex-wrap gap-1.5 sm:hidden">
                            {guruSuggestions.map((s, idx) => {
                              const c = cm[s.color] || cm.saffron;
                              return (
                                <motion.button
                                  key={`chip-${idx}`}
                                  initial={{ opacity: 0, scale: 0.9 }}
                                  animate={{ opacity: 1, scale: 1 }}
                                  whileTap={tap}
                                  transition={{ delay: idx * 0.05, ...transitionSoft }}
                                  onClick={() => handleSendMessage(s.prompt)}
                                  className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[11px] font-medium transition-all active:scale-95"
                                  style={{ background: 'rgba(255,255,255,0.04)', border: `1px solid ${c.border}`, color: c.text, fontFamily: 'var(--font-body)' }}
                                >
                                  <span className="h-1.5 w-1.5 flex-shrink-0 rounded-full" style={{ background: c.dot, boxShadow: `0 0 6px ${c.dot}` }} />
                                  {s.topic}
                                </motion.button>
                              );
                            })}
                          </div>

                          {/* Desktop: full cards — topic + full prompt text */}
                          <div className="hidden sm:flex sm:flex-col sm:gap-2">
                            {guruSuggestions.map((s, idx) => {
                              const c = cm[s.color] || cm.saffron;
                              return (
                                <motion.button
                                  key={`card-${idx}`}
                                  initial={{ opacity: 0, y: reducedMotion ? 0 : 8 }}
                                  animate={{ opacity: 1, y: 0 }}
                                  whileTap={tap}
                                  transition={{ delay: idx * 0.07, ...transitionSoft }}
                                  onClick={() => handleSendMessage(s.prompt)}
                                  className="group w-full overflow-hidden rounded-2xl px-4 py-2.5 text-left transition-all duration-200 hover:-translate-y-0.5 hover:border-white/20"
                                  style={{ background: 'linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.015))', border: `1px solid ${c.border}`, fontFamily: 'var(--font-body)' }}
                                >
                                  <span className="flex items-center gap-2">
                                    <span className="h-1.5 w-1.5 flex-shrink-0 rounded-full" style={{ background: c.dot, boxShadow: `0 0 6px ${c.dot}` }} />
                                    <span className="truncate text-[13px] font-semibold" style={{ color: c.text }}>
                                      {s.topic}
                                    </span>
                                  </span>
                                  <span className="mt-0.5 block truncate-1 pl-3.5 text-[11px] leading-snug" style={{ color: '#998871' }}>
                                    {s.prompt}
                                  </span>
                                </motion.button>
                              );
                            })}
                          </div>
                        </>
                      );
                    })()}
                  </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
        {!user && (
          <button
            onClick={() => openSignInModal()}
            className="mt-3 mx-auto hidden sm:block text-center tracking-[0.06em] px-4 py-1.5 rounded-lg border transition-colors"
            style={{
              fontFamily: 'var(--font-ui)',
              fontSize: 12,
              color: '#e8b63f',
              borderColor: 'rgba(232,182,63,0.25)',
              background: 'rgba(232,182,63,0.05)',
            }}
          >
            {getTranslation(language, "ui.sign_in_up")}
          </button>
        )}
        {user && (
          <p
            className="mt-3 hidden text-center uppercase tracking-[0.18em] sm:block"
            style={{ fontFamily: 'var(--font-ui)', fontSize: 10, color: '#7c3aed' }}
          >
            {getTranslation(language, "ui.enter_hint")}
          </p>
        )}
      </div>

      {/* Sanskrit dictionary card — opened by tapping a highlighted term. */}
      <SanskritTermCard
        entry={activeTerm}
        language={language}
        onClose={() => setActiveTerm(null)}
        onAsk={(query) => {
          setActiveTerm(null);
          handleSendMessage(query);
        }}
      />
      </div>
    </div>
  );
}
