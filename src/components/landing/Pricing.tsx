"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Check, X, Loader2, CreditCard, Shield } from "lucide-react";
import { useSubscription } from "@/context/SubscriptionContext";
import { useAuth } from "@/context/AuthContext";
import { Capacitor } from "@capacitor/core";
import { useLanguage } from "@/context/LanguageContext";
import { getTranslation, type Translations } from "@/lib/i18n";
import { SignInModal } from "@/components/auth/SignInModal";

// sessionStorage flag set right before we send a signed-out user through OAuth
// from the pricing page, so we can re-open the payment modal when they return.
const RESUME_CHECKOUT_KEY = "purangpt_resume_checkout";

export function Pricing() {
  const { language } = useLanguage();
  const [isAnnual, setIsAnnual] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);
  const [paymentModalOpen, setPaymentModalOpen] = useState(false);
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);

  const { isPro, offerings, purchasePackage, restorePurchases, isLoading } = useSubscription();
  const { user, refreshProfile } = useAuth();

  // After returning from sign-in (OAuth redirect or in-app modal), if the user
  // was mid-checkout, re-open the payment modal automatically. "Sign in first,
  // then pay" without making them hunt for the button again.
  useEffect(() => {
    if (Capacitor.isNativePlatform()) return;
    if (!user) return;
    if (typeof sessionStorage === "undefined") return;
    if (sessionStorage.getItem(RESUME_CHECKOUT_KEY) === "1") {
      sessionStorage.removeItem(RESUME_CHECKOUT_KEY);
      if (!isPro) {
        setSelectedPlan("pro");
        setPaymentModalOpen(true);
      }
    }
  }, [user, isPro]);

  const loadRazorpayScript = () => {
    return new Promise((resolve) => {
      const script = document.createElement("script");
      script.src = "https://checkout.razorpay.com/v1/checkout.js";
      script.onload = () => resolve(true);
      script.onerror = () => resolve(false);
      document.body.appendChild(script);
    });
  };

  const handleCheckout = async (provider: "stripe" | "razorpay") => {
    if (!selectedPlan) return;
    setIsProcessing(true);
    try {
      const origin = window.location.origin;
      const res = await fetch("/api/billing/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plan: selectedPlan,
          provider: provider,
          billing_cycle: isAnnual ? "annual" : "monthly",
          success_url: `${origin}/pricing?success=true&provider=${provider}`,
          cancel_url: `${origin}/pricing?cancel=true`
        })
      });

      if (!res.ok) {
        throw new Error(await res.text());
      }

      const data = await res.json();

      if (provider === "stripe") {
        window.location.href = data.url;
      } else if (provider === "razorpay") {
        const loaded = await loadRazorpayScript();
        if (!loaded) {
          alert("Failed to load Razorpay SDK. Please check your internet connection.");
          setIsProcessing(false);
          return;
        }

        const options = {
          key: data.key_id || process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID || "rzp_test_mock",
          amount: data.amount,
          currency: data.currency,
          name: "PuranGPT",
          description: `${selectedPlan.toUpperCase()} Plan Subscription`,
          order_id: data.id,
          handler: async function (response: any) {
            try {
              const verifyRes = await fetch("/api/billing/razorpay/verify", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  razorpay_order_id: response.razorpay_order_id,
                  razorpay_payment_id: response.razorpay_payment_id,
                  razorpay_signature: response.razorpay_signature,
                  plan: selectedPlan,
                  billing_cycle: isAnnual ? "annual" : "monthly",
                })
              });

              if (verifyRes.ok) {
                // Refresh the user's plan in AuthContext so Navbar shows Pro immediately
                await refreshProfile();
                window.location.href = "/chat?upgraded=1";
              } else {
                alert("Payment verification failed. Please contact support at support@purangpt.com");
              }
            } catch (err) {
              console.error(err);
              alert("Payment verification failed.");
            }
          },
          prefill: {
            email: user?.email || ""
          },
          theme: {
            color: "#e8b63f"
          }
        };

        const rzp = new (window as any).Razorpay(options);
        rzp.open();
        setPaymentModalOpen(false);
      }
    } catch (e: any) {
      console.error(e);
      alert(`Checkout failed: ${e.message || "Please try again later."}`);
    } finally {
      setIsProcessing(false);
    }
  };

  // On native iOS, use StoreKit's App Store price.
  // On web, show the Stripe price ($11.11/mo, $92.59/yr tax-inclusive).
  const monthlyPackage = offerings?.current?.monthly;
  const annualPackage = offerings?.current?.annual;

  const isNative = Capacitor.isNativePlatform();
  const proMonthlyPriceString = isNative
    ? (monthlyPackage?.product.priceString || "$9.99")
    : "$11.11";
  const proAnnualPriceString = isNative
    ? (annualPackage?.product.priceString || "$99.99")
    : "$92.59";

  const tiers: {
    name: string;
    nameKey: keyof Translations;
    descKey: keyof Translations;
    monthlyPrice: string;
    yearlyPrice: string;
    popular: boolean;
    packageToPurchase: any;
    features: { nameKey: keyof Translations; included: boolean }[];
  }[] = [
    {
      name: "Free",
      nameKey: "price.plan1.name",
      descKey: "price.plan1.desc",
      monthlyPrice: "$0",
      yearlyPrice: "$0",
      popular: false,
      packageToPurchase: null,
      features: [
        { nameKey: "price.plan1.feat1", included: true },
        { nameKey: "price.plan1.feat2", included: true },
        { nameKey: "price.plan1.feat3", included: false },
        { nameKey: "price.plan1.feat4", included: true },
        { nameKey: "price.plan1.feat5", included: false },
        { nameKey: "price.plan1.feat6", included: false },
      ],
    },
    {
      name: "Pro",
      nameKey: "price.plan2.name",
      descKey: "price.plan2.desc",
      monthlyPrice: proMonthlyPriceString,
      yearlyPrice: proAnnualPriceString,
      popular: true,
      packageToPurchase: isAnnual ? annualPackage : monthlyPackage,
      features: [
        { nameKey: "price.plan2.feat1", included: true },
        { nameKey: "price.plan2.feat2", included: true },
        { nameKey: "price.plan2.feat3", included: true },
        { nameKey: "price.plan2.feat4", included: true },
        { nameKey: "price.plan2.feat5", included: true },
        { nameKey: "price.plan2.feat6", included: true },
      ],
    },
    {
      name: "Enterprise",
      nameKey: "price.plan3.name",
      descKey: "price.plan3.desc",
      monthlyPrice: "Custom",
      yearlyPrice: "Custom",
      popular: false,
      packageToPurchase: null,
      features: [
        { nameKey: "price.plan3.feat1", included: true },
        { nameKey: "price.plan3.feat2", included: true },
        { nameKey: "price.plan3.feat3", included: true },
        { nameKey: "price.plan3.feat4", included: true },
        { nameKey: "price.plan3.feat5", included: true },
        { nameKey: "price.plan3.feat6", included: true },
      ],
    },
  ];

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.15,
      },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.6 },
    },
  };

  return (
    <section id="pricing" className="w-full py-24 px-4 sm:px-6 lg:px-8 bg-dark-900">
      <div className="max-w-6xl mx-auto">
        <motion.div
          className="text-center mb-16"
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-100px" }}
        >
          <motion.div variants={itemVariants} className="mb-5 flex items-center justify-center gap-3" aria-hidden>
            <span className="h-px w-8 bg-gradient-to-r from-transparent to-[#e8b63f]/50" />
            <span className="text-[11px] uppercase tracking-[0.32em] text-[#e8b63f]/80" style={{ fontFamily: "var(--font-marcellus)" }}>Plans</span>
            <span className="h-px w-8 bg-gradient-to-l from-transparent to-[#e8b63f]/50" />
          </motion.div>
          <motion.h2
            variants={itemVariants}
            className="text-4xl sm:text-5xl font-bold font-marcellus text-gradient mb-4"
          >
            {getTranslation(language, "price.title")}
          </motion.h2>
          <motion.p
            variants={itemVariants}
            className="text-[#a99c86] text-lg max-w-xl mx-auto mb-8"
          >
            {getTranslation(language, "price.subtitle")}
          </motion.p>

          {/* Toggle */}
          <motion.div variants={itemVariants} className="flex justify-center items-center gap-4">
            <span className={isAnnual ? "text-gray-400" : "text-white font-semibold"}>{getTranslation(language, "price.monthly")}</span>
            <button
              onClick={() => setIsAnnual(!isAnnual)}
              className="relative w-14 h-7 rounded-full bg-saffron/20 border border-saffron transition-all"
            >
              <motion.div
                className="absolute top-1 w-5 h-5 rounded-full bg-saffron"
                animate={{ x: isAnnual ? 28 : 4 }}
                transition={{ type: "spring", damping: 30 }}
              />
            </button>
            <span className={!isAnnual ? "text-gray-400" : "text-white font-semibold"}>
              {getTranslation(language, "price.yearly")}{" "}
              <span className="text-saffron text-sm ml-1">{isNative ? "Save 17%" : getTranslation(language, "price.save")}</span>
            </span>
          </motion.div>
        </motion.div>

        {/* Pricing Cards */}
        <motion.div
          className="grid md:grid-cols-3 gap-8"
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
        >
          {tiers.map((tier) => (
            <motion.div
              key={tier.name}
              variants={itemVariants}
              className={`relative rounded-2xl p-7 transition-all duration-300 ${
                tier.popular ? "md:scale-[1.04]" : "hover:-translate-y-1"
              }`}
              style={
                tier.popular
                  ? {
                      background: "linear-gradient(180deg, rgba(232,182,63,0.12), #16131F 55%)",
                      border: "1px solid rgba(232,182,63,0.45)",
                      boxShadow: "0 0 0 1px rgba(232,182,63,0.10), 0 28px 70px -28px rgba(232,182,63,0.35)",
                    }
                  : {
                      background: "linear-gradient(180deg, #16131F, #121019)",
                      border: "1px solid rgba(232,182,63,0.14)",
                    }
              }
            >
              {tier.popular && (
                <div className="mb-4 inline-block px-3 py-1 rounded-full bg-saffron/10 border border-saffron/30">
                  <span className="text-saffron text-xs font-semibold">{getTranslation(language, "price.most_popular")}</span>
                </div>
              )}

              <h3 className="text-2xl font-bold font-cinzel mb-2">{getTranslation(language, tier.nameKey)}</h3>
              <p className="text-gray-400 text-sm mb-6">{getTranslation(language, tier.descKey)}</p>

              <div className="mb-8">
                {tier.monthlyPrice !== "Custom" ? (
                  <>
                    <div className="text-5xl font-bold text-gradient leading-none" style={{ fontFamily: "var(--font-marcellus)" }}>
                      {isAnnual ? tier.yearlyPrice : tier.monthlyPrice}
                    </div>
                    <p className="text-[#7e92b8] text-sm mt-2.5">
                      {isAnnual ? getTranslation(language, "price.per_year") : getTranslation(language, "price.per_month")}
                    </p>
                  </>
                ) : (
                  <div className="text-3xl font-bold text-[#e2d4b2]" style={{ fontFamily: "var(--font-marcellus)" }}>{getTranslation(language, "price.custom")}</div>
                )}
              </div>

              <button
                onClick={async () => {
                  if (tier.name === "Free") {
                    window.location.href = "/chat";
                    return;
                  }
                  if (tier.name === "Enterprise") {
                    alert("Please contact support@purangpt.com for institutional deployments.");
                    return;
                  }

                  // Auth guard for paid tiers — sign in first, then pay.
                  // Open the in-app modal (Google + email) and remember that the
                  // user intended to check out, so we can resume after sign-in.
                  if (!user) {
                    if (typeof sessionStorage !== "undefined") {
                      sessionStorage.setItem(RESUME_CHECKOUT_KEY, "1");
                    }
                    setAuthModalOpen(true);
                    return;
                  }

                  if (Capacitor.isNativePlatform()) {
                    // Native: always use StoreKit IAP — never open web payment modal
                    if (tier.packageToPurchase) {
                      await purchasePackage(tier.packageToPurchase);
                    } else {
                      // Offerings failed to load (no products from the App Store /
                      // StoreKit config). Surface it instead of silently no-op'ing,
                      // which previously read as "the button does nothing".
                      alert(
                        "Subscription options couldn't be loaded from the App Store. " +
                          "Please check your connection and try again, or contact support@purangpt.com."
                      );
                    }
                    return;
                  }
                  setSelectedPlan("pro");
                  setPaymentModalOpen(true);
                }}
                disabled={isLoading || (tier.name === "Pro" && isPro)}
                className={`w-full py-3 rounded-lg font-semibold transition-all mb-8 flex items-center justify-center gap-2 ${
                  tier.name === "Pro" && isPro
                    ? "bg-[#e8b63f]/10 border border-[#e8b63f]/40 text-[#e8b63f] cursor-default"
                    : tier.popular
                    ? "btn-primary"
                    : "btn-secondary"
                }`}
              >
                {isLoading && tier.name === "Pro" && <Loader2 className="w-4 h-4 animate-spin" />}
                {tier.name === "Pro" && isPro
                  ? (
                    <span className="flex items-center gap-1.5">
                      <Check className="w-4 h-4" />
                      {getTranslation(language, "price.active_plan")}
                    </span>
                  )
                  : getTranslation(language, "price.get_started")}
              </button>

              {/* Manage link for active Pro web users */}
              {tier.name === "Pro" && isPro && !isNative && (
                <p className="text-center text-xs text-gray-500 -mt-5 mb-6">
                  <a
                    href="/settings?section=billing"
                    className="text-[#e8b63f] hover:text-[#e8b63f] transition-colors"
                  >
                    Manage or cancel →
                  </a>
                </p>
              )}

              <div className="space-y-3 pt-6" style={{ borderTop: "1px solid rgba(232,182,63,0.10)" }}>
                {tier.features.map((feature) => (
                  <div key={feature.nameKey} className="flex items-center gap-3 text-sm">
                    {feature.included ? (
                      <span className="flex h-[18px] w-[18px] flex-shrink-0 items-center justify-center rounded-full" style={{ background: "rgba(232,182,63,0.14)" }}>
                        <Check className="w-3 h-3 text-saffron" />
                      </span>
                    ) : (
                      <span className="flex h-[18px] w-[18px] flex-shrink-0 items-center justify-center rounded-full" style={{ background: "rgba(255,255,255,0.04)" }}>
                        <X className="w-3 h-3 text-gray-600" />
                      </span>
                    )}
                    <span className={feature.included ? "text-[#e2d4b2]" : "text-gray-600"}>
                      {getTranslation(language, feature.nameKey)}
                    </span>
                  </div>
                ))}
              </div>
            </motion.div>
          ))}
        </motion.div>

        {/* Trust strip — restrained conversion reassurance */}
        <div className="mt-12 flex flex-wrap items-center justify-center gap-x-7 gap-y-2.5 text-xs text-[#7e92b8]">
          <span className="flex items-center gap-1.5"><Shield className="w-3.5 h-3.5 text-[#e8b63f]/70" /> Secure checkout — Stripe &amp; Razorpay</span>
          <span className="hidden sm:inline text-[#e8b63f]/20">·</span>
          <span className="flex items-center gap-1.5"><Check className="w-3.5 h-3.5 text-[#e8b63f]/70" /> Cancel anytime</span>
          <span className="hidden sm:inline text-[#e8b63f]/20">·</span>
          <span className="flex items-center gap-1.5"><CreditCard className="w-3.5 h-3.5 text-[#e8b63f]/70" /> No hidden fees</span>
        </div>

        {/* Restore Purchases (Mobile Only) */}
        <div className="mt-12 text-center">
          <button
            onClick={async () => {
              const { Capacitor } = await import("@capacitor/core");
              if (!Capacitor.isNativePlatform()) {
                alert("Restore Purchases is only available in the mobile app.");
                return;
              }
              await restorePurchases();
            }}
            className="text-gray-400 hover:text-saffron text-sm transition-colors underline"
          >
            {getTranslation(language, "price.restore")}
          </button>
        </div>
      </div>

      {/* Payment Selection Modal */}
      <AnimatePresence>
        {paymentModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="relative w-full max-w-md rounded-2xl p-6 md:p-8"
              style={{
                background: 'rgba(18, 15, 12, 0.95)',
                border: '1px solid rgba(232,182,63, 0.35)',
                boxShadow: '0 24px 80px rgba(0,0,0,0.5)',
              }}
            >
              {/* Close Button */}
              <button
                onClick={() => setPaymentModalOpen(false)}
                className="absolute right-4 top-4 p-1.5 text-gray-400 hover:text-white rounded-lg transition-colors"
                disabled={isProcessing}
              >
                <X className="w-5 h-5" />
              </button>

              <div className="text-center mb-6">
                <Shield className="w-10 h-10 mx-auto text-saffron mb-3 animate-pulse" />
                <h3 className="text-2xl font-bold font-cinzel text-gray-100">{getTranslation(language, "price.modal.title")}</h3>
                <p className="text-gray-400 text-xs mt-1.5">{getTranslation(language, "price.modal.subtitle")}</p>
              </div>

              <div className="space-y-4">
                {/* Razorpay Option */}
                <button
                  onClick={() => handleCheckout("razorpay")}
                  disabled={isProcessing}
                  className="w-full flex items-center justify-between p-4 rounded-xl border border-saffron/20 bg-saffron/5 hover:bg-saffron/10 transition-all text-left group disabled:opacity-50"
                >
                  <div>
                    <h4 className="font-semibold text-gray-200 text-sm group-hover:text-saffron transition-colors">{getTranslation(language, "price.modal.razorpay")}</h4>
                    <p className="text-gray-400 text-xs mt-0.5">{getTranslation(language, "price.modal.razorpay_desc")}</p>
                  </div>
                  <Loader2 className={`w-4 h-4 text-saffron ${isProcessing ? 'animate-spin' : 'hidden'}`} />
                </button>

                {/* Stripe Option */}
                <button
                  onClick={() => handleCheckout("stripe")}
                  disabled={isProcessing}
                  className="w-full flex items-center justify-between p-4 rounded-xl border border-gray-700 bg-white/[0.02] hover:bg-white/[0.05] transition-all text-left group disabled:opacity-50"
                >
                  <div>
                    <h4 className="font-semibold text-gray-200 text-sm group-hover:text-saffron transition-colors">{getTranslation(language, "price.modal.stripe")}</h4>
                    <p className="text-gray-400 text-xs mt-0.5">{getTranslation(language, "price.modal.stripe_desc")}</p>
                  </div>
                  <CreditCard className="w-5 h-5 text-gray-400 group-hover:text-saffron transition-all" />
                </button>
              </div>

              {isProcessing && (
                <div className="mt-4 text-center">
                  <p className="text-xs text-saffron flex items-center justify-center gap-1.5 animate-pulse">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    {getTranslation(language, "price.modal.connecting")}
                  </p>
                </div>
              )}
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Sign-in — after Google OAuth, return to /pricing so the checkout-resume
          useEffect picks up the sessionStorage flag and re-opens the payment modal. */}
      <SignInModal isOpen={authModalOpen} onClose={() => setAuthModalOpen(false)} returnTo="/pricing" />
    </section>
  );
}
