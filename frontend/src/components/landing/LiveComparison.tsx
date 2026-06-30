"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, BookOpen, Check, Sparkles } from "lucide-react";

/**
 * A self-contained, looping "live" demo for the About page. It contrasts a
 * generic AI assistant (confident but unsourced) with PuranGPT, which streams
 * an answer grounded in exact verse citations — the cutting-edge difference
 * the brand leans on, shown rather than told. Pure client animation, no
 * backend: a single interval drives a deterministic timeline so it stays
 * smooth and never drifts.
 */

const QUERY = "What does the Bhagavad Gita teach about the soul?";

const GENERIC_ANSWER =
  "The Bhagavad Gita teaches that the soul is eternal and cannot be destroyed. Krishna tells Arjuna not to grieve, because the soul is beyond birth and death.";

// PuranGPT's streamed answer, split into segments so citation chips can appear
// inline the moment each phrase finishes typing.
const SEGMENTS: { text: string; cite: number | null }[] = [
  { text: "The soul (ātman) is eternal and indestructible", cite: 1 },
  { text: ". It is never born, nor does it ever die", cite: 2 },
  { text: " — weapons cannot pierce it, nor can fire burn it.", cite: null },
];

const SOURCES = [
  {
    n: 1,
    ref: "Bhagavad Gita 2.20",
    line: "na jāyate mriyate vā kadāchin…",
    gloss: "It is not born, nor does it die at any time.",
  },
  {
    n: 2,
    ref: "Bhagavad Gita 2.23",
    line: "nainaṃ chindanti śastrāṇi…",
    gloss: "Weapons cannot cut it, fire cannot burn it.",
  },
];

const TOTAL_CHARS = SEGMENTS.reduce((n, s) => n + s.text.length, 0);

// Timeline (in 40ms ticks)
const TICK_MS = 40;
const START_RIGHT = 8; // ~0.3s before PuranGPT starts streaming
const CHARS_PER_TICK = 2;
const TYPING_TICKS = Math.ceil(TOTAL_CHARS / CHARS_PER_TICK);
const HOLD_TICKS = 48; // ~1.9s to admire the finished state
const END_TICK = START_RIGHT + TYPING_TICKS + HOLD_TICKS;

function Cite({ n }: { n: number }) {
  return (
    <sup
      className="ml-0.5 inline-flex h-4 min-w-[1rem] items-center justify-center rounded-full px-1 text-[9px] font-bold align-super"
      style={{ background: "rgba(232,182,63,0.16)", border: "1px solid rgba(232,182,63,0.4)", color: "#e8b63f" }}
    >
      {n}
    </sup>
  );
}

export function LiveComparison() {
  const [tick, setTick] = useState(0);
  const reducedRef = useRef(false);

  useEffect(() => {
    reducedRef.current =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // Honour reduced-motion: show the finished state, skip the loop.
    if (reducedRef.current) {
      setTick(END_TICK - HOLD_TICKS);
      return;
    }

    const id = setInterval(() => {
      setTick((t) => (t >= END_TICK ? 0 : t + 1));
    }, TICK_MS);
    return () => clearInterval(id);
  }, []);

  const rightChars = Math.max(0, (tick - START_RIGHT) * CHARS_PER_TICK);
  const typingDone = rightChars >= TOTAL_CHARS;
  const leftVisible = tick > 4;
  const showSources = typingDone;

  // Build the streamed segments up to rightChars.
  let remaining = rightChars;
  const rendered = SEGMENTS.map((seg, i) => {
    const shown = Math.max(0, Math.min(remaining, seg.text.length));
    const full = shown >= seg.text.length;
    remaining -= seg.text.length;
    return (
      <span key={i}>
        {seg.text.slice(0, shown)}
        {full && seg.cite ? <Cite n={seg.cite} /> : null}
      </span>
    );
  });

  return (
    <section className="py-20 px-4 md:px-16 max-w-[1100px] mx-auto relative">
      <div className="saffron-glow w-[520px] h-[520px] top-0 left-1/2 -translate-x-1/2 opacity-[0.12] pointer-events-none" />

      <div className="text-center mb-12 relative z-10">
        <span
          className="text-[10px] uppercase tracking-[0.25em] text-[#a38d7c]"
          style={{ fontFamily: "var(--font-ui)" }}
        >
          See the difference
        </span>
        <h2
          className="mt-2 text-3xl md:text-4xl text-[#e5e2e1]"
          style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}
        >
          Answers you can trace to the source
        </h2>
        <p className="mt-3 text-sm md:text-base text-[#c7ae9a] max-w-xl mx-auto" style={{ fontFamily: "var(--font-body)" }}>
          Most assistants paraphrase from memory. PuranGPT retrieves the actual verses and
          cites them — every claim grounded in scripture you can open and read.
        </p>
      </div>

      {/* Shared query pill */}
      <div className="relative z-10 mb-6 flex justify-center">
        <div
          className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm"
          style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", color: "#e5e2e1", fontFamily: "var(--font-body)" }}
        >
          <Sparkles className="w-3.5 h-3.5 text-[#e8b63f]" />
          {QUERY}
        </div>
      </div>

      <div className="relative z-10 grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-5 items-stretch">
        {/* Generic assistant */}
        <div
          className="rounded-2xl p-5 flex flex-col"
          style={{ background: "rgba(20,18,15,0.6)", border: "1px solid rgba(255,255,255,0.07)" }}
        >
          <div className="flex items-center gap-2 mb-4">
            <span className="h-6 w-6 rounded-full flex items-center justify-center text-[11px]" style={{ background: "rgba(255,255,255,0.06)", color: "#9aa0a6" }}>
              AI
            </span>
            <span className="text-xs uppercase tracking-wider" style={{ color: "#9aa0a6", fontFamily: "var(--font-ui)" }}>
              A leading AI assistant
            </span>
          </div>

          <motion.p
            initial={false}
            animate={{ opacity: leftVisible ? 1 : 0.15 }}
            transition={{ duration: 0.5 }}
            className="text-sm leading-relaxed text-[#cdc6bd] flex-1"
            style={{ fontFamily: "var(--font-body)" }}
          >
            {leftVisible ? GENERIC_ANSWER : "Thinking…"}
          </motion.p>

          <div className="mt-4 flex items-center gap-2 rounded-lg px-3 py-2" style={{ background: "rgba(180,120,40,0.08)", border: "1px solid rgba(180,120,40,0.18)" }}>
            <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" style={{ color: "#c79a4a" }} />
            <span className="text-[11px]" style={{ color: "#bda483", fontFamily: "var(--font-ui)" }}>
              No sources — may paraphrase or misremember
            </span>
          </div>
        </div>

        {/* PuranGPT */}
        <div
          className="rounded-2xl p-5 flex flex-col relative overflow-hidden"
          style={{ background: "rgba(20,18,15,0.85)", border: "1px solid rgba(232,182,63,0.28)", boxShadow: "0 18px 50px rgba(232,182,63,0.06)" }}
        >
          <div className="absolute -right-12 -top-12 h-32 w-32 rounded-full bg-[#e8b63f]/10 blur-3xl pointer-events-none" />
          <div className="flex items-center gap-2 mb-4 relative">
            <span className="h-6 w-6 rounded-full flex items-center justify-center text-[11px]" style={{ background: "rgba(232,182,63,0.16)", border: "1px solid rgba(232,182,63,0.35)", color: "#e8b63f" }}>
              ॐ
            </span>
            <span className="text-xs uppercase tracking-wider" style={{ color: "#e2d4b2", fontFamily: "var(--font-ui)" }}>
              PuranGPT
            </span>
          </div>

          <p className="text-sm leading-relaxed text-[#e8e1d4] flex-1 relative" style={{ fontFamily: "var(--font-body)" }}>
            {rightChars === 0 ? (
              <span className="text-[#a38d7c]">Retrieving from 18 Mahapuranas &amp; the Gita…</span>
            ) : (
              <>
                {rendered}
                {!typingDone && (
                  <span className="inline-block w-[2px] h-4 ml-0.5 align-middle bg-[#e8b63f] animate-pulse" />
                )}
              </>
            )}
          </p>

          {/* Sources */}
          <motion.div
            initial={false}
            animate={{ opacity: showSources ? 1 : 0, height: showSources ? "auto" : 0 }}
            transition={{ duration: 0.4 }}
            className="mt-4 overflow-hidden"
          >
            <div className="flex items-center gap-1.5 mb-2">
              <BookOpen className="w-3.5 h-3.5 text-[#e8b63f]" />
              <span className="text-[10px] uppercase tracking-wider text-[#e8b63f]" style={{ fontFamily: "var(--font-ui)" }}>
                Sources
              </span>
            </div>
            <div className="space-y-2">
              {SOURCES.map((s) => (
                <div key={s.n} className="rounded-lg px-3 py-2" style={{ background: "rgba(232,182,63,0.05)", border: "1px solid rgba(232,182,63,0.16)" }}>
                  <div className="flex items-center gap-2">
                    <span className="flex h-4 min-w-[1rem] items-center justify-center rounded-full px-1 text-[9px] font-bold" style={{ background: "rgba(232,182,63,0.16)", border: "1px solid rgba(232,182,63,0.4)", color: "#e8b63f" }}>
                      {s.n}
                    </span>
                    <span className="text-[10px] uppercase tracking-wider text-[#e2d4b2]" style={{ fontFamily: "var(--font-ui)" }}>
                      {s.ref}
                    </span>
                  </div>
                  <p lang="sa" className="mt-1 text-xs text-[#ffe0b3]" style={{ fontFamily: "var(--font-display)" }}>
                    {s.line}
                  </p>
                  <p className="text-[11px] text-[#a38d7c] italic" style={{ fontFamily: "var(--font-body)" }}>
                    {s.gloss}
                  </p>
                </div>
              ))}
            </div>
            <div className="mt-3 flex items-center gap-2">
              <Check className="w-3.5 h-3.5 text-[#7bc47f]" />
              <span className="text-[11px]" style={{ color: "#9ec79e", fontFamily: "var(--font-ui)" }}>
                Every claim traceable to an exact verse
              </span>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
