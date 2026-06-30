"use client";

import { motion, AnimatePresence } from "framer-motion";
import { X, Loader2, Check, Sparkles } from "lucide-react";
import { useSubscription } from "@/context/SubscriptionContext";
import { useState } from "react";

interface NativePaywallProps {
  isOpen: boolean;
  onClose: () => void;
}

const FEATURES = [
  "Unlimited queries",
  "Complete Vedic citations",
  "English, Hindi & Russian",
  "Priority support",
  "API access",
];

export function NativePaywall({ isOpen, onClose }: NativePaywallProps) {
  const [isAnnual, setIsAnnual] = useState(false);
  const [isPurchasing, setIsPurchasing] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);
  const [result, setResult] = useState<"success" | "notfound" | "unavailable" | null>(null);

  const { offerings, purchasePackage, restorePurchases } = useSubscription();

  const monthlyPkg = offerings?.current?.monthly;
  const annualPkg = offerings?.current?.annual;
  const selectedPkg = isAnnual ? annualPkg : monthlyPkg;

  const monthlyPrice = monthlyPkg?.product.priceString ?? "$9.99";
  const annualPrice = annualPkg?.product.priceString ?? "$99.99";

  const handlePurchase = async () => {
    if (!selectedPkg) {
      // Products never loaded from the App Store / StoreKit config — tell the
      // user rather than leaving the CTA looking inert.
      setResult("unavailable");
      setTimeout(() => setResult(null), 3000);
      return;
    }
    setIsPurchasing(true);
    const success = await purchasePackage(selectedPkg);
    setIsPurchasing(false);
    if (success) {
      setResult("success");
      setTimeout(onClose, 1400);
    }
  };

  const handleRestore = async () => {
    setIsRestoring(true);
    const hasPro = await restorePurchases();
    setIsRestoring(false);
    if (hasPro) {
      setResult("success");
      setTimeout(onClose, 1400);
    } else {
      setResult("notfound");
      setTimeout(() => setResult(null), 2500);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm"
          />

          {/* Sheet */}
          <motion.div
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", damping: 28, stiffness: 280 }}
            className="fixed bottom-0 left-0 right-0 z-50 rounded-t-[28px] safe-pb"
            style={{
              background: "linear-gradient(175deg, #1c1408 0%, #0d0a04 100%)",
              border: "1px solid rgba(232,182,63,0.2)",
              boxShadow:
                "0 -20px 60px rgba(232,182,63,0.12), 0 -1px 0 rgba(232,182,63,0.15)",
            }}
          >
            {/* Drag handle */}
            <div className="flex justify-center pt-3 pb-2">
              <div className="w-9 h-1 rounded-full bg-white/20" />
            </div>

            {/* Close button */}
            <button
              onClick={onClose}
              className="absolute right-5 top-5 p-1.5 rounded-full bg-white/5 text-gray-500 hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="px-6 pt-1 pb-6">
              {/* Header */}
              <div className="text-center mb-5">
                <div className="relative inline-flex mb-3">
                  <div className="absolute inset-0 blur-2xl bg-[#e8b63f]/40 scale-150" />
                  <Sparkles
                    className="relative w-9 h-9 text-[#f6d27a]"
                    style={{
                      filter: "drop-shadow(0 0 14px rgba(232,182,63,0.65))",
                    }}
                  />
                </div>
                <h2 className="text-2xl font-bold font-cinzel text-white leading-tight">
                  Unlock PuranGPT Pro
                </h2>
                <p className="text-[#a38d7c] text-sm mt-1">
                  Full access to ancient wisdom, unlimited
                </p>
              </div>

              {/* Feature list */}
              <div className="grid grid-cols-1 gap-2.5 mb-5">
                {FEATURES.map((f) => (
                  <div key={f} className="flex items-center gap-3">
                    <div
                      className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0"
                      style={{
                        background: "rgba(232,182,63,0.15)",
                        border: "1px solid rgba(232,182,63,0.4)",
                      }}
                    >
                      <Check className="w-3 h-3 text-[#e8b63f]" />
                    </div>
                    <span className="text-[#e2d4b2] text-sm">{f}</span>
                  </div>
                ))}
              </div>

              {/* Plan toggle */}
              <div
                className="flex rounded-xl p-1 mb-4"
                style={{
                  background: "rgba(255,255,255,0.05)",
                  border: "1px solid rgba(255,255,255,0.08)",
                }}
              >
                <button
                  onClick={() => setIsAnnual(false)}
                  className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    !isAnnual ? "bg-[#e8b63f] text-[#000000]" : "text-[#a38d7c]"
                  }`}
                >
                  Monthly
                  <div
                    className={`text-xs font-normal mt-0.5 ${
                      !isAnnual ? "text-[#000000]/70" : "text-[#6b5a4e]"
                    }`}
                  >
                    {monthlyPrice}/mo
                  </div>
                </button>

                <button
                  onClick={() => setIsAnnual(true)}
                  className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition-all relative ${
                    isAnnual ? "bg-[#e8b63f] text-[#000000]" : "text-[#a38d7c]"
                  }`}
                >
                  <span
                    className={`absolute -top-2.5 left-1/2 -translate-x-1/2 text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${
                      isAnnual
                        ? "bg-[#000000] text-[#e8b63f]"
                        : "bg-green-900/60 text-green-400"
                    }`}
                  >
                    −17%
                  </span>
                  Annual
                  <div
                    className={`text-xs font-normal mt-0.5 ${
                      isAnnual ? "text-[#000000]/70" : "text-[#6b5a4e]"
                    }`}
                  >
                    {annualPrice}/yr
                  </div>
                </button>
              </div>

              {/* Inline result feedback */}
              <AnimatePresence>
                {result && (
                  <motion.div
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className={`text-center text-sm mb-3 py-2 rounded-lg ${
                      result === "success"
                        ? "text-green-400 bg-green-900/20"
                        : "text-[#a38d7c] bg-white/5"
                    }`}
                  >
                    {result === "success"
                      ? "✓ Pro unlocked — enjoy unlimited access!"
                      : result === "unavailable"
                      ? "Subscriptions couldn't be loaded from the App Store. Check your connection and try again."
                      : "No active subscription found to restore."}
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Purchase CTA */}
              <button
                onClick={handlePurchase}
                disabled={isPurchasing}
                className="w-full py-4 rounded-2xl font-bold text-[#000000] text-base transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                style={{
                  background: "linear-gradient(135deg, #e8b63f 0%, #f6d27a 100%)",
                  boxShadow: isPurchasing
                    ? "none"
                    : "0 0 28px rgba(232,182,63,0.45)",
                }}
              >
                {isPurchasing ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  `Subscribe ${isAnnual ? "Annually" : "Monthly"}`
                )}
              </button>

              {/* Restore */}
              <button
                onClick={handleRestore}
                disabled={isRestoring}
                className="w-full text-center text-[#6b5a4e] text-xs mt-3 py-2 hover:text-[#a38d7c] transition-colors flex items-center justify-center gap-1.5"
              >
                {isRestoring && <Loader2 className="w-3 h-3 animate-spin" />}
                Restore Purchases
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
