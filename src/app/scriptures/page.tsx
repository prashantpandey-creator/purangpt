import type { Metadata } from "next";
import Link from "next/link";
import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";
import {
  JsonLd,
  breadcrumbSchema,
} from "@/components/seo/StructuredData";
import { SCRIPTURES } from "./texts";

const SITE_URL = "https://purangpt.com";

export const metadata: Metadata = {
  title: "Hindu Sacred Texts — Scriptures Guide",
  description:
    "Explore the Bhagavad Gita, Ramayana, Mahabharata, the Mahapuranas, the Upanishads, and the Vedas. Read concise, reverent overviews of each scripture and ask PuranGPT for answers grounded in exact verse citations.",
  alternates: { canonical: "/scriptures" },
  openGraph: {
    title: "Hindu Sacred Texts — Scriptures Guide | PuranGPT",
    description:
      "Concise overviews of the Bhagavad Gita, Ramayana, Mahabharata, the Mahapuranas, the Upanishads, and the Vedas — and a way to ask each one your questions.",
    url: `${SITE_URL}/scriptures`,
    type: "website",
  },
};

export default function ScripturesIndexPage() {
  const breadcrumbs = breadcrumbSchema([
    { name: "Home", url: `${SITE_URL}/` },
    { name: "Scriptures", url: `${SITE_URL}/scriptures` },
  ]);

  return (
    <>
      <JsonLd schema={breadcrumbs} />
      <Navbar />
      <main className="pt-24 min-h-screen pb-20">
        {/* ─── Hero ─── */}
        <section className="px-4 md:px-16 pt-12 pb-14 text-center relative overflow-hidden">
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-full max-w-2xl h-[280px] bg-[#f0cd80]/5 blur-[100px] pointer-events-none" />
          <div className="relative z-10 max-w-3xl mx-auto space-y-5">
            <span
              className="text-[10px] uppercase tracking-[0.28em] text-[#a38d7c]"
              style={{ fontFamily: "var(--font-ui)" }}
            >
              The Sacred Corpus
            </span>
            <h1
              className="text-4xl md:text-5xl text-gradient leading-tight"
              style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}
            >
              Hindu Sacred Texts
            </h1>
            <p
              className="text-base md:text-lg text-[#c7ae9a] leading-relaxed"
              style={{ fontFamily: "var(--font-body)" }}
            >
              From the Bhagavad Gita and the great epics to the eighteen
              Mahapuranas, the Upanishads, and the Vedas — explore the scriptures
              that shape the Hindu tradition, then ask PuranGPT any question and
              receive answers grounded in exact verse citations.
            </p>
          </div>
        </section>

        {/* ─── Text cards ─── */}
        <section className="px-4 md:px-16 max-w-[1200px] mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-5">
            {SCRIPTURES.map((text) => (
              <Link
                key={text.slug}
                href={`/scriptures/${text.slug}`}
                className="group glass-panel rounded-2xl p-6 flex flex-col gap-3 transition-all duration-300 hover:-translate-y-1 hover:border-[#f0cd80]/25 hover:shadow-[0_22px_55px_rgba(232,182,63,0.08)]"
              >
                <div className="flex items-start justify-between gap-2">
                  <span
                    className="text-[10px] uppercase tracking-widest text-[#f0cd80]"
                    style={{ fontFamily: "var(--font-ui)" }}
                  >
                    {text.category}
                  </span>
                  <span
                    lang="sa"
                    className="text-sm text-[#a38d7c] leading-none"
                    style={{ fontFamily: "var(--font-display)" }}
                  >
                    {text.sanskritName}
                  </span>
                </div>

                <h2
                  className="text-xl md:text-2xl text-[#f0cd80] leading-snug"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  {text.name}
                </h2>

                <p
                  className="text-sm text-[#bfa78f] leading-relaxed truncate-3"
                  style={{ fontFamily: "var(--font-body)" }}
                >
                  {text.summary}
                </p>

                <span
                  className="mt-auto pt-3 inline-flex items-center gap-1.5 text-[11px] uppercase tracking-widest text-[#d8c594] group-hover:text-[#f6d27a] transition-colors"
                  style={{ fontFamily: "var(--font-ui)" }}
                >
                  Read overview
                  <span aria-hidden className="transition-transform duration-300 group-hover:translate-x-1">
                    →
                  </span>
                </span>
              </Link>
            ))}
          </div>
        </section>

        {/* ─── CTA ─── */}
        <section className="px-4 md:px-16 max-w-3xl mx-auto mt-16 text-center">
          <p
            className="text-sm text-[#a38d7c] mb-5"
            style={{ fontFamily: "var(--font-body)" }}
          >
            Have a question for the scriptures? Ask it in your own words.
          </p>
          <div className="flex flex-wrap gap-4 justify-center">
            <Link href="/chat" className="btn-primary">
              Ask PuranGPT
            </Link>
            <Link href="/library" className="btn-secondary">
              Browse the Library
            </Link>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
