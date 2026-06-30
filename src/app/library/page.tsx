"use client";

import { useEffect, useState } from "react";
import { Loader2, BookOpen, Compass, Search, X, Sparkles } from "lucide-react";
import Link from "next/link";
import { useLanguage } from "@/context/LanguageContext";
import { getTranslation } from "@/lib/i18n";
import { searchAPI, type SourceRef } from "@/lib/api";
import { isGarbled } from "@/lib/verse";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

// The corpus is HTML-entity encoded (e.g. yudhi&#7779;&#7789;hira). Decode + tidy
// so a search snippet reads as clean IAST instead of raw markup.
function cleanVerse(s: string): string {
  if (!s) return "";
  let t = s;
  if (typeof document !== "undefined") {
    const ta = document.createElement("textarea");
    ta.innerHTML = s;
    t = ta.value;
  }
  return t.replace(/\s+/g, " ").trim();
}

// The great texts lead. Raw catalog order buried Ramayana/Mahabharata among the
// lesser-known Puranas; surface the famous ones first, then by category, then name.
const FEATURED = ["ramayana", "mahabharata", "bhagavata", "gita", "vishnu", "shiva"];
const CAT_RANK: Record<string, number> = { epic: 0, mahapurana: 1, upanishad: 2, darshana: 3, yoga: 4, nath: 5 };

interface LibraryText {
  id: string;
  name: string;
  tradition: string;
  category: string;
  bias: string;
  downloaded: boolean;
}

export default function LibraryPage() {
  const [texts, setTexts] = useState<LibraryText[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { language } = useLanguage();

  // Semantic search across the whole corpus (hybrid pgvector + BM25, cross-lingual).
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<SourceRef[] | null>(null);

  async function runSearch() {
    const q = query.trim();
    if (!q) { setResults(null); return; }
    setSearching(true);
    try {
      // Over-fetch, then drop encoding-rotted rows (Skanda/Bhavishya OCR garbage) so
      // the visible results stay clean. Temporary — removed once the data is recleaned.
      const hits = await searchAPI.searchVerses(q, 36);
      setResults(hits.filter((r) => !isGarbled(r.text)).slice(0, 24));
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  }

  function clearSearch() {
    setQuery("");
    setResults(null);
  }

  const sortedTexts = [...texts].sort((a, b) => {
    const fa = FEATURED.indexOf(a.id);
    const fb = FEATURED.indexOf(b.id);
    if (fa !== -1 || fb !== -1) return (fa === -1 ? 99 : fa) - (fb === -1 ? 99 : fb);
    const ca = CAT_RANK[a.category] ?? 9;
    const cb = CAT_RANK[b.category] ?? 9;
    if (ca !== cb) return ca - cb;
    return a.name.localeCompare(b.name);
  });

  useEffect(() => {
    async function fetchLibrary() {
      try {
        const res = await fetch(`${API_URL}/api/puranas`);
        if (!res.ok) throw new Error("Failed to load library texts");

        const data = await res.json();
        setTexts(data.puranas || []);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }
    fetchLibrary();
  }, []);

  if (loading) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-[#000000]">
        <Loader2 className="h-6 w-6 animate-spin text-[#e8b63f]/40" />
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-6 md:p-10 bg-[#000000]">
      <div className="max-w-6xl mx-auto space-y-8 pb-20">
        <div>
          <h1 className="text-3xl font-bold text-[#e5e2e1]" style={{ fontFamily: 'var(--font-display)' }}>
            {getTranslation(language, "library.title")}
          </h1>
          <p className="text-[#a38d7c] mt-2 text-sm" style={{ fontFamily: 'var(--font-body)' }}>
            {getTranslation(language, "library.subtitle")}
          </p>
        </div>

        {/* AI search — semantic (meaning), cross-lingual, across the whole corpus */}
        <div>
          <div className="flex items-center gap-2 rounded-2xl border border-[#e8b63f]/25 bg-[#141121] px-4 py-2.5 focus-within:border-[#e8b63f]/50 transition-colors">
            <Search className="h-4 w-4 flex-shrink-0 text-[#e8b63f]" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") runSearch(); }}
              placeholder={getTranslation(language, "library.search_placeholder")}
              className="flex-1 bg-transparent text-[15px] text-[#e2d4b2] placeholder:text-[#6b5a3a] focus:outline-none"
              style={{ fontFamily: 'var(--font-body)' }}
            />
            {query && (
              <button onClick={clearSearch} aria-label="Clear search" className="flex-shrink-0 text-[#6b5a3a] hover:text-[#e8b63f] transition-colors">
                <X className="h-4 w-4" />
              </button>
            )}
            {searching && <Loader2 className="h-4 w-4 flex-shrink-0 animate-spin text-[#e8b63f]/60" />}
          </div>
          <p className="mt-2 ml-1 flex items-center gap-1.5 text-[11px] text-[#7e92b8]" style={{ fontFamily: 'var(--font-ui)' }}>
            <Sparkles className="h-3 w-3" />
            {getTranslation(language, "library.search_hint")}
          </p>
        </div>

        {error ? (
          <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-[4px] font-[Geist]">
            {error}
          </div>
        ) : results !== null ? (
          <div className="space-y-3">
            {results.length === 0 ? (
              <p className="text-[#a38d7c] text-sm py-8 text-center" style={{ fontFamily: 'var(--font-body)' }}>
                {getTranslation(language, "library.no_results")}
              </p>
            ) : (
              <>
                <p className="text-[11px] uppercase tracking-wider text-[#7e92b8]" style={{ fontFamily: 'var(--font-ui)' }}>
                  {results.length} {getTranslation(language, "library.passages_found")}
                </p>
                {results.map((r, i) => (
                  <div key={r.chunk_id ?? i} className="rounded-2xl border border-white/[0.06] bg-[#141121] p-4">
                    <div className="flex items-start justify-between gap-3">
                      <span className="text-sm text-[#f0cd80] font-semibold leading-snug" style={{ fontFamily: 'var(--font-display)' }}>
                        {r.text_name || r.purana}
                      </span>
                      {r.reference && (
                        <span className="flex-shrink-0 mt-0.5 text-[10px] uppercase tracking-wider text-[#6b5a3a]" style={{ fontFamily: 'var(--font-ui)' }}>
                          {r.reference}
                        </span>
                      )}
                    </div>
                    <p className="mt-2 text-[13px] leading-relaxed text-[#cfc3a8] line-clamp-3" style={{ fontFamily: 'var(--font-body)' }}>
                      {cleanVerse(r.text).slice(0, 240)}
                    </p>
                    {r.chunk_id && (
                      <Link
                        href={`/library/explore?verse=${encodeURIComponent(r.chunk_id)}`}
                        className="mt-3 inline-flex items-center gap-1.5 rounded-full border border-[#e8b63f]/30 bg-[#e8b63f]/10 px-3 py-1.5 text-xs font-medium text-[#f0cd80] hover:bg-[#e8b63f]/20 transition-colors"
                        style={{ fontFamily: 'var(--font-ui)' }}
                      >
                        <Compass className="h-3 w-3" />
                        {getTranslation(language, "library.read_in_context")}
                      </Link>
                    )}
                  </div>
                ))}
              </>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {sortedTexts.map((text) => (
              <div
                key={text.id}
                className="group p-5 rounded-2xl border border-white/[0.06] bg-[#141121] flex flex-col gap-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-[10px] uppercase tracking-wider text-[#e8b63f]" style={{ fontFamily: 'var(--font-ui)' }}>
                    {text.tradition}
                  </span>
                  <span className="text-[10px] text-[#3d3226] uppercase tracking-wider" style={{ fontFamily: 'var(--font-ui)' }}>
                    {text.category}
                  </span>
                </div>

                <h2 className="text-base text-[#e5e2e1] font-semibold leading-snug" style={{ fontFamily: 'var(--font-display)' }}>
                  {text.name}
                </h2>

                <div className="mt-auto pt-3 border-t border-white/[0.05] flex items-center gap-2">
                  <Link
                    href={`/library/explore?id=${text.id}`}
                    className="flex items-center gap-1.5 rounded-full border border-[#e8b63f]/30 bg-[#e8b63f]/10 px-3 py-1.5 text-xs font-medium text-[#f0cd80] hover:bg-[#e8b63f]/20 transition-colors"
                    style={{ fontFamily: 'var(--font-ui)' }}
                  >
                    <Compass className="h-3 w-3" />
                    {getTranslation(language, "library.explore")}
                  </Link>
                  <Link
                    href={`/library/text?id=${text.id}`}
                    className="flex items-center gap-1.5 rounded-full border border-white/10 px-3 py-1.5 text-xs text-[#a38d7c] hover:border-white/20 hover:text-[#e5e2e1] transition-colors"
                    style={{ fontFamily: 'var(--font-ui)' }}
                  >
                    <BookOpen className="h-3 w-3" />
                    {getTranslation(language, "library.raw_text")}
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
