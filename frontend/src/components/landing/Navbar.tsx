"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, MessageCircle, Users } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { LanguageSelector } from "@/components/ui/LanguageSelector";
import { SignInModal } from "@/components/auth/SignInModal";
import { AvatarMenu } from "@/components/auth/AvatarMenu";
import { Logo } from "@/components/ui/Logo";
import { useLanguage } from "@/context/LanguageContext";
import { getTranslation } from "@/lib/i18n";



export function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user, loading } = useAuth();
  const { language } = useLanguage();

  const [authModalOpen, setAuthModalOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <>
      <header
        className={`fixed top-0 inset-x-0 z-50 transition-all duration-300 safe-pt ${
          scrolled
            ? "bg-[#000000]/90 backdrop-blur-xl border-b border-white/5 shadow-lg"
            : "bg-transparent"
        }`}
      >
        <nav className="w-full px-4 sm:px-8 lg:px-12">
          <div className="flex h-16 items-center justify-between">
            {/* Logo */}
            <Link href="/" className="flex items-center gap-2.5 group" aria-label="PuranGPT home">
              <Logo href={null} size={44} glow="sm" />
              <span
                className="text-[22px] font-normal text-[#e2d4b2] leading-none tracking-wide ml-2"
                style={{ fontFamily: "var(--font-marcellus), serif" }}
              >
                PuranGPT
              </span>
            </Link>

            {/* Desktop CTA — minimal: a clear path back to chat + account/login */}
            <div className="hidden md:flex items-center gap-3">
              <Link
                href="/community"
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm transition-colors hover:bg-white/5"
                style={{ color: "#a38d7c", fontFamily: "var(--font-geist, sans-serif)" }}
              >
                <Users className="w-4 h-4" />
                Community
              </Link>
              <LanguageSelector />
              <Link
                href="/chat"
                className="flex items-center gap-1.5 px-5 py-2 bg-[#e8b63f] text-[#000000] rounded-xl font-semibold hover:bg-[#ffb77a] transition-colors text-sm active:scale-[0.98]"
                style={{ fontFamily: "var(--font-geist, sans-serif)" }}
              >
                <MessageCircle className="w-4 h-4" />
                {getTranslation(language, "nav2.back_to_chat")}
              </Link>
              {loading ? (
                <div className="h-8 w-8 rounded-full bg-white/5 animate-pulse" />
              ) : user ? (
                <AvatarMenu user={user} />
              ) : (
                <button
                  onClick={() => setAuthModalOpen(true)}
                  className="text-sm font-medium text-[#a38d7c] hover:text-[#e8b63f] transition-colors"
                  style={{ fontFamily: "var(--font-geist, sans-serif)" }}
                >
                  {getTranslation(language, "nav2.sign_in")}
                </button>
              )}
            </div>

            {/* Mobile toggle */}
            <button
              onClick={() => setMobileOpen((o) => !o)}
              className="md:hidden p-2 text-[#a38d7c] hover:text-[#e8b63f]"
              aria-label="Toggle menu"
            >
              {mobileOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </button>
          </div>
        </nav>

        {/* Mobile menu */}
        <AnimatePresence>
          {mobileOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="md:hidden overflow-hidden bg-[#000000]/95 backdrop-blur-xl border-b border-white/5"
            >
              <div className="px-4 py-4 space-y-1">
                <div className="flex flex-col gap-3">
                  <Link
                    href="/chat"
                    onClick={() => setMobileOpen(false)}
                    className="flex items-center justify-center gap-2 px-5 py-3 bg-[#e8b63f] text-[#000000] rounded-xl font-semibold hover:bg-[#ffb77a] transition-colors text-sm text-center"
                    style={{ fontFamily: "var(--font-geist, sans-serif)" }}
                  >
                    <MessageCircle className="w-4 h-4" />
                    {getTranslation(language, "nav2.back_to_chat")}
                  </Link>
                  <Link
                    href="/community"
                    onClick={() => setMobileOpen(false)}
                    className="flex items-center justify-center gap-2 px-5 py-3 border border-white/10 text-[#a38d7c] rounded-xl font-medium hover:bg-white/5 transition-colors text-sm text-center"
                    style={{ fontFamily: "var(--font-geist, sans-serif)" }}
                  >
                    <Users className="w-4 h-4" />
                    Community
                  </Link>
                  {loading ? (
                    <div className="h-12 rounded-xl bg-white/5 animate-pulse" />
                  ) : !user ? (
                    <button
                      onClick={() => { setMobileOpen(false); setAuthModalOpen(true); }}
                      className="px-5 py-3 border border-[#e8b63f]/40 text-[#e8b63f] rounded-xl font-medium hover:bg-white/5 transition-colors text-sm text-center"
                      style={{ fontFamily: "var(--font-geist, sans-serif)" }}
                    >
                      {getTranslation(language, "nav2.sign_in")}
                    </button>
                  ) : null}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </header>

      <SignInModal isOpen={authModalOpen} onClose={() => setAuthModalOpen(false)} />
    </>
  );
}
