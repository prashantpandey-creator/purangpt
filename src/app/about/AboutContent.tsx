"use client";

import Link from "next/link";
import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";
import { LiveComparison } from "@/components/landing/LiveComparison";
import { BookOpen, ScrollText, Library, Brain, Flame } from "lucide-react";
import { useLanguage } from "@/context/LanguageContext";
import { getTranslation } from "@/lib/i18n";

interface VerseBlockProps {
  number: string;
  devanagari: string;
  transliteration: string;
  translation: string;
  source: string;
}

function VerseBlock({ number, devanagari, transliteration, translation, source }: VerseBlockProps) {
  return (
    <div className="relative py-8 px-6 md:px-10 border-l-2 border-[#f0cd80]/40 bg-[#0e0c09]/60 rounded-r-xl">
      <span
        className="absolute -left-px top-6 -translate-x-1/2 bg-[#f0cd80] text-[#0e0c09] text-[10px] font-bold px-2 py-0.5 rounded-full"
        style={{ fontFamily: "var(--font-ui)", letterSpacing: "0.1em" }}
      >
        {number}
      </span>

      <p
        lang="sa"
        className="text-xl md:text-2xl leading-loose text-[var(--sanskrit-text)] mb-3"
        style={{ fontFamily: "var(--font-devanagari)", fontStyle: "normal" }}
      >
        {devanagari}
      </p>

      <p
        className="text-sm md:text-base italic text-[#d8c594] leading-relaxed mb-4"
        style={{ fontFamily: "var(--font-display)", letterSpacing: "0.02em" }}
      >
        {transliteration}
      </p>

      <p
        className="text-base md:text-lg text-[#e5e2e1] leading-relaxed border-l border-[#f0cd80]/20 pl-4"
        style={{ fontFamily: "var(--font-display)" }}
      >
        &ldquo;{translation}&rdquo;
      </p>

      <p
        className="mt-4 text-[10px] uppercase tracking-[0.2em] text-[#a38d7c]"
        style={{ fontFamily: "var(--font-ui)" }}
      >
        {source}
      </p>
    </div>
  );
}

// Sacred verse text is content, not UI chrome — kept verbatim across locales.
const previewSources = [
  {
    text: "न त्वेवाहं जातु नासं न त्वं नेमे जनाधिपाः। न चैव न भविष्यामः सर्वे वयमतः परम्॥",
    transliteration: "na tv evāhaṃ jātu nāsaṃ na tvaṃ neme janādhipāḥ",
    translation: "Never was there a time when I did not exist, nor you, nor all these beings; nor in the future shall any of us cease to be.",
    source: "Bhagavad Gita 2.12",
    tag: "Gita",
  },
  {
    text: "सत्यमेव जयते नानृतं सत्येन पन्था विततो देवयानः।",
    transliteration: "satyam eva jayate nānṛtaṃ satye panthā vitato devayānaḥ",
    translation: "Truth alone triumphs; not falsehood. Through truth the divine path is spread out.",
    source: "Mundaka Upanishad 3.1.6",
    tag: "Upanishad",
  },
  {
    text: "यत्र योगेश्वरः कृष्णो यत्र पार्थो धनुर्धरः। तत्र श्रीर्विजयो भूतिर्ध्रुवा नीतिर्मतिर्मम॥",
    transliteration: "yatra yogeśvaraḥ kṛṣṇo yatra pārtho dhanur-dharaḥ",
    translation: "Wherever there is Krishna, the master of yoga, and wherever there is Arjuna, the supreme archer — there will certainly be opulence, victory, power, and morality.",
    source: "Bhagavad Gita 18.78",
    tag: "Gita",
  },
];

export function AboutContent() {
  const { language } = useLanguage();
  const t = (key: Parameters<typeof getTranslation>[1]) => getTranslation(language, key);

  const corpus = [
    { label: t("about.corpus.label.mahapuranas"), sub: t("about.corpus.sub.collection"), icon: <Library className="w-5 h-5" /> },
    { label: t("about.corpus.label.mahabharata"), sub: t("about.corpus.sub.epic"), icon: <ScrollText className="w-5 h-5" /> },
    { label: t("about.corpus.label.upanishads"), sub: t("about.corpus.sub.philosophy"), icon: <Brain className="w-5 h-5" /> },
    { label: t("about.corpus.label.yoga"), sub: t("about.corpus.sub.practice"), icon: <Flame className="w-5 h-5" /> },
  ];

  return (
    <main className="bg-[#000000] text-[#e5e2e1] min-h-screen">
      <Navbar />

      {/* ─── Hero ─── */}
      <section className="pt-32 pb-20 px-4 md:px-16 text-center relative overflow-hidden">
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-full max-w-2xl h-[300px] bg-[#f0cd80]/5 blur-[100px] pointer-events-none" />
        <div className="relative z-10 max-w-3xl mx-auto space-y-6">
          <span
            className="text-[10px] uppercase tracking-[0.28em] text-[#a38d7c]"
            style={{ fontFamily: "var(--font-ui)" }}
          >
            {t("about.eyebrow")}
          </span>
          <h1
            className="text-4xl md:text-5xl text-[#f0cd80]"
            style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}
          >
            PuranGPT
          </h1>
          <p
            className="text-base md:text-lg text-[#c7ae9a] leading-relaxed"
            style={{ fontFamily: "var(--font-body)" }}
          >
            {t("about.mission")}
          </p>
          <div className="flex gap-4 justify-center pt-2">
            <Link
              href="/"
              className="px-6 py-2.5 rounded-full text-sm transition-all border border-[#f0cd80]/30 text-[#d8c594] hover:border-[#f0cd80]/70 hover:bg-white/5"
              style={{ fontFamily: "var(--font-ui)", letterSpacing: "0.07em" }}
            >
              {t("about.cta.back")}
            </Link>
            <Link
              href="/chat"
              className="px-6 py-2.5 rounded-full text-sm font-semibold transition-all hover:shadow-[0_0_20px_rgba(232,182,63,0.4)]"
              style={{
                background: "linear-gradient(135deg, #e8b63f 0%, #b8893b 100%)",
                color: "#fff",
                fontFamily: "var(--font-ui)",
                letterSpacing: "0.07em",
              }}
            >
              {t("about.cta.start")}
            </Link>
          </div>
        </div>
      </section>

      {/* ─── Live comparison: PuranGPT vs a generic assistant ─── */}
      <LiveComparison />

      {/* ─── BG 16.23–16.24 — Scripture Block ─── */}
      <section className="py-20 px-4 md:px-16 max-w-3xl mx-auto">
        <div className="text-center mb-12">
          <span
            className="text-[10px] uppercase tracking-[0.25em] text-[#a38d7c]"
            style={{ fontFamily: "var(--font-ui)" }}
          >
            {t("about.scripture.eyebrow")}
          </span>
          <h2
            className="mt-2 text-2xl md:text-3xl text-[#f0cd80]"
            style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}
          >
            {t("about.scripture.title")}
          </h2>
        </div>

        <div className="flex flex-col gap-8">
          <VerseBlock
            number="16.23"
            devanagari="यः शास्त्रविधिमुत्सृज्य वर्तते कामकारतः । न स सिद्धिमवाप्नोति न सुखं न परां गतिम् ॥"
            transliteration="yaḥ śhāstra-vidhim utsṛjya vartate kāma-kārataḥ, na sa siddhim avāpnoti na sukhaṃ na parāṃ gatim"
            translation="One who abandons the guidance of scripture and acts purely on personal whim attains neither perfection, nor happiness, nor the highest goal."
            source="Bhagavad Gita 16.23"
          />
          <VerseBlock
            number="16.24"
            devanagari="तस्माच्छास्त्रं प्रमाणं ते कार्याकार्यव्यवस्थितौ । ज्ञात्वा शास्त्रविधानोक्तं कर्म कर्तुमिहार्हसि ॥"
            transliteration="tasmāch chhāstram pramāṇaṃ te kāryākārya-vyavasthitau, jñātvā śhāstra-vidhānoktaṃ karma kartum ihārhasi"
            translation="Therefore let scripture be your standard for telling right action from wrong; understand what it prescribes, and act accordingly."
            source="Bhagavad Gita 16.24"
          />
        </div>

        {/* Guruji's own translation of the same verses (Yogeshwari Gita) — the
            living-tradition reading PuranGPT is grounded in. */}
        <div className="mt-10 glass-panel rounded-2xl p-6 md:p-10 relative overflow-hidden">
          <div className="absolute top-0 left-0 w-1 h-full bg-[#f0cd80]/50" />
          <div className="relative z-10 flex items-center gap-4 mb-6">
            <div className="h-px flex-1 bg-gradient-to-r from-[#f0cd80]/30 to-transparent" />
            <span className="text-[10px] uppercase tracking-[0.2em] text-[#a38d7c]" style={{ fontFamily: "var(--font-ui)" }}>
              Guruji&rsquo;s translation
            </span>
            <div className="h-px flex-1 bg-gradient-to-l from-[#f0cd80]/30 to-transparent" />
          </div>
          <blockquote className="relative z-10">
            <p className="text-base md:text-lg text-[#e5e2e1] leading-relaxed mb-6 italic" style={{ fontFamily: "var(--font-display)" }}>
              &ldquo;Those great sages, who, by their establishment in the consciousness of the Void, had a direct experience of the brilliance of all brilliance, the Time — they, out of their compassion for the future progeny, preserved in the memory through the medium of words, that entire knowledge about how they perceived the Time by developing their consciousness; this was for the cause of all those who would be willing to understand these signals in the future.&rdquo;
            </p>
            <footer className="flex items-center space-x-4">
              <div className="w-12 h-px bg-[#d8c594]/40" />
              <cite className="text-[11px] text-[#d8c594] uppercase not-italic tracking-wider font-semibold" style={{ fontFamily: "var(--font-ui)" }}>
                Bhagavad Gita 16.23–16.24 — Guruji Sri Shailendra Sharma, Yogeshwari Gita, Chapter 16
              </cite>
            </footer>
          </blockquote>
        </div>
      </section>

      {/* ─── Corpus Bento Grid ─── */}
      <section className="py-24 px-4 md:px-16 max-w-[1200px] mx-auto relative">
        <div className="saffron-glow w-[600px] h-[600px] top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 opacity-20" />
        <div className="text-center mb-16 relative z-10">
          <h2
            className="text-3xl md:text-4xl text-[#e5e2e1] mb-4"
            style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}
          >
            {t("about.corpus.title")}
          </h2>
          <p className="text-base text-[#d8c594] tracking-wide" style={{ fontFamily: "var(--font-body)" }}>
            {t("about.corpus.subtitle")}
          </p>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4 relative z-10">
          {corpus.map(c => (
            <div
              key={c.label}
              className="group relative overflow-hidden glass-panel rounded-2xl p-6 flex flex-col items-center justify-center text-center min-h-[170px] transition-all duration-300 hover:-translate-y-1 hover:border-[#f0cd80]/30 hover:shadow-[0_22px_55px_rgba(232,182,63,0.1)]"
            >
              <div className="absolute -right-10 -top-10 h-28 w-28 rounded-full bg-[#f0cd80]/10 blur-2xl opacity-0 transition-opacity duration-500 group-hover:opacity-100" />
              <div className="relative mb-4 inline-flex p-3 rounded-2xl border border-[#f0cd80]/20 bg-[#f0cd80]/[0.06] text-[#f0cd80] transition-transform duration-300 group-hover:scale-110">
                {c.icon}
              </div>
              <span
                className="relative text-[10px] uppercase tracking-widest font-semibold text-[#a38d7c] mb-1"
                style={{ fontFamily: "var(--font-ui)" }}
              >
                {c.sub}
              </span>
              <span
                className="relative text-xl md:text-2xl text-[#f0cd80]"
                style={{ fontFamily: "var(--font-display)" }}
              >
                {c.label}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* ─── Locked Sources Preview ─── */}
      <section className="py-20 px-4 md:px-16 max-w-[1200px] mx-auto relative">
        <div className="text-center mb-12 relative z-10">
          <span
            className="text-[10px] uppercase tracking-[0.22em] text-[#a38d7c]"
            style={{ fontFamily: "var(--font-ui)" }}
          >
            {t("about.sources.eyebrow")}
          </span>
          <h2
            className="mt-2 text-3xl md:text-4xl text-[#e5e2e1]"
            style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}
          >
            {t("about.sources.title")}
          </h2>
          <p className="mt-3 text-sm text-[#dbc2b0]" style={{ fontFamily: "var(--font-body)" }}>
            {t("about.sources.subtitle")}
          </p>
        </div>

        <div className="relative">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {previewSources.map((s, i) => (
              <div
                key={i}
                className="group glass-panel rounded-2xl p-6 flex flex-col gap-3 transition-all duration-300 hover:-translate-y-1 hover:border-[#f0cd80]/25 hover:shadow-[0_22px_55px_rgba(232,182,63,0.08)]"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="flex items-center gap-2">
                    <span
                      className="flex h-5 min-w-[1.25rem] items-center justify-center rounded-full px-1.5 text-[10px] font-bold"
                      style={{ background: "rgba(232,182,63,0.14)", border: "1px solid rgba(232,182,63,0.3)", color: "#e8b63f", fontFamily: "var(--font-ui)" }}
                    >
                      {i + 1}
                    </span>
                    <span
                      className="text-[10px] uppercase tracking-widest text-[#f0cd80]"
                      style={{ fontFamily: "var(--font-ui)" }}
                    >
                      {s.tag}
                    </span>
                  </span>
                  <span
                    className="text-[10px] text-[#a38d7c] uppercase tracking-wider"
                    style={{ fontFamily: "var(--font-ui)" }}
                  >
                    {s.source}
                  </span>
                </div>
                <p
                  lang="sa"
                  className="text-base text-[var(--sanskrit-text)] leading-loose"
                  style={{ fontFamily: "var(--font-devanagari)", fontStyle: "normal" }}
                >
                  {s.text}
                </p>
                <p className="text-xs text-[#d8c594] italic leading-relaxed" style={{ fontFamily: "var(--font-display)" }}>
                  {s.transliteration}
                </p>
                <p className="text-sm text-[#a38d7c] leading-relaxed border-t border-white/5 pt-3" style={{ fontFamily: "var(--font-body)" }}>
                  &ldquo;{s.translation}&rdquo;
                </p>
              </div>
            ))}
          </div>

          <div className="mt-8 flex flex-col items-center justify-center gap-4 text-center">
            <BookOpen className="w-6 h-6 text-[#f0cd80]/70" />
            <p
              className="text-sm text-[#d8c594] max-w-md"
              style={{ fontFamily: "var(--font-body)" }}
            >
              {t("about.sources.note")}
            </p>
            <div className="flex flex-wrap items-center justify-center gap-3">
              <Link
                href="/library"
                className="px-6 py-2.5 rounded-full font-semibold text-sm transition-all hover:shadow-[0_0_20px_rgba(232,182,63,0.4)]"
                style={{
                  background: "linear-gradient(135deg, #e8b63f 0%, #b8893b 100%)",
                  color: "#fff",
                  fontFamily: "var(--font-ui)",
                  letterSpacing: "0.07em",
                }}
              >
                {t("about.sources.browse")}
              </Link>
              <Link
                href="/chat"
                className="px-6 py-2.5 rounded-full font-semibold text-sm transition-all border border-[#f0cd80]/40 text-[#d8c594] hover:border-[#f0cd80]/80 hover:bg-white/5"
                style={{ fontFamily: "var(--font-ui)", letterSpacing: "0.07em" }}
              >
                {t("about.sources.ask")}
              </Link>
            </div>
          </div>
        </div>
      </section>

      <Footer />
    </main>
  );
}
