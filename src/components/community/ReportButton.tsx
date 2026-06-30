"use client";

import { useState } from "react";
import { Flag } from "lucide-react";
import { communityApi } from "@/lib/communityApi";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";

/** Inline "report" control for a post or comment. Minimal moderation surface. */
export function ReportButton({
  targetType,
  targetId,
  className = "",
  compact = false,
}: {
  targetType: "post" | "comment";
  targetId: number;
  className?: string;
  compact?: boolean;
}) {
  const { user } = useAuth();
  const { toast } = useToast();
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  const handle = async () => {
    if (!user) {
      toast("Sign in to report", "info");
      return;
    }
    if (done) return;
    const reason = window.prompt(
      "Report this content. Briefly, what's wrong with it? (spam, abuse, off-topic, etc.)",
      "",
    );
    if (reason === null) return; // cancelled
    setBusy(true);
    try {
      const res = await communityApi.report(targetType, targetId, reason);
      setDone(true);
      toast(
        res.hidden
          ? "Reported — content hidden pending review. Thank you."
          : "Reported. Thank you for keeping the community kind.",
        "success",
      );
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to report", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      onClick={handle}
      disabled={busy || done}
      title="Report"
      className={`inline-flex items-center gap-1 transition-colors hover:text-red-400 disabled:opacity-50 ${className}`}
    >
      <Flag size={compact ? 13 : 14} />
      {!compact && <span>{done ? "Reported" : "Report"}</span>}
    </button>
  );
}
