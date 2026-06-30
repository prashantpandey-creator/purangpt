"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, ChevronLeft, ChevronRight, Loader2, Search } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";
const LINES_PER_PAGE = 90;

function normalizeText(value: string) {
  return value.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

function highlightText(text: string, query: string) {
  if (!query.trim()) return text;

  const normalizedText = normalizeText(text);
  const normalizedQuery = normalizeText(query.trim());
  const matchIndex = normalizedText.indexOf(normalizedQuery);
  if (matchIndex === -1) return text;

  const before = text.slice(0, matchIndex);
  const match = text.slice(matchIndex, matchIndex + query.trim().length);
  const after = text.slice(matchIndex + query.trim().length);

  return (
    <>
      {before}
      <mark className="rounded bg-[#e8b63f]/25 px-0.5 text-[#ffe0b8]">{match}</mark>
      {after}
    </>
  );
}

export default function TextReaderPage() {
  const searchParams = useSearchParams();
  const textId = searchParams.get("id") || "";
  const refQuery = searchParams.get("ref") || "";

  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pageIndex, setPageIndex] = useState(0);
  const [searchTerm, setSearchTerm] = useState("");
  const contentRef = useRef<HTMLDivElement>(null);

  const title = textId.replace(/[_-]/g, " ");

  useEffect(() => {
    async function loadText() {
      if (!textId) {
        setError("Missing text id");
        setLoading(false);
        return;
      }

      try {
        const res = await fetch(`${API_URL}/api/text/${textId}?size=100000`);
        if (!res.ok) throw new Error("Failed to load text content");

        const data = await res.json();
        setContent((data.lines || []).join("\n"));
      } catch (e: any) {
        setError(e.message || "Failed to load text");
      } finally {
        setLoading(false);
      }
    }

    loadText();
  }, [textId]);

  const lines = useMemo(() => content.split(/\r?\n/), [content]);
  const totalPages = Math.max(1, Math.ceil(lines.length / LINES_PER_PAGE));
  const pageStart = pageIndex * LINES_PER_PAGE;
  const pageLines = lines.slice(pageStart, pageStart + LINES_PER_PAGE);

  const searchResults = useMemo(() => {
    const q = normalizeText(searchTerm.trim());
    if (!q) return [];

    return lines
      .map((line, index) => ({ line, index }))
      .filter(({ line }) => normalizeText(line).includes(q))
      .slice(0, 80);
  }, [lines, searchTerm]);

  useEffect(() => {
    if (!content || !refQuery) return;

    const normalizedRef = normalizeText(refQuery);
    const index = lines.findIndex((line) => normalizeText(line).includes(normalizedRef));
    if (index >= 0) {
      setPageIndex(Math.floor(index / LINES_PER_PAGE));
      setSearchTerm(refQuery);
    }
  }, [content, lines, refQuery]);

  useEffect(() => {
    contentRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  }, [pageIndex]);

  const goToPage = (nextPage: number) => {
    setPageIndex(Math.min(totalPages - 1, Math.max(0, nextPage)));
  };

  const jumpToLine = (lineIndex: number) => {
    setPageIndex(Math.floor(lineIndex / LINES_PER_PAGE));
    setTimeout(() => {
      const el = document.getElementById(`line-${lineIndex + 1}`);
      el?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 80);
  };

  if (loading) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-[#000000]">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-[#e8b63f]/40" />
          <p className="text-xs uppercase tracking-widest text-[#a38d7c]" style={{ fontFamily: "var(--font-ui)" }}>
            Unrolling scroll...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-[#000000]">
      <header className="flex-shrink-0 border-b border-white/10 bg-[#141121]/95 backdrop-blur">
        <div className="flex flex-col gap-4 p-4 md:px-6">
          <div className="flex items-center gap-4">
            <Link
              href="/library"
              className="rounded-full p-2 text-[#a38d7c] transition-colors hover:bg-white/5 hover:text-[#e8b63f]"
              aria-label="Back to library"
            >
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <div className="min-w-0 flex-1">
              <h1 className="truncate text-lg font-bold capitalize text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>
                {title}
              </h1>
              <p className="text-[10px] uppercase tracking-widest text-[#554336]" style={{ fontFamily: "var(--font-ui)" }}>
                Readable text viewer · {lines.length.toLocaleString()} lines
              </p>
            </div>
          </div>

          {!error && (
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <label className="relative block w-full lg:max-w-xl">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8a7060]" />
                <input
                  value={searchTerm}
                  onChange={(e) => {
                    setSearchTerm(e.target.value);
                    if (e.target.value.trim()) setPageIndex(0);
                  }}
                  placeholder="Search within this text..."
                  className="w-full rounded-2xl border border-white/10 bg-[#0d0d0d] py-3 pl-10 pr-4 text-sm text-[#e2d4b2] outline-none transition-colors placeholder:text-[#554336] focus:border-[#e8b63f]/40"
                  style={{ fontFamily: "var(--font-body)" }}
                />
              </label>

              <div className="flex items-center justify-between gap-3 lg:justify-end">
                <button
                  onClick={() => goToPage(pageIndex - 1)}
                  disabled={pageIndex === 0}
                  className="inline-flex items-center gap-2 rounded-full border border-white/10 px-4 py-2 text-xs text-[#a38d7c] transition-colors hover:border-[#e8b63f]/30 hover:text-[#e8b63f] disabled:cursor-not-allowed disabled:opacity-30"
                >
                  <ChevronLeft className="h-4 w-4" />
                  Previous
                </button>
                <span className="whitespace-nowrap text-xs text-[#6b5a3a]" style={{ fontFamily: "var(--font-ui)" }}>
                  Page {pageIndex + 1} / {totalPages}
                </span>
                <button
                  onClick={() => goToPage(pageIndex + 1)}
                  disabled={pageIndex >= totalPages - 1}
                  className="inline-flex items-center gap-2 rounded-full border border-white/10 px-4 py-2 text-xs text-[#a38d7c] transition-colors hover:border-[#e8b63f]/30 hover:text-[#e8b63f] disabled:cursor-not-allowed disabled:opacity-30"
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      </header>

      <main className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[1fr_320px]">
        <section ref={contentRef} className="min-h-0 overflow-y-auto px-4 py-6 md:px-8">
          <div className="mx-auto max-w-4xl pb-20">
            {error ? (
              <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-red-400" style={{ fontFamily: "var(--font-ui)" }}>
                {error}
              </div>
            ) : (
              <article
                className="rounded-3xl border border-white/10 bg-[#0d0d0d] p-5 shadow-[0_20px_80px_rgba(0,0,0,0.35)] md:p-8"
                style={{ fontFamily: "var(--font-body)" }}
              >
                <div className="mb-6 flex items-center justify-between border-b border-white/10 pb-4">
                  <p className="text-xs uppercase tracking-widest text-[#e8b63f]" style={{ fontFamily: "var(--font-ui)" }}>
                    Lines {pageStart + 1}-{Math.min(pageStart + LINES_PER_PAGE, lines.length)}
                  </p>
                  <p className="text-xs text-[#554336]" style={{ fontFamily: "var(--font-ui)" }}>
                    Scroll this page
                  </p>
                </div>

                <div className="space-y-1">
                  {pageLines.map((line, i) => {
                    const lineNumber = pageStart + i + 1;
                    const isMatched = searchTerm.trim() && normalizeText(line).includes(normalizeText(searchTerm.trim()));

                    return (
                      <div
                        id={`line-${lineNumber}`}
                        key={lineNumber}
                        className={`grid grid-cols-[56px_1fr] gap-4 rounded-lg px-2 py-1.5 transition-colors ${
                          isMatched ? "bg-[#e8b63f]/10" : "hover:bg-white/[0.025]"
                        }`}
                      >
                        <span className="select-none pt-0.5 text-right text-[11px] text-[#3d3226]" style={{ fontFamily: "var(--font-ui)" }}>
                          {lineNumber}
                        </span>
                        <p className="whitespace-pre-wrap break-words text-[15px] leading-8 text-[#e5d1b8] md:text-base">
                          {line.trim() ? highlightText(line, searchTerm) : <span className="opacity-30">¶</span>}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </article>
            )}
          </div>
        </section>

        {!error && (
          <aside className="hidden min-h-0 border-l border-white/10 bg-[#101010] lg:flex lg:flex-col">
            <div className="border-b border-white/10 p-4">
              <p className="text-[10px] uppercase tracking-widest text-[#a38d7c]" style={{ fontFamily: "var(--font-ui)" }}>
                Search Results
              </p>
              <p className="mt-1 text-xs text-[#554336]" style={{ fontFamily: "var(--font-body)" }}>
                {searchTerm.trim() ? `${searchResults.length} matches shown` : "Type to search this text"}
              </p>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-3">
              {searchResults.length > 0 ? (
                <div className="space-y-2">
                  {searchResults.map((result) => (
                    <button
                      key={result.index}
                      onClick={() => jumpToLine(result.index)}
                      className="block w-full rounded-2xl border border-white/5 bg-[#141121] p-3 text-left transition-colors hover:border-[#e8b63f]/30 hover:bg-white/5"
                    >
                      <p className="mb-1 text-[10px] uppercase tracking-widest text-[#e8b63f]" style={{ fontFamily: "var(--font-ui)" }}>
                        Line {result.index + 1}
                      </p>
                      <p className="line-clamp-3 text-xs leading-relaxed text-[#dbc2b0]" style={{ fontFamily: "var(--font-body)" }}>
                        {result.line}
                      </p>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="flex h-full items-center justify-center p-6 text-center text-sm text-[#554336]">
                  {searchTerm.trim() ? "No matches found." : "Search results will appear here."}
                </div>
              )}
            </div>
          </aside>
        )}
      </main>
    </div>
  );
}
