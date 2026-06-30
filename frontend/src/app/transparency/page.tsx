import Link from "next/link";
import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";
import { CitationComparison } from "@/components/landing/CitationComparison";
import {
  BookOpen,
  Database,
  Layers,
  Search,
  Quote,
  ShieldCheck,
  HeartHandshake,
  Cpu,
  ScrollText,
  ArrowRight,
} from "lucide-react";

export const metadata = {
  title: "Insight · How PuranGPT works",
  description:
    "A plain-spoken look at the corpus, the retrieval pipeline, and the work behind every cited answer in PuranGPT.",
};

const stats = [
  { value: "208,000+", label: "indexed verses", icon: <ScrollText className="h-5 w-5" /> },
  { value: "18", label: "Mahāpurāṇas", icon: <BookOpen className="h-5 w-5" /> },
  { value: "108", label: "Upaniṣads", icon: <Layers className="h-5 w-5" /> },
  { value: "384-dim", label: "verse embeddings", icon: <Cpu className="h-5 w-5" /> },
  { value: "$0", label: "to read — free & open", icon: <HeartHandshake className="h-5 w-5" /> },
  { value: "2 modes", label: "Scholar & Guru", icon: <Quote className="h-5 w-5" /> },
];

const pipeline = [
  {
    icon: <BookOpen className="h-5 w-5" />,
    title: "Curate the source",
    body: "We start from the original texts — Puranas, the epics, Upanishads, and yogic darshanas — and tag each with its tradition and edition so you always know what you're reading.",
  },
  {
    icon: <Layers className="h-5 w-5" />,
    title: "Split into passages",
    body: "Each text is broken into verse-level passages so a citation can point you to the exact line, not a vague chapter.",
  },
  {
    icon: <Cpu className="h-5 w-5" />,
    title: "Embed it locally",
    body: "Every passage is turned into a 384-dimension vector with an on-our-own-hardware model (all-MiniLM-L6-v2). Running embeddings ourselves keeps reading free and removes any per-query cost to you.",
  },
  {
    icon: <Search className="h-5 w-5" />,
    title: "Retrieve before answering",
    body: "When you ask something, we search those vectors (pgvector) for the passages that truly match — so the answer is built from real verses, not memory.",
  },
  {
    icon: <Quote className="h-5 w-5" />,
    title: "Answer with citations",
    body: "The model writes its reply grounded in the retrieved passages and attaches each one as a citation you can tap open and read in full.",
  },
];

export default function TransparencyPage() {
  return (
    <>
      <Navbar />
      <main className="min-h-screen bg-[#000] text-[#e5e2e1] overflow-x-hidden">
        {/* Hero */}
        <section className="relative px-4 md:px-16 pt-32 pb-16 text-center overflow-hidden">
          <div className="absolute left-1/2 top-10 h-72 w-72 -translate-x-1/2 rounded-full bg-[#e8b63f]/10 blur-[120px] pointer-events-none" />
          <div className="relative mx-auto max-w-3xl">
            <span className="text-[10px] uppercase tracking-[0.25em] text-[#a38d7c]" style={{ fontFamily: "var(--font-ui)" }}>
              Insight
            </span>
            <h1
              className="mt-3 text-4xl md:text-5xl text-transparent bg-clip-text bg-gradient-to-b from-[#ffd080] via-[#f0cd80] to-[#e8b63f]"
              style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}
            >
              How PuranGPT works — and the work behind it
            </h1>
            <p className="mx-auto mt-5 max-w-2xl text-base md:text-lg leading-8 text-[#d8c594]" style={{ fontFamily: "var(--font-body)" }}>
              You're trusting us with sacred texts, so you deserve to see under the hood. Here is — in plain words —
              what we've gathered, how an answer is actually built, and what we're still honest about. No mystique,
              just the work.
            </p>
          </div>
        </section>

        {/* By the numbers */}
        <section className="px-4 md:px-16 py-12 max-w-[1100px] mx-auto">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
            {stats.map((s) => (
              <div
                key={s.label}
                className="rounded-2xl border border-white/8 p-5 text-center"
                style={{ background: "rgba(13,13,13,0.6)" }}
              >
                <div className="mx-auto mb-3 inline-flex rounded-xl border border-[#e8b63f]/20 bg-[#e8b63f]/5 p-2.5 text-[#e8b63f]">
                  {s.icon}
                </div>
                <div className="text-2xl md:text-3xl text-[#f0cd80]" style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}>
                  {s.value}
                </div>
                <div className="mt-1 text-xs uppercase tracking-wider text-[#a38d7c]" style={{ fontFamily: "var(--font-ui)" }}>
                  {s.label}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* The pipeline */}
        <section className="px-4 md:px-16 py-16 max-w-3xl mx-auto">
          <div className="mb-10 text-center">
            <h2 className="text-2xl md:text-3xl text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}>
              How every answer is grounded
            </h2>
            <p className="mt-3 text-sm text-[#dbc2b0]" style={{ fontFamily: "var(--font-body)" }}>
              Five steps stand between your question and the reply you read.
            </p>
          </div>

          <div className="relative space-y-4">
            {pipeline.map((step, i) => (
              <div
                key={step.title}
                className="relative flex gap-4 rounded-2xl border border-white/8 p-5"
                style={{ background: "rgba(13,13,13,0.6)" }}
              >
                <div className="flex flex-col items-center">
                  <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl border border-[#e8b63f]/25 bg-[#e8b63f]/10 text-[#e8b63f]">
                    {step.icon}
                  </div>
                  {i < pipeline.length - 1 && <div className="mt-2 w-px flex-1 bg-gradient-to-b from-[#e8b63f]/30 to-transparent" />}
                </div>
                <div className="pb-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-bold text-[#6f5a34]" style={{ fontFamily: "var(--font-ui)" }}>
                      0{i + 1}
                    </span>
                    <h3 className="text-base text-[#e2d4b2]" style={{ fontFamily: "var(--font-display)", fontWeight: 500 }}>
                      {step.title}
                    </h3>
                  </div>
                  <p className="mt-1.5 text-sm leading-relaxed text-[#c7ae9a]" style={{ fontFamily: "var(--font-body)" }}>
                    {step.body}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Cited, not paraphrased — the comparison (moved here from the home page) */}
        <CitationComparison />

        {/* Why we cite */}
        <section className="px-4 md:px-16 py-12 max-w-3xl mx-auto">
          <div className="rounded-2xl border border-[#e8b63f]/20 p-8 md:p-10" style={{ background: "rgba(13,13,13,0.65)" }}>
            <ShieldCheck className="h-7 w-7 text-[#e8b63f]" />
            <h2 className="mt-4 text-2xl text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}>
              Why we cite — every time
            </h2>
            <p className="mt-3 text-sm md:text-base leading-7 text-[#d8c594]" style={{ fontFamily: "var(--font-body)" }}>
              These texts have been carried faithfully for millennia. The least we can do is point back to them
              precisely. A citation you can open is a promise: don't take our word for it — read the verse yourself.
              That's the difference between an answer you have to trust blindly and one you can verify in seconds.
            </p>
          </div>
        </section>

        {/* What we're honest about */}
        <section className="px-4 md:px-16 py-12 max-w-3xl mx-auto">
          <div className="mb-6 text-center">
            <h2 className="text-2xl md:text-3xl text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}>
              What we're honest about
            </h2>
          </div>
          <div className="space-y-3">
            {[
              {
                t: "Translations are interpretations",
                b: "Where we show a rendering in English, it is one scholar's reading. We always link the source so you can weigh it for yourself.",
              },
              {
                t: "The library keeps growing",
                b: "Indexing is ongoing. Some texts are richer than others today, and we're steadily adding and deepening coverage.",
              },
              {
                t: "AI can still get things wrong",
                b: "Grounding sharply reduces invented citations, but no model is perfect. The open source link is there precisely so you can check.",
              },
            ].map((item) => (
              <div key={item.t} className="rounded-2xl border border-white/8 p-5" style={{ background: "rgba(20,20,20,0.5)" }}>
                <h3 className="text-sm font-semibold text-[#e2d4b2]" style={{ fontFamily: "var(--font-display)" }}>
                  {item.t}
                </h3>
                <p className="mt-1.5 text-sm leading-relaxed text-[#c7ae9a]" style={{ fontFamily: "var(--font-body)" }}>
                  {item.b}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* CTA */}
        <section className="px-4 md:px-16 py-20 text-center">
          <div className="mx-auto max-w-2xl">
            <h2 className="text-3xl md:text-4xl text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}>
              See it for yourself
            </h2>
            <p className="mt-4 text-sm text-[#d8c594]" style={{ fontFamily: "var(--font-body)" }}>
              Every verse is free and open to read. No account needed.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <Link href="/library" className="btn-primary inline-flex items-center gap-2 rounded-full px-7 py-3 text-sm font-semibold">
                Browse the library
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link href="/chat" className="btn-secondary inline-flex items-center gap-2 rounded-full px-7 py-3 text-sm font-semibold">
                Ask the texts
              </Link>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
