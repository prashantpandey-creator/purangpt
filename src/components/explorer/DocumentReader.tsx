"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, BookOpen, Loader2, Volume2, VolumeX, X } from "lucide-react";
import { cleanVerse } from "@/lib/verse";
import { VoiceEngine } from "@/lib/voiceEngine";
import { TTS_BASE } from "@/lib/ttsBase";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

// Sangama — "the confluence": the floor below which the corpus is NOT considered to
// genuinely recognize a passage, so the reader keeps an honest silence instead of
// manufacturing a faint bond. NOTE: e5-small similarities run high and compressed
// (same-corpus neighbors measure ~0.95–0.99), so this floor matters most for the
// real case — an uploaded English doc meeting the Sanskrit corpus, which scores
// lower. Start fail-safe low; raise it once real uploaded-doc scores are observed.
// This single number is the seeker's to tune: it sets where reverence ends.
const RECOGNITION_FLOOR = 0.75;

// ── Types ─────────────────────────────────────────────────────────────────

export interface Verse {
  id: string;
  text: string;
  purana?: string;
  chapter?: number | string;
  verse_range?: string;
  book_section?: string;
}

interface SimilarVerse {
  id: string;
  text: string;
  purana?: string;
  chapter?: number | string;
  verse_range?: string;
  score: number;
}

interface DocumentReaderProps {
  textId: string;
  textName: string;
  currentChapter: number;
  onChapterChange: (ch: number) => void;
  onBack: () => void;
  authHeadersFn?: () => Promise<Record<string, string>>;
  onChunkVisible?: (chunkId: string) => void;
}

// ── Shared sub-components ─────────────────────────────────────────────────

export function GlowDivider() {
  return (
    <div className="relative h-px w-full overflow-hidden my-10">
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-[#e8b63f]/30 to-transparent" />
    </div>
  );
}

export function YantraSpinner() {
  const ref = useRef<SVGCircleElement>(null);
  useEffect(() => {
    let frame: number;
    let angle = 0;
    function tick() {
      angle = (angle + 1.5) % 360;
      if (ref.current) {
        ref.current.setAttribute("transform", `rotate(${angle}, 24, 24)`);
      }
      frame = requestAnimationFrame(tick);
    }
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, []);

  return (
    <svg width="48" height="48" viewBox="0 0 48 48" className="opacity-60">
      <circle cx="24" cy="24" r="18" fill="none" stroke="#e8b63f" strokeWidth="1" strokeOpacity="0.25" />
      <circle
        ref={ref}
        cx="24" cy="6" r="3"
        fill="#e8b63f"
        fillOpacity="0.8"
        transform="rotate(0, 24, 24)"
      />
    </svg>
  );
}

// ── Main component ────────────────────────────────────────────────────────

export function DocumentReader({
  textId,
  textName,
  currentChapter,
  onChapterChange,
  onBack,
  authHeadersFn,
  onChunkVisible,
}: DocumentReaderProps) {
  const [verses, setVerses] = useState<Verse[]>([]);
  const [versesLoading, setVersesLoading] = useState(false);
  const [selectedVerse, setSelectedVerse] = useState<Verse | null>(null);
  const [similar, setSimilar] = useState<SimilarVerse[]>([]);
  const [similarLoading, setSimilarLoading] = useState(false);

  // ── Narration: the funguru voice reads the chapter aloud ──────────────────
  // The TTS server (Modal CUDA in prod, local in dev) scales to zero, so a cold
  // endpoint takes some seconds to wake. We pre-warm /health and surface a
  // "waking" state, so the reader never falls back silently to the robot voice.
  // guruji (chat/darshan) is unaffected — this is the settled narrator voice.
  const narratorRef = useRef<VoiceEngine | null>(null);
  const narrationToken = useRef(0); // cancels an in-flight warm-up on chapter change
  const [voiceState, setVoiceState] = useState<"idle" | "warming" | "narrating">("idle");

  const stopNarration = useCallback(() => {
    narrationToken.current++; // cancel any in-flight warm-up
    narratorRef.current?.disable();
    setVoiceState("idle");
  }, []);

  const startNarration = useCallback(async () => {
    if (!verses.length) return;
    const text = verses.map((v) => cleanVerse(v.text)).join("\n\n");
    if (!text.trim()) return;
    const token = ++narrationToken.current;
    narratorRef.current?.disable();
    setVoiceState("warming");
    // Wake a cold (scaled-to-zero) endpoint BEFORE the engine probes it, so its
    // short health timeout can't false-fall-back to the browser voice.
    try {
      await fetch(`${TTS_BASE}/health`, { signal: AbortSignal.timeout(90_000) });
    } catch {
      /* unreachable → the engine itself falls back to the browser voice */
    }
    if (token !== narrationToken.current) return; // chapter changed mid-warm — abort
    const eng = new VoiceEngine({ ttsBase: TTS_BASE, voice: "funguru" });
    narratorRef.current = eng;
    eng.enable();
    eng.pushToken(text);
    eng.flushFinal();
    setVoiceState("narrating");
  }, [verses]);

  // Auto-start when a chapter's passages arrive; stop on chapter change / unmount.
  // (Browsers may block audio autoplay without a gesture — the control below is
  // the reliable path: a tap unlocks audio and re-arms narration.)
  useEffect(() => {
    if (versesLoading || verses.length === 0) return;
    void startNarration();
    return () => {
      narrationToken.current++;
      narratorRef.current?.disable();
      setVoiceState("idle");
    };
  }, [verses, versesLoading, startNarration]);

  // Track visibility for progress
  const observerRef = useRef<IntersectionObserver | null>(null);
  const seenChunks = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!onChunkVisible) return;
    observerRef.current = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const id = entry.target.getAttribute("data-chunk-id");
            if (id && !seenChunks.current.has(id)) {
              seenChunks.current.add(id);
              // Debounce: mark as read after 3s of visibility
              const timer = setTimeout(() => {
                if (seenChunks.current.has(id)) {
                  onChunkVisible(id);
                }
              }, 3000);
              const el = entry.target;
              const cleanup = () => clearTimeout(timer);
              el.addEventListener("visibilitychange", cleanup, { once: true });
            }
          }
        });
      },
      { threshold: 0.5 },
    );
    return () => observerRef.current?.disconnect();
  }, [onChunkVisible]);

  useEffect(() => {
    if (!textId) return;
    setVersesLoading(true);
    setSelectedVerse(null);
    setSimilar([]);

    const doFetch = async () => {
      try {
        const headers = authHeadersFn ? await authHeadersFn() : {};
        const res = await fetch(
          `${API_URL}/api/chapters/${textId}/${currentChapter}?limit=200`,
          { headers },
        );
        if (!res.ok) throw new Error(`Chapter ${currentChapter} not found`);
        const d = await res.json();
        setVerses(d.verses || []);
      } catch {
        setVerses([]);
      } finally {
        setVersesLoading(false);
      }
    };
    doFetch();
  }, [textId, currentChapter, authHeadersFn]);

  function handleVerseClick(v: Verse) {
    if (selectedVerse?.id === v.id) {
      setSelectedVerse(null);
      setSimilar([]);
      return;
    }
    setSelectedVerse(v);
    setSimilar([]);
    setSimilarLoading(true);
    fetch(`${API_URL}/api/verses/${encodeURIComponent(v.id)}/similar?top_k=8`)
      .then((r) => r.json())
      .then((d) => setSimilar(d.similar || []))
      .catch(() => setSimilar([]))
      .finally(() => setSimilarLoading(false));
  }

  // ── Header ──────────────────────────────────────────────────────────────
  const header = (
    <header className="flex-shrink-0 border-b border-white/[0.06] bg-[#0A0810]/95 backdrop-blur px-4 py-3 md:px-8">
      <div className="flex items-center gap-4">
        <button
          onClick={onBack}
          className="rounded-full p-2 text-[#a38d7c] transition-colors hover:bg-white/5 hover:text-[#e8b63f]"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-base capitalize text-[#e2d4b2]" style={{ fontFamily: "var(--font-display)" }}>
            {textName}
          </h1>
          <p className="text-[10px] uppercase tracking-widest text-[#554336]" style={{ fontFamily: "var(--font-ui)" }}>
            Section {currentChapter} · {verses.length} passages
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => onChapterChange(Math.max(1, currentChapter - 1))}
            className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-[#a38d7c] hover:border-[#e8b63f]/30 hover:text-[#e8b63f] transition-colors disabled:opacity-30"
            disabled={currentChapter <= 1}
          >
            ← Prev
          </button>
          <span className="text-xs text-[#554336] tabular-nums" style={{ fontFamily: "var(--font-ui)" }}>
            §{currentChapter}
          </span>
          <button
            onClick={() => onChapterChange(currentChapter + 1)}
            className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-[#a38d7c] hover:border-[#e8b63f]/30 hover:text-[#e8b63f] transition-colors"
          >
            Next →
          </button>
        </div>
      </div>
    </header>
  );

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <div className="flex h-full flex-col bg-[#0A0810]">
      {header}
      {verses.length > 0 && (
        <button
          onClick={() => (voiceState === "idle" ? void startNarration() : stopNarration())}
          className="fixed bottom-6 right-6 z-30 flex items-center gap-2 rounded-full border border-[#e8b63f]/30 bg-[#0A0810]/90 px-4 py-2.5 text-xs text-[#e8b63f] shadow-[0_0_24px_rgba(232,182,63,0.14)] backdrop-blur transition-colors hover:bg-[#e8b63f]/[0.08]"
          style={{ fontFamily: "var(--font-ui)" }}
          aria-label={voiceState === "narrating" ? "Stop narration" : "Narrate this chapter"}
        >
          {voiceState === "warming" ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : voiceState === "narrating" ? (
            <VolumeX className="h-4 w-4" />
          ) : (
            <Volume2 className="h-4 w-4" />
          )}
          {voiceState === "warming"
            ? "Waking the narrator…"
            : voiceState === "narrating"
              ? "Stop"
              : "Narrate"}
        </button>
      )}
      <div className="flex min-h-0 flex-1">
        <main className="min-h-0 flex-1 overflow-y-auto px-4 py-6 md:px-8">
          {versesLoading ? (
            <div className="flex h-full items-center justify-center gap-4">
              <YantraSpinner />
              <p className="text-xs uppercase tracking-widest text-[#a38d7c]" style={{ fontFamily: "var(--font-ui)" }}>
                Loading section {currentChapter}…
              </p>
            </div>
          ) : verses.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-[#554336]">
              <BookOpen className="h-8 w-8 opacity-30" />
              <p className="text-sm" style={{ fontFamily: "var(--font-ui)" }}>
                No content for section {currentChapter}.
              </p>
              <button onClick={() => onChapterChange(currentChapter + 1)} className="text-xs text-[#e8b63f] hover:underline">
                Try Section {currentChapter + 1} →
              </button>
            </div>
          ) : (
            <div className="mx-auto max-w-3xl space-y-2 pb-24">
              <p className="mb-6 text-[10px] uppercase tracking-widest text-[#554336]" style={{ fontFamily: "var(--font-ui)" }}>
                {verses.length} passages · click any to find related ones across the corpus
              </p>
              {verses.map((v) => {
                const isSelected = selectedVerse?.id === v.id;
                return (
                  <button
                    key={v.id}
                    data-chunk-id={v.id}
                    ref={(el) => {
                      if (el && observerRef.current) observerRef.current.observe(el);
                    }}
                    onClick={() => handleVerseClick(v)}
                    className={`group w-full text-left rounded-2xl border px-5 py-4 transition-all ${
                      isSelected
                        ? "border-[#e8b63f]/50 bg-[#e8b63f]/[0.07] shadow-[0_0_20px_rgba(232,182,63,0.08)]"
                        : "border-white/[0.04] bg-[#141121] hover:border-[#e8b63f]/20 hover:bg-[#1a1630]"
                    }`}
                  >
                    <div className="flex items-start gap-4">
                      <span
                        className={`mt-0.5 flex-shrink-0 text-[10px] tabular-nums transition-colors ${
                          isSelected ? "text-[#e8b63f]" : "text-[#3d3226]"
                        }`}
                        style={{ fontFamily: "var(--font-ui)" }}
                      >
                        {v.verse_range || v.id.split("-").slice(-1)[0]}
                      </span>
                      <p
                        className={`whitespace-pre-line text-sm leading-7 transition-colors ${
                          isSelected ? "text-[#e2d4b2]" : "text-[#dbc2b0] group-hover:text-[#e2d4b2]"
                        }`}
                        style={{ fontFamily: "var(--font-body)" }}
                      >
                        {cleanVerse(v.text)}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </main>

        {/* Similarity panel */}
        <aside
          className={`flex-shrink-0 border-l border-white/[0.06] bg-[#0d0b14] transition-all duration-300 overflow-hidden ${
            selectedVerse ? "w-80 lg:w-96" : "w-0"
          }`}
        >
          {selectedVerse && (
            <div className="flex h-full flex-col">
              <div className="flex-shrink-0 border-b border-white/[0.06] p-4">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-[10px] uppercase tracking-widest text-[#e8b63f]" style={{ fontFamily: "var(--font-ui)" }}>
                    Recognition
                  </p>
                  <button
                    onClick={() => { setSelectedVerse(null); setSimilar([]); }}
                    className="rounded-full p-1 text-[#554336] hover:text-[#a38d7c] transition-colors"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
                <p className="text-xs text-[#554336]" style={{ fontFamily: "var(--font-body)" }}>
                  The texts that recognize this passage
                </p>
              </div>

              <div className="min-h-0 flex-1 overflow-y-auto p-3">
                {similarLoading ? (
                  <div className="flex h-full items-center justify-center">
                    <Loader2 className="h-5 w-5 animate-spin text-[#e8b63f]/40" />
                  </div>
                ) : similar.filter((sv) => sv.score >= RECOGNITION_FLOOR).length === 0 ? (
                  <div className="flex h-full items-center justify-center px-5 text-center text-xs leading-6 text-[#554336]" style={{ fontFamily: "var(--font-body)" }}>
                    This passage walks its own path — the corpus offers no strong echo here.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {similar.filter((sv) => sv.score >= RECOGNITION_FLOOR).map((sv) => (
                      <div
                        key={sv.id}
                        className="rounded-xl border border-white/[0.04] bg-[#141121] p-4 hover:border-[#e8b63f]/20 transition-colors"
                      >
                        <div className="mb-2 flex items-center justify-between gap-2">
                          <p className="text-[10px] uppercase tracking-widest text-[#e8b63f] truncate" style={{ fontFamily: "var(--font-ui)" }}>
                            {sv.purana || "Unknown"}
                            {sv.chapter ? ` · §${sv.chapter}` : ""}
                            {sv.verse_range ? ` · ${sv.verse_range}` : ""}
                          </p>
                          <span className="flex-shrink-0 text-[10px] text-[#3d3226] tabular-nums" style={{ fontFamily: "var(--font-ui)" }}>
                            {Math.round(sv.score * 100)}%
                          </span>
                        </div>
                        <p className="text-xs leading-6 text-[#a38d7c] line-clamp-4" style={{ fontFamily: "var(--font-body)" }}>
                          {cleanVerse(sv.text)}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
