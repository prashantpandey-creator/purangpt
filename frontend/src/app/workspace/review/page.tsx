"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Loader2, ScrollText, AlertCircle } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { useLanguage } from "@/context/LanguageContext";
import { getTranslation } from "@/lib/i18n";
import { streamReview } from "@/lib/api";

// On-theme markdown — Marcellus gold headings, ivory body, no typography plugin dep.
const MD = {
  h1: (p: any) => <h2 className="mt-6 mb-2 text-lg text-[#f6d27a]" style={{ fontFamily: "var(--font-display)" }} {...p} />,
  h2: (p: any) => <h2 className="mt-6 mb-2 text-lg text-[#f6d27a]" style={{ fontFamily: "var(--font-display)" }} {...p} />,
  h3: (p: any) => <h3 className="mt-5 mb-1.5 text-base text-[#e8b63f]" style={{ fontFamily: "var(--font-display)" }} {...p} />,
  p: (p: any) => <p className="mb-3 leading-7 text-[#e2d4b2]" style={{ fontFamily: "var(--font-body)" }} {...p} />,
  li: (p: any) => <li className="mb-1 ml-5 list-disc leading-7 text-[#e2d4b2]" style={{ fontFamily: "var(--font-body)" }} {...p} />,
  strong: (p: any) => <strong className="font-medium text-[#f6d27a]" {...p} />,
  em: (p: any) => <em className="text-[#e8b63f]" {...p} />,
  blockquote: (p: any) => <blockquote className="my-3 border-l-2 border-[#e8b63f]/40 pl-4 text-[#a38d7c] italic" {...p} />,
  code: (p: any) => <code className="rounded bg-white/[0.06] px-1 py-0.5 text-[13px] text-[#f0cd80]" {...p} />,
};

function WorkspaceReviewPage() {
  const searchParams = useSearchParams();
  const docId = searchParams.get("doc") || "";
  const { language } = useLanguage();

  const [text, setText] = useState("");
  const [statusMsg, setStatusMsg] = useState("");
  const [phase, setPhase] = useState<"idle" | "streaming" | "done" | "error">("idle");
  const [error, setError] = useState("");
  const startedRef = useRef(false);

  useEffect(() => {
    if (!docId || startedRef.current) return;
    startedRef.current = true;
    (async () => {
      setPhase("streaming");
      try {
        for await (const ev of streamReview(docId, language)) {
          if (ev.type === "status") setStatusMsg(ev.message || "");
          else if (ev.type === "token") setText((t) => t + (ev.content || ""));
          else if (ev.type === "error") { setError(ev.message || "The review could not be completed."); setPhase("error"); return; }
          else if (ev.type === "done") { setPhase("done"); return; }
        }
        setPhase("done");
      } catch (e: any) {
        setError(e?.message || getTranslation(language, "review.failed"));
        setPhase("error");
      }
    })();
  }, [docId, language]);

  return (
    <div className="mx-auto flex h-full w-full max-w-3xl flex-col px-4 py-6 md:px-8">
      <div className="mb-6 flex items-center gap-3">
        <Link
          href="/workspace"
          aria-label={getTranslation(language, "review.back")}
          className="rounded-full p-2 text-[#7e92b8] transition-colors hover:text-[#e8b63f]"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div className="min-w-0">
          <h1 className="flex items-center gap-2 text-xl text-[#e2d4b2]" style={{ fontFamily: "var(--font-display)" }}>
            <ScrollText className="h-5 w-5 text-[#e8b63f]" />
            {getTranslation(language, "review.title")}
          </h1>
          <p className="text-xs text-[#7e92b8]" style={{ fontFamily: "var(--font-body)" }}>
            {getTranslation(language, "review.subtitle")}
          </p>
        </div>
      </div>

      {!docId && (
        <p className="text-sm text-[#a38d7c]">{getTranslation(language, "review.no_doc")}</p>
      )}

      {phase === "streaming" && !text && (
        <div className="flex items-center gap-3 text-sm text-[#a38d7c]" style={{ fontFamily: "var(--font-body)" }}>
          <Loader2 className="h-4 w-4 animate-spin text-[#e8b63f]" />
          {statusMsg || getTranslation(language, "review.reading")}
        </div>
      )}

      {error && (
        <div className="flex items-start gap-2 rounded-xl border border-red-500/20 bg-red-500/[0.06] p-4 text-sm text-red-300">
          <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {text && (
        <article className="min-h-0 flex-1 overflow-y-auto pb-10">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD}>
            {text}
          </ReactMarkdown>
          {phase === "streaming" && (
            <div className="mt-2 flex items-center gap-2 text-xs text-[#7e92b8]">
              <Loader2 className="h-3 w-3 animate-spin" /> {getTranslation(language, "review.still_reading")}
            </div>
          )}
        </article>
      )}
    </div>
  );
}

export default function WorkspaceReviewPageWrapper() {
  return (
    <ProtectedRoute>
      <Suspense fallback={null}>
        <WorkspaceReviewPage />
      </Suspense>
    </ProtectedRoute>
  );
}
