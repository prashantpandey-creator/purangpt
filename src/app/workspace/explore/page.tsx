"use client";

import { useEffect, useState, useCallback } from "react";
import { BookOpen, Sparkles, ChevronRight, Compass, Loader2 } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { DocumentReader, GlowDivider, YantraSpinner } from "@/components/explorer/DocumentReader";
import { authHeaders } from "@/lib/api";
import { useLanguage } from "@/context/LanguageContext";
import { getTranslation } from "@/lib/i18n";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

// ── Types ─────────────────────────────────────────────────────────────────

interface KeySection {
  section_num: number;
  title: string;
  description: string;
}

interface EntryPoint {
  section_num: number;
  label: string;
  for_reader: string;
}

interface WorkspaceIntro {
  doc_id: string;
  doc_title: string;
  tagline: string;
  what_it_is: string;
  why_it_matters: string;
  key_sections: KeySection[];
  entry_points: EntryPoint[];
  one_line_pitch: string;
}

interface Thread {
  id: string;
  label: string;
  description: string;
  icon: string;
  section_sequence: number[];
}

interface ThreadMap {
  threads: Thread[];
}

type View = "entry" | "reading";

// ── Thread icon helper ────────────────────────────────────────────────────

const THREAD_ICONS: Record<string, React.ReactNode> = {
  book:      <BookOpen className="h-4 w-4" />,
  sparkles:  <Sparkles className="h-4 w-4" />,
  compass:   <Compass className="h-4 w-4" />,
  users:     <span className="text-sm">👥</span>,
  lightbulb: <span className="text-sm">💡</span>,
};

// ── Main page ─────────────────────────────────────────────────────────────

function WorkspaceExplorePage() {
  const searchParams = useSearchParams();
  const docId = searchParams.get("id") || "";

  const [view, setView] = useState<View>("entry");
  const [currentChapter, setCurrentChapter] = useState(1);
  const { language } = useLanguage();

  const [intro, setIntro] = useState<WorkspaceIntro | null>(null);
  const [introLoading, setIntroLoading] = useState(false);
  const [introError, setIntroError] = useState<string | null>(null);

  const [threads, setThreads] = useState<ThreadMap | null>(null);
  const [threadsLoading, setThreadsLoading] = useState(false);

  const getHeaders = useCallback(async () => {
    const h = await authHeaders();
    // DocumentReader fetches similarity without auth — only workspace-specific
    // calls need auth headers. We pass this only where needed.
    return h;
  }, []);

  // Fetch intro
  useEffect(() => {
    if (!docId) return;
    setIntroLoading(true);
    authHeaders()
      .then((h) => fetch(`${API_URL}/api/workspace/docs/${docId}/intro`, { headers: h }))
      .then((r) => {
        if (!r.ok) throw new Error("Guide unavailable");
        return r.json();
      })
      .then((d) => setIntro(d))
      .catch((e) => setIntroError(e.message))
      .finally(() => setIntroLoading(false));
  }, [docId]);

  // Fetch threads (non-blocking, loads in background)
  useEffect(() => {
    if (!docId) return;
    setThreadsLoading(true);
    authHeaders()
      .then((h) => fetch(`${API_URL}/api/workspace/docs/${docId}/threads`, { headers: h }))
      .then((r) => r.json())
      .then((d) => setThreads(d))
      .catch(() => {})
      .finally(() => setThreadsLoading(false));
  }, [docId]);

  // Track reading progress
  const markRead = useCallback(
    async (chunkId: string) => {
      try {
        const headers = await authHeaders();
        await fetch(`${API_URL}/api/workspace/progress`, {
          method: "POST",
          headers,
          body: JSON.stringify({ doc_id: docId, chunk_id: chunkId, time_spent: 3 }),
        });
      } catch {
        // silent — progress tracking is non-critical
      }
    },
    [docId],
  );

  function enterSection(num: number) {
    setCurrentChapter(num);
    setView("reading");
  }

  if (!docId) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 bg-[#0A0810] text-[#a38d7c]">
        <BookOpen className="h-10 w-10 opacity-30" />
        <p className="text-sm" style={{ fontFamily: "var(--font-ui)" }}>
          {getTranslation(language, "explore.no_doc")}{" "}
          <Link href="/workspace" className="text-[#e8b63f] underline underline-offset-2">
            {getTranslation(language, "explore.back_to_workspace")}
          </Link>
        </p>
      </div>
    );
  }

  // ── Reading view ───────────────────────────────────────────────────────
  if (view === "reading") {
    return (
      <DocumentReader
        textId={docId}
        textName={intro?.doc_title || docId}
        currentChapter={currentChapter}
        onChapterChange={setCurrentChapter}
        onBack={() => setView("entry")}
        authHeadersFn={getHeaders}
        onChunkVisible={markRead}
      />
    );
  }

  // ── Entry view ─────────────────────────────────────────────────────────
  return (
    <div className="flex h-full flex-col bg-[#0A0810]">
      <header className="flex-shrink-0 border-b border-white/[0.06] bg-[#0A0810]/95 backdrop-blur px-4 py-3 md:px-8">
        <div className="flex items-center gap-4">
          <Link
            href="/workspace"
            className="rounded-full p-2 text-[#a38d7c] transition-colors hover:bg-white/5 hover:text-[#e8b63f]"
          >
            ←
          </Link>
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-base font-bold text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>
              {intro?.doc_title || getTranslation(language, "explore.loading")}
            </h1>
            <p className="text-[10px] uppercase tracking-widest text-[#554336]" style={{ fontFamily: "var(--font-ui)" }}>
              {getTranslation(language, "explore.guide_entry")}
            </p>
          </div>
        </div>
      </header>

      <main className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl px-4 py-10 pb-24 md:px-8">
          {introLoading && (
            <div className="flex flex-col items-center gap-6 py-20">
              <YantraSpinner />
              <p className="text-xs uppercase tracking-widest text-[#a38d7c]" style={{ fontFamily: "var(--font-ui)" }}>
                {getTranslation(language, "explore.reading_doc")}
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
                <p className="text-[10px] uppercase tracking-widest text-[#e8b63f] mb-3" style={{ fontFamily: "var(--font-ui)" }}>
                  <Sparkles className="inline-block h-3 w-3 mr-1.5 mb-0.5" />
                  {getTranslation(language, "explore.doc_guide")}
                </p>
                <h2 className="text-3xl md:text-4xl font-bold text-[#e2d4b2] leading-tight mb-4" style={{ fontFamily: "var(--font-display)" }}>
                  {intro.tagline}
                </h2>
                <p className="text-base text-[#a38d7c] italic leading-relaxed" style={{ fontFamily: "var(--font-body)" }}>
                  "{intro.one_line_pitch}"
                </p>
              </div>

              <GlowDivider />

              {/* What + Why */}
              <div className="grid md:grid-cols-2 gap-6">
                <div className="rounded-2xl border border-white/[0.06] bg-[#141121] p-6">
                  <p className="text-[10px] uppercase tracking-widest text-[#7e92b8] mb-3" style={{ fontFamily: "var(--font-ui)" }}>
                    {getTranslation(language, "explore.what_it_is")}
                  </p>
                  <p className="text-sm leading-7 text-[#dbc2b0]" style={{ fontFamily: "var(--font-body)" }}>
                    {intro.what_it_is}
                  </p>
                </div>
                <div className="rounded-2xl border border-white/[0.06] bg-[#141121] p-6">
                  <p className="text-[10px] uppercase tracking-widest text-[#7e92b8] mb-3" style={{ fontFamily: "var(--font-ui)" }}>
                    {getTranslation(language, "explore.why_it_matters")}
                  </p>
                  <p className="text-sm leading-7 text-[#dbc2b0]" style={{ fontFamily: "var(--font-body)" }}>
                    {intro.why_it_matters}
                  </p>
                </div>
              </div>

              <GlowDivider />

              {/* Reading threads (choice-driven navigation) */}
              {threads && threads.threads && threads.threads.length > 0 && (
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-[#e8b63f] mb-5" style={{ fontFamily: "var(--font-ui)" }}>
                    {getTranslation(language, "explore.choose_path")}
                  </p>
                  <div className="grid sm:grid-cols-2 gap-3">
                    {threads.threads.map((thread) => (
                      <button
                        key={thread.id}
                        onClick={() => enterSection(thread.section_sequence?.[0] ?? 1)}
                        className="group text-left rounded-2xl border border-white/[0.06] bg-[#141121] p-5 hover:border-[#e8b63f]/30 hover:bg-[#1a1630] transition-all"
                      >
                        <div className="flex items-start gap-3">
                          <span className="mt-0.5 flex-shrink-0 text-[#e8b63f]/60">
                            {THREAD_ICONS[thread.icon] || <Compass className="h-4 w-4" />}
                          </span>
                          <div className="min-w-0">
                            <h3 className="text-sm font-semibold text-[#e5e2e1] group-hover:text-[#f0cd80] mb-1 transition-colors" style={{ fontFamily: "var(--font-display)" }}>
                              {thread.label}
                            </h3>
                            <p className="text-xs leading-relaxed text-[#a38d7c]" style={{ fontFamily: "var(--font-body)" }}>
                              {thread.description}
                            </p>
                          </div>
                          <ChevronRight className="h-4 w-4 flex-shrink-0 text-[#554336] group-hover:text-[#e8b63f] transition-colors mt-0.5" />
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {threadsLoading && (
                <div className="flex items-center gap-3 text-[#554336]">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="text-xs" style={{ fontFamily: "var(--font-ui)" }}>{getTranslation(language, "explore.mapping_paths")}</span>
                </div>
              )}

              <GlowDivider />

              {/* Key sections */}
              {intro.key_sections && intro.key_sections.length > 0 && (
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-[#e8b63f] mb-5" style={{ fontFamily: "var(--font-ui)" }}>
                    {getTranslation(language, "explore.key_sections")}
                  </p>
                  <div className="space-y-3">
                    {intro.key_sections.map((section, i) => (
                      <button
                        key={i}
                        onClick={() => enterSection(section.section_num)}
                        className="group w-full text-left rounded-2xl border border-white/[0.06] bg-[#141121] p-5 hover:border-[#e8b63f]/30 hover:bg-[#1a1630] transition-all"
                      >
                        <div className="flex items-start gap-4">
                          <span className="mt-0.5 flex-shrink-0 text-[10px] tabular-nums text-[#554336]" style={{ fontFamily: "var(--font-ui)" }}>
                            {String(i + 1).padStart(2, "0")}
                          </span>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center justify-between gap-2 mb-1">
                              <h3 className="text-sm font-semibold text-[#e5e2e1] group-hover:text-[#f0cd80] transition-colors" style={{ fontFamily: "var(--font-display)" }}>
                                {section.title}
                              </h3>
                              <span className="flex-shrink-0 text-[10px] text-[#554336]" style={{ fontFamily: "var(--font-ui)" }}>
                                §{section.section_num}
                              </span>
                            </div>
                            <p className="text-xs leading-relaxed text-[#a38d7c]" style={{ fontFamily: "var(--font-body)" }}>
                              {section.description}
                            </p>
                          </div>
                          <ChevronRight className="h-4 w-4 flex-shrink-0 text-[#554336] group-hover:text-[#e8b63f] transition-colors" />
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <GlowDivider />

              {/* Entry points */}
              {intro.entry_points && intro.entry_points.length > 0 && (
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-[#e8b63f] mb-5" style={{ fontFamily: "var(--font-ui)" }}>
                    {getTranslation(language, "explore.where_to_enter")}
                  </p>
                  <div className="grid sm:grid-cols-3 gap-4">
                    {intro.entry_points.map((ep, i) => (
                      <button
                        key={i}
                        onClick={() => enterSection(ep.section_num)}
                        className="group rounded-2xl border border-white/[0.06] bg-[#141121] p-5 text-left hover:border-[#e8b63f]/30 hover:bg-[#1a1630] transition-all"
                      >
                        <p className="text-[10px] uppercase tracking-widest text-[#e8b63f] mb-2" style={{ fontFamily: "var(--font-ui)" }}>
                          §{ep.section_num}
                        </p>
                        <h3 className="text-sm font-semibold text-[#e5e2e1] group-hover:text-[#f0cd80] mb-2 transition-colors" style={{ fontFamily: "var(--font-display)" }}>
                          {ep.label}
                        </h3>
                        <p className="text-xs text-[#554336] leading-relaxed" style={{ fontFamily: "var(--font-body)" }}>
                          {getTranslation(language, "explore.for_prefix")} {ep.for_reader}
                        </p>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* CTA */}
              <div className="pt-4 flex justify-center">
                <button
                  onClick={() => enterSection(1)}
                  className="rounded-full border border-[#e8b63f]/40 bg-[#e8b63f]/10 px-8 py-3 text-sm font-semibold text-[#f0cd80] hover:bg-[#e8b63f]/20 hover:border-[#e8b63f]/60 transition-all"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  Begin from the Start →
                </button>
              </div>
            </div>
          )}

          {!intro && !introLoading && !introError && (
            <div className="flex flex-col items-center gap-6 py-20">
              <button
                onClick={() => enterSection(1)}
                className="rounded-full border border-[#e8b63f]/40 bg-[#e8b63f]/10 px-8 py-3 text-sm font-semibold text-[#f0cd80] hover:bg-[#e8b63f]/20 transition-all"
                style={{ fontFamily: "var(--font-display)" }}
              >
                Enter Section 1
              </button>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default function WorkspaceExplorePageWrapper() {
  return (
    <ProtectedRoute>
      <WorkspaceExplorePage />
    </ProtectedRoute>
  );
}
