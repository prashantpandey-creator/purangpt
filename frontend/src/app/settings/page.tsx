"use client";

import { useState, useEffect, useRef } from "react";
import { ArrowLeft, Save, LogOut, Trash2, Volume2, VolumeX, Check, Crown, KeyRound, Copy, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { useSubscription } from "@/context/SubscriptionContext";
import { usePaywall } from "@/context/PaywallContext";
import { useToast } from "@/context/ToastContext";
import { useChatPreferences, type Verbosity, type TextSize } from "@/context/ChatPreferencesContext";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { PlanCard } from "@/components/account/PlanCard";
import { motion } from "framer-motion";
import { Capacitor } from "@capacitor/core";

const SECTION = {
  Profile: "profile",
  Chat: "chat",
  Preferences: "preferences",
  Billing: "billing",
  API: "api",
  Account: "account",
} as const;

type Section = typeof SECTION[keyof typeof SECTION];

interface ApiKeyMeta {
  id: string;
  prefix: string;
  name: string | null;
  created_at: string;
  last_used_at: string | null;
}

function SectionTab({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-4 py-2.5 rounded-xl text-sm font-medium transition-colors ${
        active
          ? "bg-[#e8b63f]/15 text-[#e8b63f]"
          : "text-[#a38d7c] hover:bg-white/5 hover:text-[#e5e2e1]"
      }`}
      style={{ fontFamily: "var(--font-ui)" }}
    >
      {label}
    </button>
  );
}

export default function SettingsPage() {
  const router = useRouter();
  const { user, signOut, refreshProfile } = useAuth();
  const { isPro } = useSubscription();
  const { openPaywall } = usePaywall();
  const { toast } = useToast();
  const chatPrefs = useChatPreferences();

  const [section, setSection] = useState<Section>(SECTION.Profile);
  const [displayName, setDisplayName] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Sound preference (localStorage). Audio feedback is a native-app-only
  // feature, so the toggle is only shown when running inside the app.
  const [muted, setMuted] = useState(false);
  const [isApp, setIsApp] = useState(false);
  // Devanagari display mode (localStorage)
  const [devanagariMode, setDevanagariMode] = useState<"both" | "transliteration">("both");

  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const deleteInputRef = useRef<HTMLInputElement>(null);

  // API keys
  const [apiKeys, setApiKeys] = useState<ApiKeyMeta[]>([]);
  const [keysLoading, setKeysLoading] = useState(false);
  const [creatingKey, setCreatingKey] = useState(false);
  const [newKey, setNewKey] = useState<string | null>(null); // shown exactly once

  const loadApiKeys = async () => {
    setKeysLoading(true);
    try {
      const res = await fetch("/api/keys");
      if (res.ok) {
        const data = await res.json();
        setApiKeys(data.keys ?? []);
      }
    } finally {
      setKeysLoading(false);
    }
  };

  useEffect(() => {
    if (section === SECTION.API && isPro) loadApiKeys();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [section, isPro]);

  const handleCreateKey = async () => {
    setCreatingKey(true);
    try {
      const res = await fetch("/api/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const data = await res.json();
      if (res.ok) {
        setNewKey(data.key);
        await loadApiKeys();
        toast("API key created — copy it now, it won't be shown again", "success");
      } else {
        toast(data.error ?? "Failed to create key", "error");
      }
    } finally {
      setCreatingKey(false);
    }
  };

  const handleRevokeKey = async (id: string) => {
    const res = await fetch(`/api/keys/${id}`, { method: "DELETE" });
    if (res.ok) {
      setApiKeys((ks) => ks.filter((k) => k.id !== id));
      toast("Key revoked", "success");
    } else {
      toast("Failed to revoke key", "error");
    }
  };

  const copyKey = (value: string) => {
    navigator.clipboard?.writeText(value);
    toast("Copied to clipboard", "success");
  };

  useEffect(() => {
    if (user?.display_name) setDisplayName(user.display_name);
    if (typeof window !== "undefined") {
      setIsApp(Capacitor.isNativePlatform());
      setMuted(localStorage.getItem("purangpt:muted") === "true");
      setDevanagariMode(
        (localStorage.getItem("purangpt:devanagari") as "both" | "transliteration") ?? "both"
      );
    }
  }, [user]);

  const handleSaveProfile = async () => {
    if (!user) return;
    setSaving(true);
    try {
      const res = await fetch("/api/user/update", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name: displayName }),
      });
      if (res.ok) {
        await refreshProfile();
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
        toast("Display name saved", "success");
      } else {
        toast("Failed to save", "error");
      }
    } finally {
      setSaving(false);
    }
  };

  const handleToggleMute = () => {
    const next = !muted;
    setMuted(next);
    localStorage.setItem("purangpt:muted", String(next));
    window.dispatchEvent(new Event("purangpt:mute-change"));
  };

  const handleDevanagariMode = (val: "both" | "transliteration") => {
    setDevanagariMode(val);
    localStorage.setItem("purangpt:devanagari", val);
  };

  const handleSignOut = async () => {
    await signOut();
    router.push("/");
  };

  const handleDeleteAccount = async () => {
    if (!deleteConfirm) {
      setDeleteConfirm(true);
      setTimeout(() => deleteInputRef.current?.focus(), 50);
      return;
    }
    toast("Account deletion is not available yet. Please contact support.", "error");
    setDeleteConfirm(false);
  };

  const planLabel = isPro ? "Pro" : "Free";
  const planColor = isPro ? "text-[#e8b63f]" : "text-[#a38d7c]";

  return (
    <ProtectedRoute>
      <div
        className="min-h-screen text-[#e5e2e1]"
        style={{ background: "#0e0e0e" }}
      >
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
            Settings
          </h1>
        </div>

        <div className="max-w-4xl mx-auto px-4 py-8 flex gap-8">
          {/* Sidebar nav */}
          <aside className="hidden sm:flex flex-col gap-1 w-44 flex-shrink-0">
            {Object.entries(SECTION).map(([label, val]) => (
              <SectionTab
                key={val}
                label={label}
                active={section === val}
                onClick={() => setSection(val)}
              />
            ))}
          </aside>

          {/* Mobile nav */}
          <div className="sm:hidden w-full mb-4 flex gap-2 overflow-x-auto pb-2">
            {Object.entries(SECTION).map(([label, val]) => (
              <button
                key={val}
                onClick={() => setSection(val)}
                className={`flex-shrink-0 px-4 py-2 rounded-full text-xs font-medium transition-colors border ${
                  section === val
                    ? "bg-[#e8b63f]/15 text-[#e8b63f] border-[#e8b63f]/30"
                    : "text-[#a38d7c] border-white/10 hover:bg-white/5"
                }`}
                style={{ fontFamily: "var(--font-ui)" }}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Content */}
          <main className="flex-1 min-w-0 space-y-6">

            {/* ── Profile ──────────────────────────────────────── */}
            {section === SECTION.Profile && (
              <motion.div
                key="profile"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-6"
              >
                <div
                  className="rounded-2xl border border-white/10 p-6 space-y-6"
                  style={{ background: "rgba(28,27,27,0.8)" }}
                >
                  <h2
                    className="text-base font-semibold text-[#e5e2e1]"
                    style={{ fontFamily: "var(--font-display)" }}
                  >
                    Profile
                  </h2>

                  {/* Avatar */}
                  <div className="flex items-center gap-4">
                    <div className={`w-16 h-16 rounded-full overflow-hidden flex-shrink-0 ${isPro ? "ring-2 ring-[#e8b63f]" : "ring-1 ring-white/20"}`}>
                      {user?.picture ? (
                        <img src={user.picture} alt="" className="w-full h-full object-cover" referrerPolicy="no-referrer" />
                      ) : (
                        <div className="w-full h-full bg-[#e8b63f]/20 flex items-center justify-center text-[#e8b63f] text-xl font-bold">
                          {(user?.display_name || user?.name || "?")[0].toUpperCase()}
                        </div>
                      )}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-[#e5e2e1]">{user?.name}</p>
                      <p className="text-xs text-[#a38d7c] mt-0.5">{user?.email}</p>
                      <span className={`text-xs mt-1 inline-flex items-center gap-1 ${planColor}`} style={{ fontFamily: "var(--font-ui)" }}>
                        {isPro && <Crown className="w-3 h-3" />} {planLabel} Plan
                      </span>
                    </div>
                  </div>

                  {/* Display name */}
                  <div>
                    <label className="block text-xs text-[#a38d7c] mb-2" style={{ fontFamily: "var(--font-ui)" }}>
                      Display Name (optional override)
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
                        onClick={handleSaveProfile}
                        disabled={saving}
                        className="flex items-center gap-2 px-4 py-2.5 bg-[#e8b63f] text-[#000000] rounded-lg text-sm font-medium hover:bg-[#ffb77a] transition-colors disabled:opacity-50"
                        style={{ fontFamily: "var(--font-ui)" }}
                      >
                        {saved ? <Check className="w-4 h-4" /> : <Save className="w-4 h-4" />}
                        {saving ? "Saving…" : saved ? "Saved!" : "Save"}
                      </button>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {/* ── Chat ─────────────────────────────────────────── */}
            {section === SECTION.Chat && (
              <motion.div
                key="chat"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-4"
              >
                {/* How the assistant addresses you */}
                <div className="rounded-2xl border border-white/10 p-6 space-y-4" style={{ background: "rgba(28,27,27,0.8)" }}>
                  <div>
                    <h2 className="text-base font-semibold text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>
                      How PuranGPT addresses you
                    </h2>
                    <p className="mt-1 text-xs text-[#a38d7c]" style={{ fontFamily: "var(--font-ui)" }}>
                      The name or form the guide uses when speaking to you (e.g. &ldquo;Arjuna&rdquo;, &ldquo;seeker&rdquo;, &ldquo;my friend&rdquo;). Leave blank for none.
                    </p>
                  </div>
                  <input
                    type="text"
                    value={chatPrefs.addressAs}
                    onChange={(e) => chatPrefs.setAddressAs(e.target.value)}
                    placeholder="e.g. Arjuna"
                    maxLength={60}
                    className="w-full bg-[#141121] border border-white/10 rounded-xl px-4 py-2.5 text-sm text-[#e5e2e1] placeholder:text-[#554336] focus:outline-none focus:border-[#e8b63f]/50 transition-colors"
                    style={{ fontFamily: "var(--font-ui)" }}
                  />
                </div>

                {/* Voice & creativity */}
                <div className="rounded-2xl border border-white/10 p-6 space-y-6" style={{ background: "rgba(28,27,27,0.8)" }}>
                  <h2 className="text-base font-semibold text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>
                    Voice &amp; length
                  </h2>

                  {/* Verbosity */}
                  <div>
                    <label className="block text-xs text-[#a38d7c] mb-2" style={{ fontFamily: "var(--font-ui)" }}>
                      Response length
                    </label>
                    <div className="grid grid-cols-3 gap-2">
                      {(["concise", "balanced", "detailed"] as Verbosity[]).map((v) => (
                        <button
                          key={v}
                          onClick={() => chatPrefs.setVerbosity(v)}
                          className={`px-3 py-2.5 rounded-xl text-sm capitalize transition-colors border ${
                            chatPrefs.verbosity === v
                              ? "bg-[#e8b63f]/15 text-[#e8b63f] border-[#e8b63f]/40"
                              : "text-[#a38d7c] border-white/10 hover:bg-white/5"
                          }`}
                          style={{ fontFamily: "var(--font-ui)" }}
                        >
                          {v}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Temperature */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <label className="text-xs text-[#a38d7c]" style={{ fontFamily: "var(--font-ui)" }}>
                        Creativity (temperature)
                      </label>
                      <span className="text-xs text-[#e8b63f] tabular-nums" style={{ fontFamily: "var(--font-ui)" }}>
                        {chatPrefs.temperature.toFixed(2)}
                      </span>
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={1.5}
                      step={0.05}
                      value={chatPrefs.temperature}
                      onChange={(e) => chatPrefs.setTemperature(parseFloat(e.target.value))}
                      className="w-full accent-[#e8b63f]"
                    />
                    <div className="flex justify-between mt-1 text-[10px] text-[#6b5a3a]" style={{ fontFamily: "var(--font-ui)" }}>
                      <span>Precise</span>
                      <span>Balanced</span>
                      <span>Creative</span>
                    </div>
                  </div>
                </div>

                {/* Behavior */}
                <div className="rounded-2xl border border-white/10 p-6 space-y-4" style={{ background: "rgba(28,27,27,0.8)" }}>
                  <h2 className="text-base font-semibold text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>
                    Behavior
                  </h2>
                  {[
                    { label: "Auto-scroll to newest message", value: chatPrefs.autoScroll, set: chatPrefs.setAutoScroll },
                    { label: "Press Enter to send", value: chatPrefs.enterToSend, set: chatPrefs.setEnterToSend },
                  ].map((row) => (
                    <div key={row.label} className="flex items-center justify-between">
                      <span className="text-sm text-[#d8c594]" style={{ fontFamily: "var(--font-ui)" }}>{row.label}</span>
                      <button
                        onClick={() => row.set(!row.value)}
                        role="switch"
                        aria-checked={row.value}
                        className={`relative h-6 w-11 rounded-full transition-colors ${row.value ? "bg-[#e8b63f]" : "bg-white/15"}`}
                      >
                        <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${row.value ? "translate-x-[22px]" : "translate-x-0.5"}`} />
                      </button>
                    </div>
                  ))}
                </div>

                {/* Accessibility: text size */}
                <div className="rounded-2xl border border-white/10 p-6 space-y-4" style={{ background: "rgba(28,27,27,0.8)" }}>
                  <h2 className="text-base font-semibold text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>
                    Accessibility
                  </h2>
                  <label className="block text-xs text-[#a38d7c]" style={{ fontFamily: "var(--font-ui)" }}>
                    Text size
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    {([
                      { id: "compact", label: "Compact" },
                      { id: "normal", label: "Normal" },
                      { id: "large", label: "Large" },
                    ] as { id: TextSize; label: string }[]).map((o) => (
                      <button
                        key={o.id}
                        onClick={() => chatPrefs.setTextSize(o.id)}
                        className={`px-3 py-2.5 rounded-xl transition-colors border ${
                          chatPrefs.textSize === o.id
                            ? "bg-[#e8b63f]/15 text-[#e8b63f] border-[#e8b63f]/40"
                            : "text-[#a38d7c] border-white/10 hover:bg-white/5"
                        }`}
                        style={{ fontFamily: "var(--font-ui)", fontSize: o.id === "compact" ? "0.8rem" : o.id === "large" ? "1.05rem" : "0.9rem" }}
                      >
                        {o.label}
                      </button>
                    ))}
                  </div>
                </div>
              </motion.div>
            )}

            {/* ── Preferences ──────────────────────────────────── */}
            {section === SECTION.Preferences && (
              <motion.div
                key="preferences"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-4"
              >
                <div
                  className="rounded-2xl border border-white/10 p-6 space-y-6"
                  style={{ background: "rgba(28,27,27,0.8)" }}
                >
                  <h2
                    className="text-base font-semibold text-[#e5e2e1]"
                    style={{ fontFamily: "var(--font-display)" }}
                  >
                    Preferences
                  </h2>

                  {/* Sound — native-app-only feature (intentionally hidden on the web) */}
                  {isApp && (
                    <div className="flex items-center justify-between rounded-xl border border-[#e8b63f]/25 p-4" style={{ background: "rgba(232,182,63,0.06)" }}>
                      <div>
                        <p className="text-sm text-[#e5e2e1] flex items-center gap-2">
                          Sound Effects
                          <span className="text-[9px] uppercase tracking-wider bg-[#e8b63f]/15 text-[#e8b63f] px-1.5 py-0.5 rounded">App</span>
                        </p>
                        <p className="text-xs text-[#a38d7c] mt-0.5">ASMR click, thinking pulse, accepted tick</p>
                      </div>
                      <button
                        onClick={handleToggleMute}
                        className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm transition-colors ${
                          !muted
                            ? "bg-[#e8b63f]/15 text-[#e8b63f] border border-[#e8b63f]/30"
                            : "bg-white/5 text-[#a38d7c] border border-white/10"
                        }`}
                        style={{ fontFamily: "var(--font-ui)" }}
                      >
                        {muted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
                        {muted ? "Muted" : "On"}
                      </button>
                    </div>
                  )}

                  <div className={isApp ? "border-t border-white/10 pt-4" : ""}>
                    {/* Devanagari display */}
                    <p className="text-sm text-[#e5e2e1] mb-1">Sanskrit Display</p>
                    <p className="text-xs text-[#a38d7c] mb-3">How verses appear in answers</p>
                    <div className="flex gap-2">
                      {(["both", "transliteration"] as const).map((val) => (
                        <button
                          key={val}
                          onClick={() => handleDevanagariMode(val)}
                          className={`px-4 py-2 rounded-full text-sm transition-colors border ${
                            devanagariMode === val
                              ? "bg-[#e8b63f]/15 text-[#e8b63f] border-[#e8b63f]/30"
                              : "text-[#a38d7c] border-white/10 hover:bg-white/5"
                          }`}
                          style={{ fontFamily: "var(--font-ui)" }}
                        >
                          {val === "both" ? "Devanagari + Transliteration" : "Transliteration only"}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {/* ── Billing ──────────────────────────────────────── */}
            {section === SECTION.Billing && (
              <motion.div
                key="billing"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-4"
              >
                <h2
                  className="text-base font-semibold text-[#e5e2e1] px-1"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  Subscription &amp; Billing
                </h2>

                <PlanCard />

                {!isPro && (
                  <Link
                    href="/pricing"
                    className="block text-center text-xs text-[#a38d7c] hover:text-[#e8b63f] transition-colors py-2"
                    style={{ fontFamily: "var(--font-ui)" }}
                  >
                    Compare all plans →
                  </Link>
                )}
              </motion.div>
            )}

            {/* ── API ──────────────────────────────────────────── */}
            {section === SECTION.API && (
              <motion.div
                key="api"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-4"
              >
                <div
                  className="rounded-2xl border border-white/10 p-6 space-y-5"
                  style={{ background: "rgba(28,27,27,0.8)" }}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <h2 className="text-base font-semibold text-[#e5e2e1] flex items-center gap-2" style={{ fontFamily: "var(--font-display)" }}>
                        <KeyRound className="w-4 h-4 text-[#e8b63f]" /> API Access
                      </h2>
                      <p className="text-xs text-[#a38d7c] mt-1">
                        Call PuranGPT from your own code with cited answers.{" "}
                        <Link href="/docs" className="text-[#e8b63f] hover:underline">Read the docs</Link>.
                      </p>
                    </div>
                    {isPro && (
                      <button
                        onClick={handleCreateKey}
                        disabled={creatingKey}
                        className="flex-shrink-0 flex items-center gap-1.5 px-4 py-2 bg-[#e8b63f] text-[#000000] rounded-lg text-sm font-medium hover:bg-[#ffb77a] transition-colors disabled:opacity-50"
                        style={{ fontFamily: "var(--font-ui)" }}
                      >
                        <Plus className="w-4 h-4" />
                        {creatingKey ? "Creating…" : "New key"}
                      </button>
                    )}
                  </div>

                  {!isPro ? (
                    <div className="flex items-center justify-between p-4 rounded-xl border border-[#e8b63f]/25" style={{ background: "rgba(232,182,63,0.05)" }}>
                      <p className="text-sm text-[#d8c594]">API access is a Pro feature.</p>
                      <button
                        onClick={openPaywall}
                        className="px-4 py-2 bg-[#e8b63f] text-[#000000] rounded-lg text-sm font-semibold hover:bg-[#ffb77a] transition-colors flex items-center gap-1.5"
                        style={{ fontFamily: "var(--font-ui)" }}
                      >
                        <Crown className="w-3.5 h-3.5" /> Upgrade to Pro
                      </button>
                    </div>
                  ) : (
                    <>
                      {/* One-time reveal of a freshly created key */}
                      {newKey && (
                        <div className="rounded-xl border border-[#e8b63f]/30 p-4" style={{ background: "rgba(232,182,63,0.06)" }}>
                          <p className="text-xs text-[#e8b63f] mb-2" style={{ fontFamily: "var(--font-ui)" }}>
                            Copy your key now — it won&apos;t be shown again.
                          </p>
                          <div className="flex items-center gap-2">
                            <code className="flex-1 min-w-0 truncate text-xs text-[#e5e2e1] bg-[#0e0e0e] rounded-lg px-3 py-2 font-mono">
                              {newKey}
                            </code>
                            <button
                              onClick={() => copyKey(newKey)}
                              className="flex-shrink-0 p-2 rounded-lg border border-white/10 text-[#a38d7c] hover:text-[#e5e2e1] hover:bg-white/5 transition-colors"
                              aria-label="Copy key"
                            >
                              <Copy className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => setNewKey(null)}
                              className="flex-shrink-0 text-xs text-[#a38d7c] hover:text-[#e5e2e1] px-2"
                              style={{ fontFamily: "var(--font-ui)" }}
                            >
                              Done
                            </button>
                          </div>
                        </div>
                      )}

                      {/* Existing keys */}
                      {keysLoading ? (
                        <p className="text-xs text-[#a38d7c]">Loading…</p>
                      ) : apiKeys.length === 0 ? (
                        <p className="text-xs text-[#a38d7c]">No keys yet. Create one to get started.</p>
                      ) : (
                        <div className="space-y-2">
                          {apiKeys.map((k) => (
                            <div key={k.id} className="flex items-center justify-between gap-3 p-3 rounded-xl border border-white/10" style={{ background: "rgba(255,255,255,0.02)" }}>
                              <div className="min-w-0">
                                <p className="text-sm text-[#e5e2e1] font-mono truncate">{k.prefix}…</p>
                                <p className="text-[11px] text-[#a38d7c] mt-0.5" style={{ fontFamily: "var(--font-ui)" }}>
                                  Created {new Date(k.created_at).toLocaleDateString()}
                                  {k.last_used_at ? ` · last used ${new Date(k.last_used_at).toLocaleDateString()}` : " · never used"}
                                </p>
                              </div>
                              <button
                                onClick={() => handleRevokeKey(k.id)}
                                className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-red-900/50 text-red-400 hover:bg-red-900/10 text-xs transition-colors"
                                style={{ fontFamily: "var(--font-ui)" }}
                              >
                                <Trash2 className="w-3.5 h-3.5" /> Revoke
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </motion.div>
            )}

            {/* ── Account ──────────────────────────────────────── */}
            {section === SECTION.Account && (
              <motion.div
                key="account"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-4"
              >
                <div
                  className="rounded-2xl border border-white/10 p-6 space-y-4"
                  style={{ background: "rgba(28,27,27,0.8)" }}
                >
                  <h2
                    className="text-base font-semibold text-[#e5e2e1]"
                    style={{ fontFamily: "var(--font-display)" }}
                  >
                    Account
                  </h2>

                  <button
                    onClick={handleSignOut}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-lg border border-white/10 text-[#a38d7c] hover:text-[#e5e2e1] hover:bg-white/5 text-sm transition-colors"
                    style={{ fontFamily: "var(--font-ui)" }}
                  >
                    <LogOut className="w-4 h-4" />
                    Sign out
                  </button>
                </div>

                <div
                  className="rounded-2xl border border-red-900/30 p-6 space-y-4"
                  style={{ background: "rgba(28,27,27,0.8)" }}
                >
                  <h3 className="text-sm font-semibold text-red-400" style={{ fontFamily: "var(--font-ui)" }}>
                    Danger Zone
                  </h3>
                  <p className="text-xs text-[#a38d7c]">
                    Deleting your account is permanent and cannot be undone. All your conversations and data will be removed.
                  </p>
                  {!deleteConfirm ? (
                    <button
                      onClick={handleDeleteAccount}
                      className="flex items-center gap-2 px-5 py-2.5 rounded-lg border border-red-900/50 text-red-400 hover:bg-red-900/10 text-sm transition-colors"
                      style={{ fontFamily: "var(--font-ui)" }}
                    >
                      <Trash2 className="w-4 h-4" />
                      Delete account &amp; data
                    </button>
                  ) : (
                    <div className="space-y-3">
                      <p className="text-sm text-red-400">
                        To confirm, please contact <span className="font-mono">support@purangpt.com</span> from your registered email address.
                      </p>
                      <button
                        onClick={() => setDeleteConfirm(false)}
                        className="text-xs text-[#a38d7c] hover:text-[#e5e2e1] transition-colors"
                        style={{ fontFamily: "var(--font-ui)" }}
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                </div>
              </motion.div>
            )}
          </main>
        </div>
      </div>
    </ProtectedRoute>
  );
}
