"use client";

import { Crown, Check, Zap, Sparkles, ExternalLink, Loader2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useSubscription } from "@/context/SubscriptionContext";
import { usePaywall } from "@/context/PaywallContext";
import { Capacitor } from "@capacitor/core";
import { useState } from "react";

/**
 * PlanCard — the canonical "active plan" surface for the signed-in user flow.
 * Shows the current tier, status, renewal date and the entitlements that come
 * with it, plus the relevant CTA (Upgrade for Free users, Manage for Pro).
 * Reused on the Profile (account overview) and Settings → Billing screens so the
 * plan presentation stays consistent everywhere.
 */

const FREE_FEATURES = [
  "Scholar & Guru chat modes",
  "Cited verses from the Mahapuranas, Ramayana & Gita",
  "Limited daily questions",
];

const PRO_FEATURES = [
  "Unlimited questions, every day",
  "Deep Research — web-grounded synthesis",
  "Priority responses & longer context",
  "Early access to new modes",
];

function formatDate(iso?: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export function PlanCard() {
  const { user } = useAuth();
  const { isPro } = useSubscription();
  const { openPaywall } = usePaywall();
  const [portalLoading, setPortalLoading] = useState(false);
  const isNative = Capacitor.isNativePlatform();

  const handleManage = async () => {
    if (isNative) {
      // StoreKit/Apple manages subscriptions — open App Store subscriptions page
      window.open("https://apps.apple.com/account/subscriptions");
      return;
    }
    setPortalLoading(true);
    try {
      const res = await fetch("/api/billing/stripe/portal", { method: "POST" });
      const data = await res.json();
      if (data.url) window.location.href = data.url;
    } catch {
      /* ignore */
    } finally {
      setPortalLoading(false);
    }
  };

  const planLabel = isPro ? "Pro" : "Free";
  const status = user?.plan_status ?? "active";
  const renewsOn = formatDate(user?.plan_current_period_end);
  const features = isPro ? PRO_FEATURES : FREE_FEATURES;

  return (
    <div
      className="relative overflow-hidden rounded-2xl border p-6"
      style={{
        borderColor: isPro ? "rgba(232,182,63,0.30)" : "rgba(255,255,255,0.08)",
        background: isPro ? "rgba(232,182,63,0.05)" : "rgba(28,27,27,0.8)",
      }}
    >
      {/* Glow accent for Pro */}
      {isPro && (
        <div
          aria-hidden
          className="pointer-events-none absolute -top-16 -right-10 w-48 h-48 rounded-full blur-3xl opacity-50"
          style={{ background: "radial-gradient(circle, rgba(232,182,63,0.45), transparent 70%)" }}
        />
      )}

      <div className="relative flex items-start justify-between gap-4">
        <div>
          <p
            className="text-xs uppercase tracking-wider text-[#a38d7c]"
            style={{ fontFamily: "var(--font-ui)" }}
          >
            Current Plan
          </p>
          <div className="mt-1 flex items-center gap-2">
            {isPro ? (
              <Crown className="w-5 h-5 text-[#e8b63f] drop-shadow-[0_0_10px_rgba(232,182,63,0.65)]" />
            ) : (
              <Zap className="w-5 h-5 text-[#a38d7c]" />
            )}
            <h3
              className="text-xl font-semibold text-[#e5e2e1]"
              style={{ fontFamily: "var(--font-display)" }}
            >
              {planLabel}
            </h3>
          </div>

          {/* Status + renewal */}
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium capitalize ${
                status === "active"
                  ? "bg-emerald-500/10 text-emerald-300 border border-emerald-500/25"
                  : "bg-white/5 text-[#a38d7c] border border-white/10"
              }`}
              style={{ fontFamily: "var(--font-ui)" }}
            >
              {status}
            </span>
            {isPro && renewsOn && (
              <span className="text-[11px] text-[#a38d7c]" style={{ fontFamily: "var(--font-ui)" }}>
                Renews {renewsOn}
              </span>
            )}
          </div>
        </div>

        {/* CTA */}
        {!isPro && (
          <button
            onClick={openPaywall}
            className="flex-shrink-0 flex items-center gap-1.5 px-4 py-2 bg-[#e8b63f] text-[#000000] rounded-lg text-sm font-semibold hover:bg-[#ffb77a] transition-colors drop-shadow-[0_0_14px_rgba(232,182,63,0.45)]"
            style={{ fontFamily: "var(--font-ui)" }}
          >
            <Sparkles className="w-3.5 h-3.5" />
            Upgrade
          </button>
        )}
      </div>

      {/* Features */}
      <ul className="relative mt-5 space-y-2.5">
        {features.map((feat) => (
          <li key={feat} className="flex items-start gap-2.5">
            <Check className="w-4 h-4 mt-0.5 flex-shrink-0 text-[#e8b63f]" />
            <span className="text-sm text-[#cabfb6]" style={{ fontFamily: "var(--font-ui)" }}>
              {feat}
            </span>
          </li>
        ))}
      </ul>

      {/* Pro management */}
      {isPro && (
        <button
          onClick={handleManage}
          disabled={portalLoading}
          className="relative mt-5 flex items-center gap-1.5 text-xs text-[#a38d7c] hover:text-[#e8b63f] transition-colors disabled:opacity-50"
          style={{ fontFamily: "var(--font-ui)" }}
        >
          {portalLoading
            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
            : <ExternalLink className="w-3.5 h-3.5" />}
          {isNative ? "Manage in App Store" : "Manage subscription"}
        </button>
      )}
    </div>
  );
}
