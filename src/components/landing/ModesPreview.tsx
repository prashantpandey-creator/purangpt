"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { BookOpen, Sparkles } from "lucide-react";

/**
 * A faithful, *animated* replica of how PuranGPT actually answers in each of
 * its two modes. This is not a stock illustration — the bubbles, streaming,
 * citation badges, and source cards mirror the real chat UI (see
 * ChatInterface / SourcesPanel). The demo auto-plays the real flow: question →
 * thinking → streamed answer → citations → sources, then loops. It pauses when
 * scrolled out of view and respects prefers-reduced-motion.
 *
 * The example exchanges use real, verifiable Bhagavad Gita citations.
 */

type Token = { t: "text"; v: string } | { t: "cite"; n: number };

interface SourceItem {
  index: number;
  name: string;
  reference: string;
  excerpt: string;
}

// Module-level constants so their identity is stable across renders (the
// animation effect depends on them).
const words = (s: string): Token[] => s.split(" ").map((v) => ({ t: "text", v }));

const RESEARCH_TOKENS: Token[] = [
  ...words("Krishna tells Arjuna that one has a right to action alone, never to its fruits"),
  { t: "cite", n: 1 },
  ...words(
    "He counsels performing one’s duty established in yoga, abandoning attachment to success and failure — for such evenness of mind is itself called yoga"
  ),
  { t: "cite", n: 2 },
];

const RESEARCH_SOURCES: SourceItem[] = [
  {
    index: 1,
    name: "Bhagavad Gita",
    reference: "2.47",
    excerpt: "You have a right to perform your prescribed duty, but you are not entitled to the fruits of action.",
  },
  {
    index: 2,
    name: "Bhagavad Gita",
    reference: "2.48",
    excerpt: "Perform your duty established in yoga, abandoning attachment… evenness of mind is called yoga.",
  },
];

const GUIDE_TOKENS: Token[] = words(
  "That anxiety often comes from binding your peace to an outcome you can’t fully control. The Gita’s counsel here is gentle: give yourself wholly to the work in front of you, and loosen your grip on its fruits. Do the next right thing with care, and let the result unfold. The steadiness you’re really looking for isn’t a particular outcome — it’s an evenness of mind that no result can shake."
);

type Phase = "idle" | "question" | "thinking" | "streaming" | "sources" | "done";

function prefersReducedMotion() {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Drives the auto-playing, looping demo for one card. */
function useChatDemo(tokens: Token[], sources: SourceItem[], active: boolean) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [tokenCount, setTokenCount] = useState(0);
  const [sourceCount, setSourceCount] = useState(0);

  useEffect(() => {
    if (!active) return;

    // Reduced motion: skip straight to the finished state, no looping.
    if (prefersReducedMotion()) {
      setPhase("done");
      setTokenCount(tokens.length);
      setSourceCount(sources.length);
      return;
    }

    let cancelled = false;
    const timers: ReturnType<typeof setTimeout>[] = [];
    const wait = (ms: number) =>
      new Promise<void>((resolve) => {
        timers.push(setTimeout(resolve, ms));
      });

    async function run() {
      while (!cancelled) {
        setPhase("question");
        setTokenCount(0);
        setSourceCount(0);
        await wait(750);
        if (cancelled) return;

        setPhase("thinking");
        await wait(1100);
        if (cancelled) return;

        setPhase("streaming");
        for (let i = 1; i <= tokens.length; i++) {
          if (cancelled) return;
          setTokenCount(i);
          await wait(tokens[i - 1].t === "cite" ? 280 : 52);
        }

        if (sources.length > 0) {
          setPhase("sources");
          for (let i = 1; i <= sources.length; i++) {
            if (cancelled) return;
            setSourceCount(i);
            await wait(480);
          }
        }

        setPhase("done");
        await wait(3400);
      }
    }

    run();
    return () => {
      cancelled = true;
      timers.forEach(clearTimeout);
    };
  }, [active, tokens, sources]);

  return { phase, tokenCount, sourceCount };
}

function OmAvatar() {
  return (
    <div
      className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-2xl text-sm"
      style={{ background: "rgba(13,13,13,0.82)", border: "1px solid rgba(139,92,246,0.3)", color: "#a78bfa" }}
    >
      ॐ
    </div>
  );
}

function UserBubble({ children, show }: { children: React.ReactNode; show: boolean }) {
  return (
    <motion.div
      className="flex justify-end"
      initial={{ opacity: 0, y: 8 }}
      animate={show ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
    >
      <div
        className="max-w-[88%] rounded-[1.4rem] rounded-tr-md px-4 py-2.5 text-sm"
        style={{
          border: "1px solid rgba(139,92,246,0.28)",
          background: "linear-gradient(135deg, rgba(139,92,246,0.14), rgba(139,92,246,0.07))",
          color: "#efe0be",
          fontFamily: "var(--font-body)",
          lineHeight: 1.6,
        }}
      >
        {children}
      </div>
    </motion.div>
  );
}

function Cite({ n }: { n: number }) {
  return (
    <motion.span
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ type: "spring", stiffness: 520, damping: 22 }}
      className="mx-0.5 inline-flex h-[1.15rem] min-w-[1.15rem] items-center justify-center rounded-full border px-1 align-super text-[10px] font-bold"
      style={{ background: "rgba(139,92,246,0.2)", color: "#a78bfa", borderColor: "rgba(139,92,246,0.3)" }}
    >
      {n}
    </motion.span>
  );
}

function ThinkingDots() {
  return (
    <div className="flex items-center gap-1.5 py-1">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="h-1.5 w-1.5 rounded-full"
          style={{ background: "#a78bfa" }}
          animate={{ opacity: [0.25, 1, 0.25], y: [0, -2, 0] }}
          transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.18, ease: "easeInOut" }}
        />
      ))}
    </div>
  );
}

function SourceCard({ source }: { source: SourceItem }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="rounded-2xl border border-l-2 border-white/5 p-3"
      style={{ background: "#141121", borderLeftColor: "#554336" }}
    >
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-2">
          <span
            className="flex h-[1.1rem] min-w-[1.1rem] items-center justify-center rounded-full border px-1 text-[10px] font-bold"
            style={{ background: "rgba(139,92,246,0.16)", color: "#a78bfa", borderColor: "rgba(139,92,246,0.35)" }}
          >
            {source.index}
          </span>
          <span className="truncate text-[10px] uppercase tracking-wider text-[#a78bfa]" style={{ fontFamily: "var(--font-ui)" }}>
            {source.name}
          </span>
        </span>
        <span className="flex-shrink-0 text-[10px] text-[#a38d7c]" style={{ fontFamily: "var(--font-ui)" }}>
          {source.reference}
        </span>
      </div>
      <p className="text-[12px] leading-relaxed text-[#dbc2b0]" style={{ fontFamily: "var(--font-body)" }}>
        {source.excerpt}
      </p>
    </motion.div>
  );
}

function ChatFrame({
  accent,
  icon,
  badge,
  children,
}: {
  accent: string;
  icon: React.ReactNode;
  badge: string;
  children: React.ReactNode;
}) {
  return (
    <div className="overflow-hidden rounded-2xl border border-white/10 bg-[#0b0a09] shadow-[0_24px_80px_rgba(0,0,0,0.45)]">
      <div className="flex items-center gap-2 border-b border-white/5 px-4 py-2.5" style={{ background: "#000" }}>
        <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
        <span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
        <span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
        <span
          className="ml-3 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[10px] uppercase tracking-[0.18em]"
          style={{ borderColor: `${accent}55`, color: accent, fontFamily: "var(--font-ui)" }}
        >
          {icon}
          {badge}
        </span>
      </div>
      <div className="space-y-4 p-4 sm:p-5">{children}</div>
    </div>
  );
}

function StreamedAnswer({
  accent,
  tokens,
  visible,
  streaming,
}: {
  accent: string;
  tokens: Token[];
  visible: number;
  streaming: boolean;
}) {
  return (
    <span>
      {tokens.slice(0, visible).map((tk, i) =>
        tk.t === "cite" ? (
          <Cite key={i} n={tk.n} />
        ) : (
          <span key={i}>{tk.v} </span>
        )
      )}
      {streaming && (
        <span
          className="ml-0.5 inline-block h-[1em] w-[2px] translate-y-[2px] animate-pulse"
          style={{ background: accent }}
          aria-hidden="true"
        />
      )}
    </span>
  );
}

function ModePreviewCard({
  active,
  accent,
  badge,
  badgeIcon,
  headerIcon,
  title,
  description,
  question,
  tokens,
  sources,
}: {
  active: boolean;
  accent: string;
  badge: string;
  badgeIcon: React.ReactNode;
  headerIcon: React.ReactNode;
  title: string;
  description: string;
  question: string;
  tokens: Token[];
  sources: SourceItem[];
}) {
  const { phase, tokenCount, sourceCount } = useChatDemo(tokens, sources, active);
  const showAnswer = phase === "streaming" || phase === "sources" || phase === "done";

  return (
    <div>
      <div className="mb-3 flex items-start gap-3">
        <div className="inline-flex rounded-xl border p-2" style={{ borderColor: `${accent}33`, background: `${accent}0d`, color: accent }}>
          {headerIcon}
        </div>
        <div>
          <h3 className="text-lg text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)", fontWeight: 500 }}>
            {title}
          </h3>
          <p className="text-xs text-[#a38d7c]" style={{ fontFamily: "var(--font-body)" }}>
            {description}
          </p>
        </div>
      </div>

      <ChatFrame accent={accent} badge={badge} icon={badgeIcon}>
        <UserBubble show={phase !== "idle"}>{question}</UserBubble>

        {(phase === "thinking" || showAnswer) && (
          <div className="flex gap-3">
            <OmAvatar />
            <div
              className="max-w-[92%] rounded-[1.4rem] rounded-tl-md px-4 py-3 text-sm"
              style={{
                background: "rgba(13,13,13,0.74)",
                border: "1px solid rgba(255,255,255,0.08)",
                borderLeft: `2px solid ${accent}`,
                color: "#e2d4b2",
                fontFamily: "var(--font-body)",
                lineHeight: 1.7,
              }}
            >
              {phase === "thinking" ? (
                <ThinkingDots />
              ) : (
                <>
                  <StreamedAnswer accent={accent} tokens={tokens} visible={tokenCount} streaming={phase === "streaming"} />
                  {sources.length > 0 && sourceCount > 0 && (
                    <div className="mt-3 space-y-2">
                      {sources.slice(0, sourceCount).map((s) => (
                        <SourceCard key={s.index} source={s} />
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        )}
      </ChatFrame>
    </div>
  );
}

export function ModesPreview() {
  const sectionRef = useRef<HTMLElement>(null);
  const [active, setActive] = useState(false);

  // Only animate while the section is on screen — saves CPU and feels like the
  // demo "comes alive" as you scroll to it.
  useEffect(() => {
    const el = sectionRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => setActive(entry.isIntersecting),
      { threshold: 0.25 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <section ref={sectionRef} className="relative py-20 px-4 md:px-16 max-w-[1200px] mx-auto">
      <div className="mb-12 text-center">
        <span className="text-[10px] uppercase tracking-[0.22em] text-[#a38d7c]" style={{ fontFamily: "var(--font-ui)" }}>
          Two ways to ask
        </span>
        <h2 className="mt-2 text-3xl md:text-4xl text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}>
          See how each mode answers
        </h2>
        <p className="mx-auto mt-3 max-w-2xl text-sm text-[#dbc2b0]" style={{ fontFamily: "var(--font-body)" }}>
          The same scripture, two voices. These play out live — exactly how answers stream inside the app.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ModePreviewCard
          active={active}
          accent="#a78bfa"
          badge="Citations"
          badgeIcon={<BookOpen className="h-3 w-3" />}
          headerIcon={<BookOpen className="h-5 w-5" />}
          title="Scholar Mode"
          description="Every claim carries an exact verse citation you can open and read."
          question="What does the Bhagavad Gita say about acting without attachment to results?"
          tokens={RESEARCH_TOKENS}
          sources={RESEARCH_SOURCES}
        />
        <ModePreviewCard
          active={active}
          accent="#a78bfa"
          badge="Guruji first"
          badgeIcon={<Sparkles className="h-3 w-3" />}
          headerIcon={<Sparkles className="h-5 w-5" />}
          title="Guru Mode"
          description="Warm, personal guidance grounded in the same teachings — no citation clutter."
          question="I keep feeling anxious about whether my work will succeed. How do I cope?"
          tokens={GUIDE_TOKENS}
          sources={[]}
        />
      </div>
    </section>
  );
}
