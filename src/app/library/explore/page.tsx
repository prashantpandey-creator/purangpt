"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowLeft, BookOpen, ChevronRight, Loader2, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cleanVerse } from "@/lib/verse";
import { streamIlluminate } from "@/lib/api";
import { useLanguage } from "@/context/LanguageContext";
import { getTranslation } from "@/lib/i18n";

// On-theme markdown for the illuminated edition (Marcellus gold, ivory body).
const ILLUM_MD = {
  h1: (p: any) => <h2 className="mt-7 mb-2 text-lg text-[#f6d27a]" style={{ fontFamily: "var(--font-display)" }} {...p} />,
  h2: (p: any) => <h2 className="mt-7 mb-2 text-lg text-[#f6d27a]" style={{ fontFamily: "var(--font-display)" }} {...p} />,
  h3: (p: any) => <h3 className="mt-6 mb-1.5 text-base text-[#e8b63f]" style={{ fontFamily: "var(--font-display)" }} {...p} />,
  p: (p: any) => <p className="mb-3 leading-7 text-[#a99cb0]" style={{ fontFamily: "var(--font-body)" }} {...p} />,
  em: (p: any) => <em className="not-italic block leading-[1.85] text-[#e2d4b2]" style={{ fontFamily: "var(--font-display)", fontStyle: "italic" }} {...p} />,
  strong: (p: any) => <strong className="font-medium text-[#e8b63f]" {...p} />,
  li: (p: any) => <li className="mb-1 ml-5 list-disc leading-7 text-[#a99cb0]" style={{ fontFamily: "var(--font-body)" }} {...p} />,
  blockquote: (p: any) => <blockquote className="my-3 border-l-2 border-[#e8b63f]/40 pl-4 text-[#e2d4b2] italic" {...p} />,
};

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

// ── Types ─────────────────────────────────────────────────────────────────

interface FamousStory {
  title: string;
  chapter_hint: string;
  description: string;
}

interface EntryChapter {
  chapter_hint: string;
  label: string;
  for_reader: string;
}

interface GuideIntro {
  text_id: string;
  text_name: string;
  tagline: string;
  what_it_is: string;
  why_it_matters: string;
  famous_stories: FamousStory[];
  entry_chapters: EntryChapter[];
  one_line_pitch: string;
}

interface Verse {
  id: string;
  text: string;
  purana?: string;
  chapter?: number | string;
  verse_range?: string;
}

interface SimilarVerse {
  id: string;
  text: string;
  purana?: string;
  chapter?: number | string;
  verse_range?: string;
  score: number;
}

// ── Sub-components ────────────────────────────────────────────────────────

function GlowDivider() {
  return (
    <div className="relative h-px w-full overflow-hidden my-10">
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-[#e8b63f]/30 to-transparent" />
    </div>
  );
}

function YantraSpinner() {
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

// ── Main page ─────────────────────────────────────────────────────────────

type View = "entry" | "chapter" | "verse";

export default function ExplorePage() {
  const searchParams = useSearchParams();
  const idParam = searchParams.get("id") || "";
  const initialChapter = searchParams.get("chapter");
  // A citation deep-link arrives as ?verse={chunk_id} (no id/chapter). We resolve
  // the chunk server-side to discover its text + chapter, then land in it.
  const verseParam = searchParams.get("verse") || "";

  // textId is the value used to filter chapters (the chunk metadata "purana").
  // Seeded from ?id, or resolved from ?verse below.
  const [textId, setTextId] = useState<string>(idParam);

  const [view, setView] = useState<View>(
    initialChapter || verseParam ? "chapter" : "entry"
  );

  // Entry screen state
  const [intro, setIntro] = useState<GuideIntro | null>(null);
  const [introLoading, setIntroLoading] = useState(false);
  const [introError, setIntroError] = useState<string | null>(null);

  // Chapter / verse state
  const [verses, setVerses] = useState<Verse[]>([]);
  const [versesLoading, setVersesLoading] = useState(false);
  // Illuminate: the AI reading edition (verse · clean Sanskrit · translation).
  const { language } = useLanguage();
  const [illuminate, setIlluminate] = useState(false);
  const [illumMd, setIllumMd] = useState("");
  const [illuminating, setIlluminating] = useState(false);
  const [illumErr, setIllumErr] = useState("");
  const illumKeyRef = useRef("");
  // The corpus is indexed flat: every verse sits under chapter 0 (the real
  // chapter lives only inside the verse marker, not in metadata). So 0 — not 1 —
  // is the body of the text. Default there.
  const [currentChapter, setCurrentChapter] = useState<number>(
    initialChapter ? parseInt(initialChapter) : 0
  );

  // Similarity panel state
  const [selectedVerse, setSelectedVerse] = useState<Verse | null>(null);
  const [similar, setSimilar] = useState<SimilarVerse[]>([]);
  const [similarLoading, setSimilarLoading] = useState(false);

  // Deep-link target: the chunk_id to scroll to + highlight once a chapter loads.
  const [targetVerseId, setTargetVerseId] = useState<string>(verseParam);
  const verseRefs = useRef<Record<string, HTMLButtonElement | null>>({});

  const textName = intro?.text_name || textId.replace(/[_-]/g, " ");

  // ── Resolve a citation deep-link (?verse=chunk_id) ──────────────────────
  useEffect(() => {
    if (!verseParam || textId) return; // only when arriving via verse with no id
    fetch(`${API_URL}/api/verses/${encodeURIComponent(verseParam)}`)
      .then((r) => {
        if (!r.ok) throw new Error("Verse not found");
        return r.json();
      })
      .then((chunk) => {
        const resolvedText = chunk.purana || chunk.doc_id || "";
        // Preserve a real chapter 0 — `|| 1` was turning the valid flat-text
        // chapter into a non-existent "chapter 1" and the deep-link never landed.
        const _pc = parseInt(String(chunk.chapter));
        const ch = Number.isNaN(_pc) ? 0 : _pc;
        if (resolvedText) {
          setTextId(resolvedText);
          setCurrentChapter(ch);
          setView("chapter");
          setTargetVerseId(verseParam);
        }
      })
      .catch(() => {});
  }, [verseParam, textId]);

  // ── Fetch intro ────────────────────────────────────────────────────────
  useEffect(() => {
    if (!textId) return;
    setIntroLoading(true);
    fetch(`${API_URL}/api/explore/${textId}/intro`)
      .then((r) => {
        if (!r.ok) throw new Error("Guide unavailable");
        return r.json();
      })
      .then((d) => setIntro(d))
      .catch((e) => setIntroError(e.message))
      .finally(() => setIntroLoading(false));
  }, [textId]);

  // ── Fetch chapter verses ───────────────────────────────────────────────
  useEffect(() => {
    if (view !== "chapter" && view !== "verse") return;
    if (!textId) return;
    setVersesLoading(true);
    setSelectedVerse(null);
    setSimilar([]);
    // Send textId as-is — the slug from ?id ("bhagavata", "bhagavad_gita") OR the
    // metadata display name from a ?verse deep-link. The backend resolves BOTH:
    // slugs by chunk-id prefix (with audited remaps), display names by metadata.
    // (intro.text_name was wrong for ~5 texts whose display name carries a qualifier
    // — "Vishnu Purana" vs the indexed "Vishnu Purana (Critical Edition)".)
    fetch(`${API_URL}/api/chapters/${encodeURIComponent(textId)}/${currentChapter}?limit=200`)
      .then((r) => {
        if (!r.ok) throw new Error(`Chapter ${currentChapter} not found`);
        return r.json();
      })
      .then((d) => setVerses(d.verses || []))
      .catch(() => setVerses([]))
      .finally(() => setVersesLoading(false));
  }, [textId, currentChapter, view]);

  // ── Illuminate: stream the AI reading edition ───────────────────────────
  useEffect(() => {
    if (!illuminate || !textId || (view !== "chapter" && view !== "verse")) return;
    const key = `${textId}:${currentChapter}:${language}`;
    if (illumKeyRef.current === key && illumMd) return; // already have this one
    illumKeyRef.current = key;
    let cancelled = false;
    setIllumMd("");
    setIllumErr("");
    setIlluminating(true);
    (async () => {
      try {
        for await (const ev of streamIlluminate(textId, currentChapter, language)) {
          if (cancelled) return;
          if (ev.type === "token") setIllumMd((m) => m + (ev.content || ""));
          else if (ev.type === "error") { setIllumErr(ev.message || getTranslation(language, "reader.illuminate_failed")); break; }
          else if (ev.type === "done") break;
        }
      } catch (e: any) {
        if (!cancelled) setIllumErr(e?.message || getTranslation(language, "reader.illuminate_failed"));
      } finally {
        if (!cancelled) setIlluminating(false);
      }
    })();
    return () => { cancelled = true; };
    // illumMd intentionally NOT a dep: it mutates as tokens stream, and including
    // it re-runs the effect → the cleanup cancels its own stream after the first
    // token. The illumKeyRef guard already dedups across (text, chapter, language).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [illuminate, textId, currentChapter, language, view]);

  // ── Fetch similar verses ───────────────────────────────────────────────
  function selectVerse(v: Verse) {
    setSelectedVerse(v);
    setSimilar([]);
    setSimilarLoading(true);
    fetch(`${API_URL}/api/verses/${encodeURIComponent(v.id)}/similar?top_k=8`)
      .then((r) => r.json())
      .then((d) => setSimilar(d.similar || []))
      .catch(() => setSimilar([]))
      .finally(() => setSimilarLoading(false));
  }

  function handleVerseClick(v: Verse) {
    if (selectedVerse?.id === v.id) {
      setSelectedVerse(null);
      setSimilar([]);
      return;
    }
    selectVerse(v);
  }

  // ── Deep-link: once the target chapter's verses load, scroll to + select ─
  useEffect(() => {
    if (!targetVerseId || versesLoading || verses.length === 0) return;
    const match = verses.find((v) => v.id === targetVerseId);
    if (!match) {
      setTargetVerseId(""); // not in this chapter — give up quietly
      return;
    }
    selectVerse(match);
    // Wait a frame for the element to mount, then scroll it into view.
    const t = setTimeout(() => {
      verseRefs.current[targetVerseId]?.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
      setTargetVerseId(""); // consume — don't re-trigger on subsequent renders
    }, 120);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetVerseId, versesLoading, verses]);

  function enterChapter(ch: number) {
    setCurrentChapter(ch);
    setView("chapter");
  }

  // ── No text id ─────────────────────────────────────────────────────────
  // If a citation deep-link (?verse=) is still resolving, show a spinner
  // instead of the empty state.
  if (!textId) {
    if (verseParam) {
      return (
        <div className="flex h-full flex-col items-center justify-center gap-6 bg-[#0A0810]">
          <YantraSpinner />
          <p className="text-xs uppercase tracking-widest text-[#a38d7c]" style={{ fontFamily: "var(--font-ui)" }}>
            Opening the cited passage…
          </p>
        </div>
      );
    }
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 bg-[#0A0810] text-[#a38d7c]">
        <BookOpen className="h-10 w-10 opacity-30" />
        <p className="text-sm" style={{ fontFamily: "var(--font-ui)" }}>
          No text selected. Return to{" "}
          <Link href="/library" className="text-[#e8b63f] underline underline-offset-2">
            Library
          </Link>
          .
        </p>
      </div>
    );
  }

  // ── Shared header ──────────────────────────────────────────────────────
  const header = (
    <header className="flex-shrink-0 border-b border-white/[0.06] bg-[#0A0810]/95 backdrop-blur px-4 py-3 md:px-8">
      <div className="flex items-center gap-4">
        {view === "entry" ? (
          <Link
            href="/library"
            className="rounded-full p-2 text-[#a38d7c] transition-colors hover:bg-white/5 hover:text-[#e8b63f]"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
        ) : (
          <button
            onClick={() => setView("entry")}
            className="rounded-full p-2 text-[#a38d7c] transition-colors hover:bg-white/5 hover:text-[#e8b63f]"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
        )}
        <div className="min-w-0 flex-1">
          <h1
            className="truncate text-base font-bold capitalize text-[#e5e2e1]"
            style={{ fontFamily: "var(--font-display)" }}
          >
            {textName}
          </h1>
          <p
            className="text-[10px] uppercase tracking-widest text-[#554336]"
            style={{ fontFamily: "var(--font-ui)" }}
          >
            {view === "entry"
              ? "Guide · Entry Point"
              : view === "chapter"
              ? `${verses.length} verses`
              : `Verse Explorer`}
          </p>
        </div>
        {/* No chapter nav — the corpus is indexed flat (one body per text), so
            prev/next chapters point at nothing. Removed until the index is
            re-segmented from the verse markers (bhp_SS.CC.VVV). */}
      </div>
    </header>
  );

  // ── Entry view ─────────────────────────────────────────────────────────
  if (view === "entry") {
    return (
      <div className="flex h-full flex-col bg-[#0A0810]">
        {header}
        <main className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-4 py-10 pb-24 md:px-8">
            {introLoading && (
              <div className="flex flex-col items-center gap-6 py-20">
                <YantraSpinner />
                <p
                  className="text-xs uppercase tracking-widest text-[#a38d7c]"
                  style={{ fontFamily: "var(--font-ui)" }}
                >
                  The guide is reading the {textName}…
                </p>
              </div>
            )}

            {introError && (
              <div className="rounded-2xl border border-red-500/20 bg-red-500/10 p-5 text-sm text-red-400">
                {introError}
              </div>
            )}

            {intro && !introLoading && (
              <div className="space-y-10">
                {/* Tagline */}
                <div>
                  <p
                    className="text-[10px] uppercase tracking-widest text-[#e8b63f] mb-3"
                    style={{ fontFamily: "var(--font-ui)" }}
                  >
                    <Sparkles className="inline-block h-3 w-3 mr-1.5 mb-0.5" />
                    Guide Introduction
                  </p>
                  <h2
                    className="text-3xl md:text-4xl font-bold text-[#e2d4b2] leading-tight mb-4"
                    style={{ fontFamily: "var(--font-display)" }}
                  >
                    {intro.tagline}
                  </h2>
                  <p
                    className="text-base text-[#a38d7c] italic leading-relaxed"
                    style={{ fontFamily: "var(--font-body)" }}
                  >
                    "{intro.one_line_pitch}"
                  </p>
                </div>

                <GlowDivider />

                {/* What + Why */}
                <div className="grid md:grid-cols-2 gap-6">
                  <div className="rounded-2xl border border-white/[0.06] bg-[#141121] p-6">
                    <p
                      className="text-[10px] uppercase tracking-widest text-[#7e92b8] mb-3"
                      style={{ fontFamily: "var(--font-ui)" }}
                    >
                      What it is
                    </p>
                    <p
                      className="text-sm leading-7 text-[#dbc2b0]"
                      style={{ fontFamily: "var(--font-body)" }}
                    >
                      {intro.what_it_is}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-white/[0.06] bg-[#141121] p-6">
                    <p
                      className="text-[10px] uppercase tracking-widest text-[#7e92b8] mb-3"
                      style={{ fontFamily: "var(--font-ui)" }}
                    >
                      Why it matters today
                    </p>
                    <p
                      className="text-sm leading-7 text-[#dbc2b0]"
                      style={{ fontFamily: "var(--font-body)" }}
                    >
                      {intro.why_it_matters}
                    </p>
                  </div>
                </div>

                <GlowDivider />

                {/* Famous stories */}
                <div>
                  <p
                    className="text-[10px] uppercase tracking-widest text-[#e8b63f] mb-5"
                    style={{ fontFamily: "var(--font-ui)" }}
                  >
                    The Stories Worth Your Time
                  </p>
                  <div className="space-y-3">
                    {intro.famous_stories.map((story, i) => (
                      <button
                        key={i}
                        onClick={() => enterChapter(0)}
                        className="group w-full text-left rounded-2xl border border-white/[0.06] bg-[#141121] p-5 hover:border-[#e8b63f]/30 hover:bg-[#1a1630] transition-all"
                      >
                        <div className="flex items-start gap-4">
                          <span
                            className="mt-0.5 flex-shrink-0 text-[10px] tabular-nums text-[#554336]"
                            style={{ fontFamily: "var(--font-ui)" }}
                          >
                            {String(i + 1).padStart(2, "0")}
                          </span>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center justify-between gap-2 mb-1">
                              <h3
                                className="text-sm font-semibold text-[#e5e2e1] group-hover:text-[#f0cd80] transition-colors"
                                style={{ fontFamily: "var(--font-display)" }}
                              >
                                {story.title}
                              </h3>
                              <span
                                className="flex-shrink-0 text-[10px] text-[#554336]"
                                style={{ fontFamily: "var(--font-ui)" }}
                              >
                                {story.chapter_hint}
                              </span>
                            </div>
                            <p
                              className="text-xs leading-relaxed text-[#a38d7c]"
                              style={{ fontFamily: "var(--font-body)" }}
                            >
                              {story.description}
                            </p>
                          </div>
                          <ChevronRight className="h-4 w-4 flex-shrink-0 text-[#554336] group-hover:text-[#e8b63f] transition-colors" />
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                <GlowDivider />

                {/* Entry chapters */}
                <div>
                  <p
                    className="text-[10px] uppercase tracking-widest text-[#e8b63f] mb-5"
                    style={{ fontFamily: "var(--font-ui)" }}
                  >
                    Where to Enter
                  </p>
                  <div className="grid sm:grid-cols-3 gap-4">
                    {intro.entry_chapters.map((ec, i) => (
                      <button
                        key={i}
                        onClick={() => enterChapter(0)}
                        className="group rounded-2xl border border-white/[0.06] bg-[#141121] p-5 text-left hover:border-[#e8b63f]/30 hover:bg-[#1a1630] transition-all"
                      >
                        <p
                          className="text-[10px] uppercase tracking-widest text-[#e8b63f] mb-2"
                          style={{ fontFamily: "var(--font-ui)" }}
                        >
                          {ec.chapter_hint}
                        </p>
                        <h3
                          className="text-sm font-semibold text-[#e5e2e1] group-hover:text-[#f0cd80] mb-2 transition-colors"
                          style={{ fontFamily: "var(--font-display)" }}
                        >
                          {ec.label}
                        </h3>
                        <p
                          className="text-xs text-[#554336] leading-relaxed"
                          style={{ fontFamily: "var(--font-body)" }}
                        >
                          For {ec.for_reader}
                        </p>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Open the text body CTA */}
                <div className="pt-4 flex justify-center">
                  <button
                    onClick={() => enterChapter(0)}
                    className="rounded-full border border-[#e8b63f]/40 bg-[#e8b63f]/10 px-8 py-3 text-sm font-semibold text-[#f0cd80] hover:bg-[#e8b63f]/20 hover:border-[#e8b63f]/60 transition-all"
                    style={{ fontFamily: "var(--font-display)" }}
                  >
                    {getTranslation(language, "reader.begin_reading")} →
                  </button>
                </div>
              </div>
            )}

            {/* No intro yet — direct chapter entry */}
            {!intro && !introLoading && !introError && (
              <div className="flex flex-col items-center gap-6 py-20">
                <button
                  onClick={() => enterChapter(0)}
                  className="rounded-full border border-[#e8b63f]/40 bg-[#e8b63f]/10 px-8 py-3 text-sm font-semibold text-[#f0cd80] hover:bg-[#e8b63f]/20 transition-all"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  {getTranslation(language, "reader.begin_reading")}
                </button>
              </div>
            )}
          </div>
        </main>
      </div>
    );
  }

  // ── Chapter / Verse view ───────────────────────────────────────────────
  return (
    <div className="flex h-full flex-col bg-[#0A0810]">
      {header}

      <div className="flex min-h-0 flex-1">
        {/* Verse list */}
        <main className="min-h-0 flex-1 overflow-y-auto px-4 py-6 md:px-8">
          {versesLoading ? (
            <div className="flex h-full items-center justify-center gap-4">
              <YantraSpinner />
              <p
                className="text-xs uppercase tracking-widest text-[#a38d7c]"
                style={{ fontFamily: "var(--font-ui)" }}
              >
                Loading chapter {currentChapter}…
              </p>
            </div>
          ) : verses.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-[#554336]">
              <BookOpen className="h-8 w-8 opacity-30" />
              <p className="text-sm" style={{ fontFamily: "var(--font-ui)" }}>
                {getTranslation(language, "reader.no_indexed")}
              </p>
              <button
                onClick={() => setView("entry")}
                className="text-xs text-[#e8b63f] hover:underline"
              >
                ← {getTranslation(language, "reader.back_to_guide")}
              </button>
            </div>
          ) : (
            <div className="mx-auto max-w-3xl space-y-2 pb-24">
              <div className="mb-6 flex items-center justify-between gap-3">
                <p className="text-[10px] uppercase tracking-widest text-[#554336]" style={{ fontFamily: "var(--font-ui)" }}>
                  {illuminate ? getTranslation(language, "reader.illuminated_edition") : `${verses.length} ${getTranslation(language, "reader.verses_tap")}`}
                </p>
                <button
                  onClick={() => setIlluminate((v) => !v)}
                  className="flex flex-shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors"
                  style={illuminate
                    ? { background: "rgba(232,182,63,0.18)", borderColor: "rgba(232,182,63,0.5)", color: "#f6d27a", fontFamily: "var(--font-ui)" }
                    : { background: "transparent", borderColor: "rgba(232,182,63,0.3)", color: "#e8b63f", fontFamily: "var(--font-ui)" }}
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  {illuminate ? getTranslation(language, "reader.raw_text") : getTranslation(language, "reader.illuminate")}
                </button>
              </div>

              {illuminate && (
                <div className="pb-10">
                  {illuminating && !illumMd && (
                    <div className="flex items-center gap-3 py-6 text-sm text-[#a38d7c]" style={{ fontFamily: "var(--font-body)" }}>
                      <Loader2 className="h-4 w-4 animate-spin text-[#e8b63f]" />
                      Illuminating the verses…
                    </div>
                  )}
                  {illumErr && (
                    <div className="rounded-xl border border-red-500/20 bg-red-500/[0.06] p-4 text-sm text-red-300">{illumErr}</div>
                  )}
                  {illumMd && (
                    <article>
                      <ReactMarkdown remarkPlugins={[remarkGfm]} components={ILLUM_MD}>{illumMd}</ReactMarkdown>
                      {illuminating && <Loader2 className="mt-2 h-3 w-3 animate-spin text-[#7e92b8]" />}
                    </article>
                  )}
                </div>
              )}

              {!illuminate && verses.map((v) => {
                const isSelected = selectedVerse?.id === v.id;
                return (
                  <button
                    key={v.id}
                    ref={(el) => { verseRefs.current[v.id] = el; }}
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
                  <p
                    className="text-[10px] uppercase tracking-widest text-[#e8b63f]"
                    style={{ fontFamily: "var(--font-ui)" }}
                  >
                    {getTranslation(language, "reader.related_verses")}
                  </p>
                  <button
                    onClick={() => { setSelectedVerse(null); setSimilar([]); }}
                    className="rounded-full p-1 text-[#554336] hover:text-[#a38d7c] transition-colors"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
                <p
                  className="text-xs text-[#554336]"
                  style={{ fontFamily: "var(--font-body)" }}
                >
                  Semantically similar across the entire corpus
                </p>
              </div>

              <div className="min-h-0 flex-1 overflow-y-auto p-3">
                {similarLoading ? (
                  <div className="flex h-full items-center justify-center">
                    <Loader2 className="h-5 w-5 animate-spin text-[#e8b63f]/40" />
                  </div>
                ) : similar.length === 0 ? (
                  <div className="flex h-full items-center justify-center text-center text-xs text-[#3d3226]">
                    No similar verses found.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {similar.map((sv) => (
                      <div
                        key={sv.id}
                        className="rounded-xl border border-white/[0.04] bg-[#141121] p-4 hover:border-[#e8b63f]/20 transition-colors"
                      >
                        <div className="mb-2 flex items-center justify-between gap-2">
                          <p
                            className="text-[10px] uppercase tracking-widest text-[#e8b63f] truncate"
                            style={{ fontFamily: "var(--font-ui)" }}
                          >
                            {sv.purana || "Unknown"}
                            {sv.chapter ? ` · Ch. ${sv.chapter}` : ""}
                            {sv.verse_range ? ` · ${sv.verse_range}` : ""}
                          </p>
                          <span
                            className="flex-shrink-0 text-[10px] text-[#3d3226] tabular-nums"
                            style={{ fontFamily: "var(--font-ui)" }}
                          >
                            {Math.round(sv.score * 100)}%
                          </span>
                        </div>
                        <p
                          className="text-xs leading-6 text-[#a38d7c] line-clamp-4"
                          style={{ fontFamily: "var(--font-body)" }}
                        >
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
