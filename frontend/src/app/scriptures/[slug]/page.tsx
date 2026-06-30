import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";
import {
  JsonLd,
  articleSchema,
  breadcrumbSchema,
  faqSchema,
} from "@/components/seo/StructuredData";
import { SCRIPTURES, getScriptureBySlug } from "../texts";

const SITE_URL = "https://purangpt.com";

/** Statically generate one page per scripture at build time. */
export function generateStaticParams() {
  return SCRIPTURES.map((text) => ({ slug: text.slug }));
}

/**
 * Reject any slug that isn't one of the 12 real scriptures with a hard 404.
 * Without this, Next's default (dynamicParams = true) renders unknown slugs
 * on-demand and returns a soft 200 — Google then indexes empty phantom URLs
 * as thin/duplicate content. This pins the route to generateStaticParams only.
 */
export const dynamicParams = false;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const text = getScriptureBySlug(slug);

  if (!text) {
    return { title: "Scripture not found" };
  }

  const title = `${text.name} — Overview, Themes & Key Questions`;
  const description = text.summary.length > 158
    ? `${text.summary.slice(0, 155).trimEnd()}…`
    : text.summary;

  return {
    title,
    description,
    alternates: { canonical: `/scriptures/${text.slug}` },
    openGraph: {
      title: `${text.name} | PuranGPT`,
      description,
      url: `${SITE_URL}/scriptures/${text.slug}`,
      type: "article",
    },
  };
}

export default async function ScripturePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const text = getScriptureBySlug(slug);

  if (!text) {
    notFound();
  }

  const pageUrl = `${SITE_URL}/scriptures/${text.slug}`;

  // Resolve related-text slugs into real entries (drops any that don't resolve).
  const related = (text.relatedTexts ?? [])
    .map((s) => getScriptureBySlug(s))
    .filter((t): t is NonNullable<typeof t> => Boolean(t));

  const breadcrumbs = breadcrumbSchema([
    { name: "Home", url: `${SITE_URL}/` },
    { name: "Scriptures", url: `${SITE_URL}/scriptures` },
    { name: text.name, url: pageUrl },
  ]);

  const article = articleSchema({
    headline: `${text.name} — Overview, Themes & Key Questions`,
    description: text.summary,
    url: pageUrl,
  });

  // Turn each seeker question into an FAQ entry whose answer routes them to the
  // chat — honest about where the real, cited answer is produced.
  const faq = faqSchema(
    text.sampleQuestions.map((q) => ({
      question: q,
      answer: `Ask PuranGPT this question to receive an answer drawn from the ${text.name} with exact verse citations.`,
    }))
  );

  return (
    <>
      <JsonLd schema={breadcrumbs} />
      <JsonLd schema={article} />
      <JsonLd schema={faq} />
      <Navbar />
      <main className="pt-24 min-h-screen pb-20">
        <article className="px-4 md:px-8 max-w-3xl mx-auto">
          {/* ─── Breadcrumb ─── */}
          <nav
            aria-label="Breadcrumb"
            className="flex items-center gap-2 text-[11px] uppercase tracking-widest text-[#a38d7c] mb-8"
            style={{ fontFamily: "var(--font-ui)" }}
          >
            <Link href="/" className="hover:text-[#f0cd80] transition-colors">
              Home
            </Link>
            <span aria-hidden>/</span>
            <Link
              href="/scriptures"
              className="hover:text-[#f0cd80] transition-colors"
            >
              Scriptures
            </Link>
            <span aria-hidden>/</span>
            <span className="text-[#d8c594]">{text.name}</span>
          </nav>

          {/* ─── Header ─── */}
          <header className="mb-12 text-center relative overflow-hidden">
            <div className="absolute -top-6 left-1/2 -translate-x-1/2 w-full max-w-md h-[200px] bg-[#f0cd80]/5 blur-[90px] pointer-events-none" />
            <div className="relative z-10 space-y-4">
              <span
                className="text-[10px] uppercase tracking-[0.28em] text-[#a38d7c]"
                style={{ fontFamily: "var(--font-ui)" }}
              >
                {text.category}
              </span>
              <h1
                className="text-4xl md:text-5xl text-gradient leading-tight"
                style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}
              >
                {text.name}
              </h1>
              <p
                lang="sa"
                className="text-2xl text-[var(--sanskrit-text)]"
                style={{ fontFamily: "var(--font-display)" }}
              >
                {text.sanskritName}
              </p>
            </div>
          </header>

          {/* ─── Overview ─── */}
          <section className="mb-12">
            <h2
              className="text-2xl text-[#f0cd80] mb-4"
              style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}
            >
              Overview
            </h2>
            <p
              className="text-base md:text-lg text-[#d8c8b0] leading-relaxed"
              style={{ fontFamily: "var(--font-body)" }}
            >
              {text.summary}
            </p>
          </section>

          {/* ─── Themes ─── */}
          <section className="mb-12">
            <h2
              className="text-2xl text-[#f0cd80] mb-5"
              style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}
            >
              Major Themes
            </h2>
            <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {text.themes.map((theme) => (
                <li
                  key={theme}
                  className="glass-panel rounded-xl px-4 py-3 text-sm text-[#d8c594] leading-snug"
                  style={{ fontFamily: "var(--font-body)" }}
                >
                  {theme}
                </li>
              ))}
            </ul>
          </section>

          {/* ─── Questions seekers ask ─── */}
          <section className="mb-12">
            <h2
              className="text-2xl text-[#f0cd80] mb-2"
              style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}
            >
              Questions Seekers Ask
            </h2>
            <p
              className="text-sm text-[#a38d7c] mb-5"
              style={{ fontFamily: "var(--font-body)" }}
            >
              Tap any question to ask PuranGPT and receive an answer grounded in
              exact verse citations from the {text.name}.
            </p>
            <ul className="flex flex-col gap-3">
              {text.sampleQuestions.map((q) => (
                <li key={q}>
                  <Link
                    href={`/?q=${encodeURIComponent(q)}`}
                    className="group flex items-center justify-between gap-3 glass-panel rounded-xl px-5 py-4 transition-all duration-300 hover:-translate-y-0.5 hover:border-[#f0cd80]/25 hover:shadow-[0_18px_45px_rgba(232,182,63,0.08)]"
                  >
                    <span
                      className="text-sm md:text-base text-[#e5e2e1] leading-snug"
                      style={{ fontFamily: "var(--font-body)" }}
                    >
                      {q}
                    </span>
                    <span
                      aria-hidden
                      className="text-[#f0cd80] transition-transform duration-300 group-hover:translate-x-1"
                    >
                      →
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>

          {/* ─── Related scriptures (topical cross-links) ─── */}
          {related.length > 0 && (
            <section className="mb-12">
              <h2
                className="text-2xl text-[#f0cd80] mb-5"
                style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}
              >
                Related Scriptures
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {related.map((r) => (
                  <Link
                    key={r.slug}
                    href={`/scriptures/${r.slug}`}
                    className="group glass-panel rounded-2xl p-5 flex flex-col gap-2 transition-all duration-300 hover:-translate-y-1 hover:border-[#f0cd80]/25 hover:shadow-[0_18px_45px_rgba(232,182,63,0.08)]"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span
                        className="text-[10px] uppercase tracking-widest text-[#f0cd80]"
                        style={{ fontFamily: "var(--font-ui)" }}
                      >
                        {r.category}
                      </span>
                      <span
                        lang="sa"
                        className="text-sm text-[#a38d7c] leading-none"
                        style={{ fontFamily: "var(--font-devanagari)" }}
                      >
                        {r.sanskritName}
                      </span>
                    </div>
                    <h3
                      className="text-lg text-[#e5e2e1] leading-snug"
                      style={{ fontFamily: "var(--font-display)" }}
                    >
                      {r.name}
                    </h3>
                  </Link>
                ))}
              </div>
            </section>
          )}

          {/* ─── CTA ─── */}
          <section className="text-center pt-2">
            <div className="flex flex-wrap gap-4 justify-center">
              <Link href="/chat" className="btn-primary">
                Ask PuranGPT
              </Link>
              <Link href="/scriptures" className="btn-secondary">
                All Scriptures
              </Link>
            </div>
          </section>
        </article>
      </main>
      <Footer />
    </>
  );
}
