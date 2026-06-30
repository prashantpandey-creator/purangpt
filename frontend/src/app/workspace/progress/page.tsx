"use client";

import { useEffect, useState } from "react";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { authHeaders } from "@/lib/api";
import { useLanguage } from "@/context/LanguageContext";
import { getTranslation } from "@/lib/i18n";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

interface SectionProgress {
  section_num: number;
  title: string;
  total: number;
  read: number;
  coverage: number;
}

interface ProgressData {
  doc_id: string;
  title: string;
  total_chunks: number;
  read_chunks: number;
  overall_coverage: number;
  sections: SectionProgress[];
}

function CoverageRing({ pct }: { pct: number }) {
  const r = 28;
  const circ = 2 * Math.PI * r;
  const dash = (pct / 100) * circ;
  return (
    <svg width="72" height="72" viewBox="0 0 72 72">
      <circle cx="36" cy="36" r={r} fill="none" stroke="#1a1630" strokeWidth="6" />
      <circle
        cx="36" cy="36" r={r} fill="none"
        stroke={pct >= 80 ? "#4ade80" : pct >= 40 ? "#e8b63f" : "#7e92b8"}
        strokeWidth="6"
        strokeDasharray={`${dash} ${circ - dash}`}
        strokeLinecap="round"
        transform="rotate(-90 36 36)"
        className="transition-all duration-500"
      />
      <text x="36" y="40" textAnchor="middle" fontSize="12" fill="#e5e2e1" fontFamily="var(--font-ui)">
        {Math.round(pct)}%
      </text>
    </svg>
  );
}

function ProgressPage() {
  const searchParams = useSearchParams();
  const docId = searchParams.get("id") || "";
  const [data, setData] = useState<ProgressData | null>(null);
  const [loading, setLoading] = useState(true);
  const { language } = useLanguage();

  useEffect(() => {
    if (!docId) return;
    authHeaders()
      .then((h) => fetch(`${API_URL}/api/workspace/docs/${docId}/progress`, { headers: h }))
      .then((r) => r.json())
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [docId]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center bg-[#0A0810]">
        <Loader2 className="h-6 w-6 animate-spin text-[#e8b63f]/40" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex h-full items-center justify-center bg-[#0A0810] text-[#a38d7c] text-sm">
        {getTranslation(language, "progress.not_found")}
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto bg-[#0A0810]">
      <header className="border-b border-white/[0.06] bg-[#0A0810]/95 backdrop-blur px-4 py-3 md:px-8 flex items-center gap-4">
        <Link href={`/workspace/explore?id=${docId}`} className="rounded-full p-2 text-[#a38d7c] hover:text-[#e8b63f] transition-colors">
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-base font-bold text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>
            {getTranslation(language, "progress.title")}
          </h1>
          <p className="text-[10px] uppercase tracking-widest text-[#554336]" style={{ fontFamily: "var(--font-ui)" }}>
            {data.title}
          </p>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-10 pb-24 md:px-8 space-y-10">
        {/* Overall ring */}
        <div className="flex items-center gap-8 rounded-2xl border border-white/[0.06] bg-[#141121] p-8">
          <CoverageRing pct={data.overall_coverage} />
          <div>
            <p className="text-2xl font-bold text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>
              {data.read_chunks} {getTranslation(language, "progress.of")} {data.total_chunks} {getTranslation(language, "progress.passages_read")}
            </p>
            <p className="text-sm text-[#a38d7c] mt-1" style={{ fontFamily: "var(--font-body)" }}>
              {data.overall_coverage >= 80
                ? getTranslation(language, "progress.covered_most")
                : data.overall_coverage >= 40
                ? getTranslation(language, "progress.good_progress")
                : getTranslation(language, "progress.just_started")}
            </p>
          </div>
        </div>

        {/* Section breakdown */}
        <div>
          <p className="text-[10px] uppercase tracking-widest text-[#e8b63f] mb-5" style={{ fontFamily: "var(--font-ui)" }}>
            {getTranslation(language, "progress.section_coverage")}
          </p>
          <div className="space-y-3">
            {data.sections.map((s) => (
              <Link
                key={s.section_num}
                href={`/workspace/explore?id=${docId}&section=${s.section_num}`}
                className="group flex items-center gap-4 rounded-2xl border border-white/[0.06] bg-[#141121] p-4 hover:border-[#e8b63f]/20 hover:bg-[#1a1630] transition-all"
              >
                <div className="w-10 flex-shrink-0 text-center">
                  <span className="text-xs tabular-nums text-[#554336]" style={{ fontFamily: "var(--font-ui)" }}>
                    §{s.section_num}
                  </span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-[#e5e2e1] truncate" style={{ fontFamily: "var(--font-display)" }}>
                    {s.title}
                  </p>
                  <div className="mt-2 h-1 w-full rounded-full bg-[#1a1630] overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${s.coverage}%`,
                        background: s.coverage >= 80 ? "#4ade80" : s.coverage >= 40 ? "#e8b63f" : "#7e92b8",
                      }}
                    />
                  </div>
                </div>
                <span className="flex-shrink-0 text-[10px] tabular-nums text-[#a38d7c]" style={{ fontFamily: "var(--font-ui)" }}>
                  {s.read}/{s.total}
                </span>
              </Link>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}

export default function ProgressPageWrapper() {
  return (
    <ProtectedRoute>
      <ProgressPage />
    </ProtectedRoute>
  );
}
