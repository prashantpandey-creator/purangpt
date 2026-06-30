"use client";

import { useState, useEffect } from "react";
import { ArrowLeft, Save, Check, Settings, Mail, Fingerprint, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { motion } from "framer-motion";
import { useAuth } from "@/context/AuthContext";
import { useSubscription } from "@/context/SubscriptionContext";
import { useToast } from "@/context/ToastContext";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { PlanCard } from "@/components/account/PlanCard";

function providerLabel(provider?: string): string {
  switch (provider) {
    case "google":
      return "Google";
    case "logto":
      return "Email";
    default:
      return provider ? provider[0].toUpperCase() + provider.slice(1) : "Account";
  }
}

export default function ProfilePage() {
  const { user, refreshProfile } = useAuth();
  const { isPro } = useSubscription();
  const { toast } = useToast();

  const [displayName, setDisplayName] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (user?.display_name) setDisplayName(user.display_name);
  }, [user]);

  const handleSave = async () => {
    if (!user) return;
    setSaving(true);
    try {
      const res = await fetch("/api/user/update", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name: displayName.trim() }),
      });
      if (res.ok) {
        await refreshProfile();
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
        toast("Display name saved", "success");
      } else {
        toast("Failed to save", "error");
      }
    } catch {
      toast("Failed to save", "error");
    } finally {
      setSaving(false);
    }
  };

  const fullName = user?.display_name || user?.name || user?.email?.split("@")[0] || "Seeker";
  const dirty = displayName.trim() !== (user?.display_name ?? "");

  return (
    <ProtectedRoute>
      <div className="min-h-screen text-[#e5e2e1]" style={{ background: "#0e0e0e" }}>
        {/* Header */}
        <div
          className="sticky top-0 z-20 border-b border-white/10 px-6 py-4 flex items-center gap-4"
          style={{ background: "rgba(14,14,14,0.95)", backdropFilter: "blur(12px)" }}
        >
          <Link
            href="/chat"
            className="flex items-center gap-2 text-[#a38d7c] hover:text-[#e5e2e1] transition-colors text-sm"
          >
            <ArrowLeft className="w-4 h-4" />
            <span style={{ fontFamily: "var(--font-ui)" }}>Back</span>
          </Link>
          <h1
            className="text-lg font-bold text-[#e5e2e1]"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Account
          </h1>
        </div>

        <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
          {/* ── Identity hero ─────────────────────────────────── */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="relative overflow-hidden rounded-2xl border border-white/10 p-6"
            style={{ background: "rgba(28,27,27,0.8)" }}
          >
            <div
              aria-hidden
              className="pointer-events-none absolute -top-20 -left-10 w-56 h-56 rounded-full blur-3xl opacity-40"
              style={{ background: "radial-gradient(circle, rgba(232,182,63,0.30), transparent 70%)" }}
            />
            <div className="relative flex items-center gap-4">
              <div
                className={`w-20 h-20 rounded-full overflow-hidden flex-shrink-0 ${
                  isPro ? "ring-2 ring-[#e8b63f]" : "ring-1 ring-white/20"
                }`}
              >
                {user?.picture ? (
                  <img
                    src={user.picture}
                    alt=""
                    className="w-full h-full object-cover"
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <div className="w-full h-full bg-[#e8b63f]/20 flex items-center justify-center text-[#e8b63f] text-2xl font-bold">
                    {fullName[0].toUpperCase()}
                  </div>
                )}
              </div>
              <div className="min-w-0">
                <h2
                  className="text-2xl font-semibold text-[#e5e2e1] truncate"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  {fullName}
                </h2>
                <p className="text-sm text-[#a38d7c] truncate">{user?.email}</p>
              </div>
            </div>
          </motion.div>

          {/* ── Active plan ───────────────────────────────────── */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
          >
            <PlanCard />
          </motion.div>

          {/* ── Account details ───────────────────────────────── */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="rounded-2xl border border-white/10 p-6 space-y-5"
            style={{ background: "rgba(28,27,27,0.8)" }}
          >
            <h3
              className="text-base font-semibold text-[#e5e2e1]"
              style={{ fontFamily: "var(--font-display)" }}
            >
              Account Details
            </h3>

            {/* Display name (editable) */}
            <div>
              <label
                className="block text-xs text-[#a38d7c] mb-2"
                style={{ fontFamily: "var(--font-ui)" }}
              >
                Display Name
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder={user?.name ?? "Your display name"}
                  className="flex-1 bg-[#141121] border border-white/10 rounded-lg px-4 py-2.5 text-sm text-[#e5e2e1] placeholder:text-[#554336] focus:outline-none focus:border-[#e8b63f]/50 transition-colors"
                  style={{ fontFamily: "var(--font-ui)" }}
                />
                <button
                  onClick={handleSave}
                  disabled={saving || !dirty}
                  className="flex items-center gap-2 px-4 py-2.5 bg-[#e8b63f] text-[#000000] rounded-lg text-sm font-medium hover:bg-[#ffb77a] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  style={{ fontFamily: "var(--font-ui)" }}
                >
                  {saved ? <Check className="w-4 h-4" /> : <Save className="w-4 h-4" />}
                  {saving ? "Saving…" : saved ? "Saved!" : "Save"}
                </button>
              </div>
            </div>

            {/* Read-only fields */}
            <div className="grid sm:grid-cols-2 gap-3 pt-1">
              <ReadOnlyField icon={<Mail className="w-4 h-4" />} label="Email" value={user?.email ?? "—"} />
              <ReadOnlyField
                icon={<ShieldCheck className="w-4 h-4" />}
                label="Signed in with"
                value={providerLabel(user?.provider)}
              />
              <ReadOnlyField
                icon={<Fingerprint className="w-4 h-4" />}
                label="Account ID"
                value={user?.sub ?? "—"}
                mono
              />
            </div>
          </motion.div>

          {/* ── Footer actions ────────────────────────────────── */}
          <Link
            href="/settings"
            className="flex items-center justify-between rounded-2xl border border-white/10 px-6 py-4 hover:bg-white/5 transition-colors group"
            style={{ background: "rgba(28,27,27,0.8)" }}
          >
            <span className="flex items-center gap-3 text-sm text-[#e5e2e1]" style={{ fontFamily: "var(--font-ui)" }}>
              <Settings className="w-4 h-4 text-[#a38d7c]" />
              Preferences, billing & account settings
            </span>
            <ArrowLeft className="w-4 h-4 text-[#a38d7c] rotate-180 group-hover:translate-x-0.5 transition-transform" />
          </Link>
        </div>
      </div>
    </ProtectedRoute>
  );
}

function ReadOnlyField({
  icon,
  label,
  value,
  mono,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="rounded-xl border border-white/5 bg-white/[0.02] px-4 py-3">
      <div className="flex items-center gap-1.5 text-[#a38d7c]" style={{ fontFamily: "var(--font-ui)" }}>
        {icon}
        <span className="text-xs">{label}</span>
      </div>
      <p
        className={`mt-1 text-sm text-[#e5e2e1] truncate ${mono ? "font-mono text-xs" : ""}`}
        style={mono ? undefined : { fontFamily: "var(--font-ui)" }}
        title={value}
      >
        {value}
      </p>
    </div>
  );
}
