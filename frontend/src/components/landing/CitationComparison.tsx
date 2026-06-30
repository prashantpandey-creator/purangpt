import { Check, X, Minus, ShieldCheck, AlertTriangle } from "lucide-react";

/**
 * An honest, brand-neutral comparison of how PuranGPT cites scripture versus a
 * typical general-purpose AI assistant. We deliberately do NOT name or quote
 * specific competitors — instead we contrast the structural difference: a
 * retrieval-grounded system that returns exact, openable verse citations vs a
 * general chatbot that answers from training memory and tends to paraphrase
 * without a verifiable source. Language is hedged ("typically", "often") so the
 * claims stay fair and defensible.
 */

const QUESTION = "What does the Bhagavad Gita say about acting without attachment to results?";

interface Row {
  label: string;
  puran: "yes";
  general: "no" | "partial";
  generalNote: string;
}

const ROWS: Row[] = [
  {
    label: "Exact chapter.verse references",
    puran: "yes",
    general: "no",
    generalNote: "usually paraphrased",
  },
  {
    label: "Tap to open the original verse",
    puran: "yes",
    general: "no",
    generalNote: "no source attached",
  },
  {
    label: "Answers grounded in indexed source texts",
    puran: "yes",
    general: "no",
    generalNote: "training memory only",
  },
  {
    label: "Resistant to invented citations",
    puran: "yes",
    general: "partial",
    generalNote: "can hallucinate refs",
  },
  {
    label: "Cross-scripture synthesis with sources",
    puran: "yes",
    general: "partial",
    generalNote: "limited / unsourced",
  },
];

function Verdict({ kind }: { kind: "yes" | "no" | "partial" }) {
  if (kind === "yes")
    return (
      <span className="inline-flex h-6 w-6 items-center justify-center rounded-full" style={{ background: "rgba(232,182,63,0.15)", color: "#e8b63f" }}>
        <Check className="h-3.5 w-3.5" />
      </span>
    );
  if (kind === "partial")
    return (
      <span className="inline-flex h-6 w-6 items-center justify-center rounded-full" style={{ background: "rgba(255,255,255,0.05)", color: "#a38d7c" }}>
        <Minus className="h-3.5 w-3.5" />
      </span>
    );
  return (
    <span className="inline-flex h-6 w-6 items-center justify-center rounded-full" style={{ background: "rgba(255,255,255,0.04)", color: "#7c6f63" }}>
      <X className="h-3.5 w-3.5" />
    </span>
  );
}

export function CitationComparison() {
  return (
    <section className="relative py-20 px-4 md:px-16 max-w-[1200px] mx-auto">
      <div className="mb-12 text-center">
        <span className="text-[10px] uppercase tracking-[0.22em] text-[#a38d7c]" style={{ fontFamily: "var(--font-ui)" }}>
          Why grounding matters
        </span>
        <h2 className="mt-2 text-3xl md:text-4xl text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}>
          Cited, not paraphrased
        </h2>
        <p className="mx-auto mt-3 max-w-2xl text-sm text-[#dbc2b0]" style={{ fontFamily: "var(--font-body)" }}>
          General-purpose assistants answer scripture from training memory, so they tend to paraphrase and rarely
          point to an exact, openable verse. PuranGPT retrieves the source first, then answers.
        </p>
      </div>

      {/* Shared question */}
      <div className="mx-auto mb-6 max-w-2xl">
        <div className="flex justify-center">
          <div
            className="rounded-[1.4rem] rounded-tr-md px-4 py-2.5 text-center text-sm"
            style={{
              border: "1px solid rgba(232,182,63,0.28)",
              background: "linear-gradient(135deg, rgba(232,182,63,0.14), rgba(232,182,63,0.07))",
              color: "#efe0be",
              fontFamily: "var(--font-body)",
              lineHeight: 1.6,
            }}
          >
            {QUESTION}
          </div>
        </div>
        <p className="mt-2 text-center text-[10px] uppercase tracking-[0.2em] text-[#554336]" style={{ fontFamily: "var(--font-ui)" }}>
          Same question · two systems
        </p>
      </div>

      {/* Two answers */}
      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        {/* PuranGPT */}
        <div
          className="relative overflow-hidden rounded-2xl border p-5"
          style={{ borderColor: "rgba(232,182,63,0.35)", background: "rgba(13,13,13,0.74)", boxShadow: "0 0 40px rgba(232,182,63,0.08)" }}
        >
          <div className="absolute -right-16 -top-16 h-40 w-40 rounded-full bg-[#e8b63f]/10 blur-3xl" />
          <div className="relative">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-sm font-semibold text-[#e2d4b2]" style={{ fontFamily: "var(--font-display)" }}>
                PuranGPT
              </span>
              <span
                className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[10px] uppercase tracking-[0.16em]"
                style={{ borderColor: "rgba(232,182,63,0.4)", color: "#e8b63f", fontFamily: "var(--font-ui)" }}
              >
                <ShieldCheck className="h-3 w-3" />
                Cited &amp; grounded
              </span>
            </div>

            <p className="text-sm leading-7 text-[#e2d4b2]" style={{ fontFamily: "var(--font-body)" }}>
              Krishna tells Arjuna that one has a right to action alone, never to its fruits
              <Cite n={1} /> and counsels performing one&apos;s duty established in yoga, abandoning attachment to
              outcomes<Cite n={2} />
            </p>

            <div className="mt-4 space-y-2">
              <SourceLine name="Bhagavad Gita" reference="2.47" excerpt="You have a right to your duty, but never to the fruits of action." />
              <SourceLine name="Bhagavad Gita" reference="2.48" excerpt="Established in yoga, perform your duty… evenness of mind is called yoga." />
            </div>
          </div>
        </div>

        {/* Typical general-purpose AI */}
        <div className="relative overflow-hidden rounded-2xl border border-white/8 p-5" style={{ background: "rgba(20,20,20,0.6)" }}>
          <div className="relative">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-sm font-semibold text-[#cfcabf]" style={{ fontFamily: "var(--font-display)" }}>
                Typical general-purpose AI
              </span>
              <span
                className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[10px] uppercase tracking-[0.16em]"
                style={{ borderColor: "rgba(255,255,255,0.12)", color: "#9a8e80", fontFamily: "var(--font-ui)" }}
              >
                <AlertTriangle className="h-3 w-3" />
                Paraphrased
              </span>
            </div>

            <p className="text-sm leading-7 text-[#b8b2a8]" style={{ fontFamily: "var(--font-body)" }}>
              The Bhagavad Gita teaches that you should focus on your actions and not be attached to the results —
              often summarized as &ldquo;do your duty without expecting rewards.&rdquo;
            </p>

            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-2.5 py-1 text-[11px] text-[#8a7f72]" style={{ fontFamily: "var(--font-ui)" }}>
                <X className="h-3 w-3" /> No exact verse
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-2.5 py-1 text-[11px] text-[#8a7f72]" style={{ fontFamily: "var(--font-ui)" }}>
                <X className="h-3 w-3" /> Source not linked
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-2.5 py-1 text-[11px] text-[#8a7f72]" style={{ fontFamily: "var(--font-ui)" }}>
                <AlertTriangle className="h-3 w-3" /> Citation unverified
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Capability checklist */}
      <div className="mx-auto mt-12 max-w-3xl overflow-hidden rounded-2xl border border-white/8" style={{ background: "rgba(13,13,13,0.6)" }}>
        <div className="grid grid-cols-[1fr_auto_auto] items-center gap-x-4 border-b border-white/8 px-5 py-3 text-[10px] uppercase tracking-[0.16em] text-[#a38d7c]" style={{ fontFamily: "var(--font-ui)" }}>
          <span>Capability</span>
          <span className="w-24 text-center text-[#e8b63f]">PuranGPT</span>
          <span className="w-28 text-center">General AI</span>
        </div>
        {ROWS.map((row, i) => (
          <div
            key={row.label}
            className="grid grid-cols-[1fr_auto_auto] items-center gap-x-4 px-5 py-3.5"
            style={{ borderTop: i === 0 ? "none" : "1px solid rgba(255,255,255,0.05)" }}
          >
            <span className="text-sm text-[#dbc2b0]" style={{ fontFamily: "var(--font-body)" }}>
              {row.label}
            </span>
            <span className="flex w-24 justify-center">
              <Verdict kind={row.puran} />
            </span>
            <span className="flex w-28 flex-col items-center gap-1">
              <Verdict kind={row.general} />
              <span className="text-[9px] text-[#6f6458]" style={{ fontFamily: "var(--font-ui)" }}>
                {row.generalNote}
              </span>
            </span>
          </div>
        ))}
      </div>

      <p className="mx-auto mt-12 max-w-2xl text-center text-[11px] leading-relaxed text-[#554336]" style={{ fontFamily: "var(--font-body)" }}>
        Comparison reflects how general-purpose assistants typically handle niche scriptural sources without
        retrieval grounding. Individual results vary by model and prompt.
      </p>
    </section>
  );
}

/** Inline gold citation badge — matches the real chat. */
function Cite({ n }: { n: number }) {
  return (
    <span
      className="mx-0.5 inline-flex h-[1.15rem] min-w-[1.15rem] items-center justify-center rounded-full border px-1 align-super text-[10px] font-bold"
      style={{ background: "rgba(232,182,63,0.2)", color: "#e8b63f", borderColor: "rgba(232,182,63,0.3)" }}
    >
      {n}
    </span>
  );
}

function SourceLine({ name, reference, excerpt }: { name: string; reference: string; excerpt: string }) {
  return (
    <div className="rounded-xl border border-l-2 border-white/5 p-2.5" style={{ background: "#141121", borderLeftColor: "#554336" }}>
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="truncate text-[10px] uppercase tracking-wider text-[#e8b63f]" style={{ fontFamily: "var(--font-ui)" }}>
          {name}
        </span>
        <span className="flex-shrink-0 text-[10px] text-[#a38d7c]" style={{ fontFamily: "var(--font-ui)" }}>
          {reference}
        </span>
      </div>
      <p className="text-[12px] leading-relaxed text-[#dbc2b0]" style={{ fontFamily: "var(--font-body)" }}>
        {excerpt}
      </p>
    </div>
  );
}
