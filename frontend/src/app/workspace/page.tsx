"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Upload, FileText, Loader2, Compass, Trash2, AlertCircle, Link2, CheckCircle2, ScrollText } from "lucide-react";
import Link from "next/link";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { authHeaders } from "@/lib/api";
import { useLanguage } from "@/context/LanguageContext";
import { getTranslation } from "@/lib/i18n";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

interface WorkspaceDoc {
  doc_id: string;
  filename: string;
  doc_type: string;
  status: string;
  error_msg?: string;
  chunk_count: number;
  section_count: number;
  title?: string;
  created_at: string;
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  pending:    { label: "Queued",     color: "text-[#a38d7c]" },
  extracting: { label: "Extracting", color: "text-[#7e92b8]" },
  chunking:   { label: "Chunking",   color: "text-[#7e92b8]" },
  embedding:  { label: "Embedding",  color: "text-[#e8b63f]" },
  ready:      { label: "Ready",      color: "text-emerald-400" },
  failed:     { label: "Failed",     color: "text-red-400" },
};

function StatusBadge({ status }: { status: string }) {
  const { language } = useLanguage();
  const s = STATUS_LABELS[status] || { label: status, color: "text-[#a38d7c]" };
  const label = STATUS_LABELS[status]
    ? getTranslation(language, `workspace.status_${status}` as Parameters<typeof getTranslation>[1])
    : status;
  const isProcessing = !["ready", "failed"].includes(status);
  return (
    <span className={`inline-flex items-center gap-1.5 text-[10px] uppercase tracking-widest ${s.color}`}
          style={{ fontFamily: "var(--font-ui)" }}>
      {isProcessing && <Loader2 className="h-3 w-3 animate-spin" />}
      {status === "ready" && <CheckCircle2 className="h-3 w-3" />}
      {status === "failed" && <AlertCircle className="h-3 w-3" />}
      {label}
    </span>
  );
}

function WorkspacePage() {
  const [docs, setDocs] = useState<WorkspaceDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [urlInput, setUrlInput] = useState("");
  const { language } = useLanguage();
  const fileRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchDocs = useCallback(async () => {
    try {
      const headers = await authHeaders();
      const res = await fetch(`${API_URL}/api/workspace/docs`, { headers });
      if (res.ok) {
        const data = await res.json();
        setDocs(data.documents || []);
      }
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDocs();
  }, [fetchDocs]);

  // Poll for in-progress documents
  useEffect(() => {
    const hasPending = docs.some(d => !["ready", "failed"].includes(d.status));
    if (hasPending) {
      pollRef.current = setInterval(fetchDocs, 3000);
    } else if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [docs, fetchDocs]);

  async function uploadFile(file: File) {
    setUploading(true);
    try {
      const headers = await authHeaders();
      delete headers["Content-Type"];
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_URL}/api/workspace/upload`, {
        method: "POST",
        headers,
        body: form,
      });
      if (res.ok) {
        fetchDocs();
      }
    } finally {
      setUploading(false);
    }
  }

  async function uploadUrl() {
    if (!urlInput.trim()) return;
    setUploading(true);
    try {
      const headers = await authHeaders();
      delete headers["Content-Type"];
      const form = new FormData();
      form.append("url", urlInput.trim());
      const res = await fetch(`${API_URL}/api/workspace/upload`, {
        method: "POST",
        headers,
        body: form,
      });
      if (res.ok) {
        setUrlInput("");
        fetchDocs();
      }
    } finally {
      setUploading(false);
    }
  }

  async function deleteDoc(docId: string) {
    const headers = await authHeaders();
    await fetch(`${API_URL}/api/workspace/docs/${docId}`, {
      method: "DELETE",
      headers,
    });
    setDocs(prev => prev.filter(d => d.doc_id !== docId));
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file);
  }

  return (
    <div className="h-full overflow-y-auto p-6 md:p-10 bg-[#0A0810]">
      <div className="max-w-4xl mx-auto space-y-8 pb-20">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>
            {getTranslation(language, "workspace.title")}
          </h1>
          <p className="text-[#a38d7c] mt-2 text-sm" style={{ fontFamily: "var(--font-body)" }}>
            {getTranslation(language, "workspace.subtitle")}
          </p>
        </div>

        {/* Upload zone */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          className={`relative rounded-2xl border-2 border-dashed p-8 text-center transition-all ${
            dragOver
              ? "border-[#e8b63f] bg-[#e8b63f]/[0.06]"
              : "border-white/[0.08] bg-[#141121] hover:border-white/[0.15]"
          }`}
        >
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) uploadFile(file);
            }}
          />

          <Upload className={`mx-auto h-8 w-8 mb-4 transition-colors ${dragOver ? "text-[#e8b63f]" : "text-[#554336]"}`} />

          <p className="text-sm text-[#a38d7c] mb-4" style={{ fontFamily: "var(--font-body)" }}>
            {getTranslation(language, "workspace.drop_hint")}{" "}
            <button
              onClick={() => fileRef.current?.click()}
              className="text-[#e8b63f] underline underline-offset-2 hover:text-[#f0cd80] transition-colors"
            >
              {getTranslation(language, "workspace.browse")}
            </button>
          </p>

          {/* URL input */}
          <div className="flex items-center gap-2 max-w-md mx-auto">
            <div className="relative flex-1">
              <Link2 className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#554336]" />
              <input
                type="url"
                placeholder={getTranslation(language, "workspace.url_placeholder")}
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && uploadUrl()}
                className="w-full rounded-xl border border-white/[0.08] bg-[#0A0810] pl-10 pr-4 py-2.5 text-sm text-[#e5e2e1] placeholder-[#3d3226] focus:border-[#e8b63f]/30 focus:outline-none transition-colors"
                style={{ fontFamily: "var(--font-body)" }}
              />
            </div>
            <button
              onClick={uploadUrl}
              disabled={!urlInput.trim() || uploading}
              className="rounded-xl border border-[#e8b63f]/30 bg-[#e8b63f]/10 px-4 py-2.5 text-xs font-medium text-[#f0cd80] hover:bg-[#e8b63f]/20 disabled:opacity-30 transition-colors"
              style={{ fontFamily: "var(--font-ui)" }}
            >
              {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : getTranslation(language, "workspace.ingest")}
            </button>
          </div>
        </div>

        {/* Document list */}
        {loading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-[#e8b63f]/40" />
          </div>
        ) : docs.length === 0 ? (
          <div className="text-center py-12">
            <FileText className="mx-auto h-10 w-10 text-[#554336]/50 mb-4" />
            <p className="text-sm text-[#554336]" style={{ fontFamily: "var(--font-body)" }}>
              No documents yet. Upload something to get started.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-[10px] uppercase tracking-widest text-[#554336]" style={{ fontFamily: "var(--font-ui)" }}>
              {docs.length} document{docs.length !== 1 ? "s" : ""}
            </p>
            {docs.map((doc) => (
              <div
                key={doc.doc_id}
                className="group rounded-2xl border border-white/[0.06] bg-[#141121] p-5 flex items-center gap-4"
              >
                <div className="flex-shrink-0">
                  <FileText className="h-8 w-8 text-[#554336]" />
                </div>

                <div className="flex-1 min-w-0">
                  <h3
                    className="text-sm font-semibold text-[#e5e2e1] truncate"
                    style={{ fontFamily: "var(--font-display)" }}
                  >
                    {doc.title || doc.filename}
                  </h3>
                  <div className="flex items-center gap-3 mt-1">
                    <StatusBadge status={doc.status} />
                    {doc.status === "ready" && (
                      <span className="text-[10px] text-[#3d3226]" style={{ fontFamily: "var(--font-ui)" }}>
                        {doc.chunk_count} chunks · {doc.section_count} sections
                      </span>
                    )}
                    {doc.status === "failed" && doc.error_msg && (
                      <span className="text-[10px] text-red-400/60 truncate max-w-[200px]">
                        {doc.error_msg}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 flex-shrink-0">
                  {doc.status === "ready" && (
                    <>
                      <Link
                        href={`/workspace/explore?id=${doc.doc_id}`}
                        className="flex items-center gap-1.5 rounded-full border border-[#e8b63f]/30 bg-[#e8b63f]/10 px-3 py-1.5 text-xs font-medium text-[#f0cd80] hover:bg-[#e8b63f]/20 transition-colors"
                        style={{ fontFamily: "var(--font-ui)" }}
                      >
                        <Compass className="h-3 w-3" />
                        Explore
                      </Link>
                      <Link
                        href={`/workspace/review?doc=${doc.doc_id}`}
                        title={getTranslation(language, "workspace.review_tip")}
                        className="flex items-center gap-1.5 rounded-full border border-[#7e92b8]/30 bg-[#7e92b8]/10 px-3 py-1.5 text-xs font-medium text-[#9fb0d0] hover:bg-[#7e92b8]/20 transition-colors"
                        style={{ fontFamily: "var(--font-ui)" }}
                      >
                        <ScrollText className="h-3 w-3" />
                        {getTranslation(language, "workspace.review")}
                      </Link>
                    </>
                  )}
                  <button
                    onClick={() => deleteDoc(doc.doc_id)}
                    className="rounded-full p-2 text-[#3d3226] hover:text-red-400 hover:bg-red-400/10 transition-colors opacity-0 group-hover:opacity-100"
                    title={getTranslation(language, "workspace.delete")}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function WorkspacePageWrapper() {
  return (
    <ProtectedRoute>
      <WorkspacePage />
    </ProtectedRoute>
  );
}
