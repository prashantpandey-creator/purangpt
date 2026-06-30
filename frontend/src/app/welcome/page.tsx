"use client";

/**
 * The front door. The pattern every modern AI product uses:
 *  - returning / signed-in visitors skip straight to /chat (zero friction)
 *  - new / signed-out visitors land HERE — a marketing front page that presents
 *    PuranGPT (the Guru, the texts, the new voice darshan) and invites them in.
 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Sparkles, BookOpen, Mic, ArrowRight } from "lucide-react";
import { GurujiBindu } from "@/components/guruji/GurujiBindu";
import { useAuth } from "@/context/AuthContext";
import { useLanguage } from "@/context/LanguageContext";
import { getTranslation } from "@/lib/i18n";

export default function Home() {
  const router = useRouter();
  const { user, initialized } = useAuth();
  const { language } = useLanguage();

  const PILLARS = [
    {
      icon: Sparkles,
      title: getTranslation(language, "welcome.pillar1_title"),
      body: getTranslation(language, "welcome.pillar1_body"),
    },
    {
      icon: Mic,
      title: getTranslation(language, "welcome.pillar2_title"),
      badge: getTranslation(language, "welcome.pillar2_badge"),
      body: getTranslation(language, "welcome.pillar2_body"),
      href: "/darshan",
    },
    {
      icon: BookOpen,
      title: getTranslation(language, "welcome.pillar3_title"),
      body: getTranslation(language, "welcome.pillar3_body"),
      href: "/library",
    },
  ];

  // Returning / signed-in → straight into the product.
  useEffect(() => {
    if (initialized && user) router.replace("/chat");
  }, [initialized, user, router]);

  // While the auth check resolves (or we're redirecting a signed-in user), hold a
  // quiet orb so a signed-in visitor never flashes the marketing page.
  if (!initialized || user) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-[#0A0810]">
        <GurujiBindu state="resting" size={120} />
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-[#0A0810] text-[#e2e8f0] overflow-x-hidden">
      {/* minimal top bar */}
      <nav className="flex items-center justify-between px-6 py-5 md:px-10">
        <span className="text-lg tracking-wide text-[#a5b4fc]" style={{ fontFamily: "var(--font-display)" }}>
          PuranGPT
        </span>
        <Link
          href="/chat"
          className="text-sm text-[#94a3b8] hover:text-[#a78bfa] transition-colors"
          style={{ fontFamily: "var(--font-ui)" }}
        >
          {getTranslation(language, "welcome.sign_in")}
        </Link>
      </nav>

      {/* hero */}
      <section className="flex flex-col items-center px-6 pt-10 pb-20 text-center md:pt-16">
        <GurujiBindu state="resting" size={232} />

        <h1
          className="mt-10 text-4xl leading-tight text-[#a5b4fc] md:text-6xl"
          style={{ fontFamily: "var(--font-display)" }}
        >
          {getTranslation(language, "welcome.hero_line1")}
          <br className="hidden md:block" /> {getTranslation(language, "welcome.hero_line2")}
        </h1>

        <p
          className="mt-6 max-w-xl text-base leading-relaxed text-[#94a3b8] md:text-lg"
          style={{ fontFamily: "var(--font-body)" }}
        >
          {getTranslation(language, "welcome.hero_desc")}
        </p>

        <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row">
          <Link
            href="/chat"
            className="group inline-flex items-center gap-2 rounded-full px-8 py-3.5 text-base font-medium text-[#1a1206] transition-all"
            style={{ background: "linear-gradient(135deg,#a5b4fc,#a78bfa)", fontFamily: "var(--font-ui)" }}
          >
            {getTranslation(language, "welcome.cta_enter")}
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
          <Link
            href="/darshan"
            className="inline-flex items-center gap-2 rounded-full border border-[#a78bfa]/40 px-7 py-3.5 text-base text-[#a78bfa] transition-all hover:border-[#a78bfa]/70 hover:bg-[#a78bfa]/10"
            style={{ fontFamily: "var(--font-ui)" }}
          >
            <Mic className="h-4 w-4" />
            {getTranslation(language, "welcome.cta_speak")}
          </Link>
        </div>
      </section>

      {/* pillars */}
      <section className="mx-auto grid max-w-5xl gap-5 px-6 pb-24 md:grid-cols-3 md:px-10">
        {PILLARS.map(({ icon: Icon, title, body, badge, href }) => {
          const card = (
            <div className="h-full rounded-2xl border border-white/[0.06] bg-[#141121] p-7 transition-all hover:border-[#a78bfa]/25 hover:bg-[#16131F]">
              <div className="flex items-center gap-2.5">
                <Icon className="h-5 w-5 text-[#a78bfa]" />
                <h3 className="text-lg text-[#e2e8f0]" style={{ fontFamily: "var(--font-display)" }}>
                  {title}
                </h3>
                {badge && (
                  <span className="rounded-full bg-[#a78bfa]/15 px-2 py-0.5 text-[10px] uppercase tracking-widest text-[#a5b4fc]">
                    {badge}
                  </span>
                )}
              </div>
              <p
                className="mt-3 text-sm leading-relaxed text-[#94a3b8]"
                style={{ fontFamily: "var(--font-body)" }}
              >
                {body}
              </p>
            </div>
          );
          return href ? (
            <Link key={title} href={href} className="block">
              {card}
            </Link>
          ) : (
            <div key={title}>{card}</div>
          );
        })}
      </section>

      <footer className="border-t border-white/[0.05] px-6 py-8 text-center md:px-10">
        <p className="text-xs text-[#554336]" style={{ fontFamily: "var(--font-ui)" }}>
          {getTranslation(language, "welcome.footer")}
        </p>
      </footer>
    </main>
  );
}
