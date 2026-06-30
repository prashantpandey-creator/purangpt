"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { X, ArrowLeft, Mail, Lock, Loader2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Logo } from "@/components/ui/Logo";
import { recordConsent } from "@/lib/consent";

interface SignInModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** After OAuth completes, redirect here instead of the default /chat */
  returnTo?: string;
}

type View = "menu" | "email";

export function SignInModal({ isOpen, onClose, returnTo }: SignInModalProps) {
  const { signIn, signInWithEmail } = useAuth();
  const [agreed, setAgreed] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [view, setView] = useState<View>("menu");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [emailLoading, setEmailLoading] = useState(false);
  const [checkFlash, setCheckFlash] = useState(false);
  const emailRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Reset view + fields when modal opens/closes
  useEffect(() => {
    if (isOpen) {
      setView("menu");
      setEmail("");
      setPassword("");
      setError("");
    }
  }, [isOpen]);

  // Focus email field when switching to email view
  useEffect(() => {
    if (view === "email") {
      setTimeout(() => emailRef.current?.focus(), 100);
    }
  }, [view]);

  /**
   * When a disabled button is clicked, flash the Terms checkbox to show the user
   * what they're missing — instead of a silent dead tap.
   */
  const nudgeConsent = useCallback(() => {
    setCheckFlash(true);
    setTimeout(() => setCheckFlash(false), 700);
  }, []);

  const recordAndProceed = useCallback(
    (provider?: "google") => {
      const deviceId =
        typeof window !== "undefined" ? localStorage.getItem("purangpt_device_id") : null;
      void recordConsent({ consentType: "signup", deviceId });
      onClose();
      if (provider === "google") signIn("google", returnTo);
      // No else: all sign-in paths go through explicit methods (Google or email form).
      // The old Logto-hosted UI redirect has been removed.
    },
    [signIn, onClose, returnTo],
  );

  const handleEmailSignIn = useCallback(async () => {
    if (!email.trim() || !password) {
      setError("Please enter your email and password.");
      return;
    }
    setError("");
    setEmailLoading(true);

    try {
      const deviceId =
        typeof window !== "undefined" ? localStorage.getItem("purangpt_device_id") : null;
      void recordConsent({ consentType: "signup", deviceId });
      await signInWithEmail(email.trim(), password);
      onClose();
    } catch (e: any) {
      setError(e?.message || "Sign in failed. Please check your credentials.");
    } finally {
      setEmailLoading(false);
    }
  }, [email, password, signInWithEmail, onClose]);

  const handleEmailKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleEmailSignIn();
  };

  const modalContent = (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0, y: 10 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.95, opacity: 0, y: 10 }}
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-sm rounded-[24px] border border-white/10 bg-[#141121] p-8 shadow-2xl overflow-hidden"
          >
            {/* Background Accents */}
            <div className="absolute -top-16 -right-16 h-32 w-32 rounded-full bg-[#7c3aed]/10 blur-2xl" />
            <div className="absolute -bottom-16 -left-16 h-32 w-32 rounded-full bg-[#e8b63f]/5 blur-2xl" />

            <button
              onClick={onClose}
              className="absolute top-5 right-5 text-[#94a3b8] hover:text-white transition-colors z-10"
            >
              <X className="w-5 h-5" />
            </button>

            {/* ── Menu View ──────────────────────────────────────────── */}
            {view === "menu" && (
              <>
                <div className="flex flex-col items-center text-center gap-2 mb-8 mt-4 relative z-10">
                  <div className="mb-2">
                    <Logo size={64} glow="lg" href={null} />
                  </div>
                  <h2 className="text-2xl font-bold text-gradient" style={{ fontFamily: "var(--font-marcellus), serif" }}>
                    Atithi Devo Bhava
                  </h2>
                  <p className="text-sm text-[#a38d7c]">The guest is God — enter and ask</p>
                </div>

                <div className="flex flex-col gap-4 relative z-10">
                  {/* Google — top, prominent */}
                  <button
                    onClick={() => (agreed ? recordAndProceed("google") : nudgeConsent())}
                    className="flex items-center justify-center gap-3 w-full py-3 px-4 bg-white hover:bg-gray-100 text-gray-900 rounded-[8px] font-medium transition-colors"
                  >
                    <svg viewBox="0 0 24 24" className="w-5 h-5">
                      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
                      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
                    </svg>
                    Continue with Google
                  </button>

                  <div className="relative flex items-center py-2">
                    <div className="flex-grow border-t border-white/10"></div>
                    <span className="flex-shrink-0 mx-4 text-xs text-[#94a3b8]">or</span>
                    <div className="flex-grow border-t border-white/10"></div>
                  </div>

                  {/* Email — opens custom form (API-driven, no Logto UI) */}
                  <button
                    onClick={() => (agreed ? setView("email") : nudgeConsent())}
                    className="flex items-center justify-center gap-3 w-full py-3 px-4 bg-[#2a2a2a] hover:bg-[#353535] border border-white/5 text-white rounded-[8px] font-medium transition-colors"
                  >
                    <Mail className="w-4 h-4" />
                    Continue with Email
                  </button>

                  {/* Terms checkbox — BELOW the buttons. Natural flow: see button → try to tap →
                      notice it's disabled → look down → find the checkbox. */}
                  <motion.label
                    animate={checkFlash ? { scale: [1, 1.03, 1], borderColor: ["rgba(232,182,63,0.2)", "rgba(232,182,63,0.8)", "rgba(232,182,63,0.2)"] } : {}}
                    className="flex items-start gap-2.5 cursor-pointer select-none rounded-lg p-2.5 transition-colors"
                    style={{ background: checkFlash ? "rgba(232,182,63,0.08)" : "transparent" }}
                  >
                    <input
                      type="checkbox"
                      checked={agreed}
                      onChange={(e) => setAgreed(e.target.checked)}
                      className="mt-0.5 h-4 w-4 shrink-0 accent-[#a78bfa] cursor-pointer"
                    />
                    <span className="text-left text-[11px] leading-relaxed text-[#94a3b8]">
                      I agree to the{" "}
                      <a href="/terms" target="_blank" rel="noopener noreferrer" className="text-[#a78bfa] hover:underline">
                        Terms of Service
                      </a>{" "}
                      and{" "}
                      <a href="/privacy" target="_blank" rel="noopener noreferrer" className="text-[#a78bfa] hover:underline">
                        Privacy Policy
                      </a>
                      .
                    </span>
                  </motion.label>
                </div>
              </>
            )}

            {/* ── Email View ──────────────────────────────────────────── */}
            {view === "email" && (
              <>
                <div className="flex items-center gap-3 mb-6 mt-2 relative z-10">
                  <button
                    onClick={() => { setView("menu"); setError(""); }}
                    className="text-[#94a3b8] hover:text-white transition-colors p-1 -ml-1"
                  >
                    <ArrowLeft className="w-5 h-5" />
                  </button>
                  <h2
                    className="text-xl font-bold text-[#e2e8f0]"
                    style={{ fontFamily: "var(--font-marcellus), serif" }}
                  >
                    Continue with Email
                  </h2>
                </div>

                <div className="flex flex-col gap-4 relative z-10">
                  {/* Email field */}
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94a3b8]" />
                    <input
                      ref={emailRef}
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      onKeyDown={handleEmailKeyDown}
                      placeholder="your@email.com"
                      autoComplete="email"
                      className="w-full pl-10 pr-4 py-3 bg-[#1a1a2e] border border-white/10 rounded-[8px] text-white placeholder-[#5a5a7a] focus:outline-none focus:border-[#a78bfa]/50 focus:ring-1 focus:ring-[#a78bfa]/30 transition-colors text-sm"
                    />
                  </div>

                  {/* Password field */}
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94a3b8]" />
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      onKeyDown={handleEmailKeyDown}
                      placeholder="Your password"
                      autoComplete="current-password"
                      className="w-full pl-10 pr-4 py-3 bg-[#1a1a2e] border border-white/10 rounded-[8px] text-white placeholder-[#5a5a7a] focus:outline-none focus:border-[#a78bfa]/50 focus:ring-1 focus:ring-[#a78bfa]/30 transition-colors text-sm"
                    />
                  </div>

                  {/* Error */}
                  {error && (
                    <motion.p
                      initial={{ opacity: 0, y: -4 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="text-xs text-red-400 bg-red-400/10 rounded-[6px] px-3 py-2 border border-red-400/20"
                    >
                      {error}
                    </motion.p>
                  )}

                  {/* Submit */}
                  <button
                    onClick={handleEmailSignIn}
                    disabled={emailLoading}
                    className="flex items-center justify-center gap-2 w-full py-3 px-4 bg-[#a78bfa] hover:bg-[#a5b4fc] text-[#000000] rounded-[8px] font-semibold transition-colors disabled:opacity-60 disabled:cursor-not-allowed text-sm"
                  >
                    {emailLoading ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Continuing...
                      </>
                    ) : (
                      "Continue"
                    )}
                  </button>

                  {/* Sign-up hint — new users are auto-created by Logto */}
                  <p className="text-center text-[11px] text-[#94a3b8] leading-relaxed">
                    New to PuranGPT? Your account will be created automatically.
                  </p>

                  {/* Forgot password — links to Logto's reset flow */}
                  <p className="text-center text-[11px] text-[#94a3b8]">
                    <a
                      href={`${process.env.NEXT_PUBLIC_LOGTO_ENDPOINT || 'https://auth.purangpt.com'}/forgot-password`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:text-[#a78bfa] transition-colors"
                    >
                      Forgot your password?
                    </a>
                  </p>
                </div>
              </>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );

  if (!mounted) return null;
  return createPortal(modalContent, document.body);
}
