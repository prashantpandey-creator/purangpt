"use client";

import { motion, AnimatePresence } from "framer-motion";
import { X, ArrowRight } from "lucide-react";
import type { GlossaryEntry } from "@/lib/sanskritGlossary";

// Localised "explore this term" follow-up query + button label. The backend
// answers in the user's language regardless, but the query the seeker sees
// should read in their tongue.
const ASK_TEMPLATE: Record<string, (e: GlossaryEntry) => string> = {
  en: (e) => `Explain ${e.term} (${e.translation}) in depth, with what the sacred texts teach about it.`,
  hi: (e) => `${e.term} (${e.translation}) को गहराई से समझाइए — शास्त्र इसके विषय में क्या कहते हैं?`,
  ru: (e) => `Подробно объясните ${e.term} (${e.translation}) — что говорят об этом священные тексты?`,
};
const ASK_LABEL: Record<string, string> = {
  en: "Explore in the sacred texts",
  hi: "शास्त्रों में खोजें",
  ru: "Исследовать в писаниях",
};
const DICTIONARY_LABEL: Record<string, string> = {
  en: "Sanskrit Dictionary",
  hi: "संस्कृत शब्दकोश",
  ru: "Санскритский словарь",
};

/**
 * A beautiful dictionary card for a single Sanskrit term: large Devanagari, the
 * IAST transliteration, a literal-translation chip, an evocative meaning, and a
 * follow-up button that launches a fresh query about the term.
 */
export function SanskritTermCard({
  entry,
  language = "en",
  onClose,
  onAsk,
}: {
  entry: GlossaryEntry | null;
  language?: string;
  onClose: () => void;
  onAsk: (query: string) => void;
}) {
  const lang = ["en", "hi", "ru"].includes(language) ? language : "en";

  return (
    <AnimatePresence>
      {entry && (
        <motion.div
          className="fixed inset-0 z-[120] flex items-end justify-center sm:items-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.22 }}
          onClick={onClose}
          aria-modal="true"
          role="dialog"
        >
          {/* Scrim */}
          <div
            className="absolute inset-0"
            style={{ background: "rgba(0,0,0,0.72)", backdropFilter: "blur(4px)" }}
          />

          <motion.div
            onClick={(e) => e.stopPropagation()}
            initial={{ opacity: 0, y: 40, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 24, scale: 0.98 }}
            transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
            className="relative z-10 w-full max-w-md overflow-hidden rounded-t-3xl sm:rounded-3xl"
            style={{
              background: "linear-gradient(180deg, #1a1510, #100d0a)",
              border: "1px solid rgba(232,182,63,0.28)",
              boxShadow: "0 -10px 60px rgba(0,0,0,0.6), 0 0 50px rgba(232,182,63,0.10)",
            }}
          >
            {/* Header band — eyebrow + close */}
            <div className="flex items-center justify-between px-5 pt-4">
              <span
                className="text-[10px] uppercase tracking-[0.28em]"
                style={{ fontFamily: "var(--font-ui)", color: "#9c8150" }}
              >
                {DICTIONARY_LABEL[lang]}
              </span>
              <button
                onClick={onClose}
                className="rounded-full p-1.5 transition-colors hover:bg-white/10"
                style={{ color: "#9c8150" }}
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Devanagari focal glyph */}
            <div className="relative flex flex-col items-center px-6 pb-2 pt-3 text-center">
              <span
                className="leading-none"
                style={{
                  fontFamily: "var(--font-display)",
                  fontSize: "clamp(3rem, 16vw, 4.25rem)",
                  background: "linear-gradient(180deg, #a5b4fc, #a78bfa)",
                  WebkitBackgroundClip: "text",
                  backgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  filter: "drop-shadow(0 0 22px rgba(232,182,63,0.30))",
                }}
                lang="sa"
              >
                {entry.devanagari}
              </span>

              <h2
                className="mt-2 text-2xl"
                style={{ fontFamily: "var(--font-display)", color: "#a5b4fc" }}
              >
                {entry.term}
              </h2>
              <span
                className="mt-0.5 text-sm italic"
                style={{ fontFamily: "var(--font-body)", color: "#9c8150" }}
              >
                {entry.iast}
              </span>

              {/* Translation chip */}
              <span
                className="mt-3 inline-block rounded-full px-3.5 py-1.5 text-[12.5px]"
                style={{
                  background: "rgba(232,182,63,0.10)",
                  border: "1px solid rgba(232,182,63,0.26)",
                  color: "#a5b4fc",
                  fontFamily: "var(--font-body)",
                }}
              >
                {entry.translation}
              </span>
            </div>

            {/* Danda divider */}
            <div className="my-3 flex items-center justify-center gap-3" aria-hidden>
              <span className="h-px w-12 bg-gradient-to-r from-transparent to-[#a78bfa]/40" />
              <span className="text-xs leading-none text-[#a78bfa]/70">॥</span>
              <span className="h-px w-12 bg-gradient-to-l from-transparent to-[#a78bfa]/40" />
            </div>

            {/* Meaning */}
            <p
              className="px-6 text-[14.5px] leading-relaxed"
              style={{ fontFamily: "var(--font-body)", color: "#e2e8f0" }}
            >
              {entry.meaning}
            </p>

            {/* Follow-up — starts a new query about the term */}
            <div className="px-5 pb-6 pt-5">
              <button
                onClick={() => onAsk(ASK_TEMPLATE[lang](entry))}
                className="group flex w-full items-center justify-between gap-2 rounded-2xl px-4 py-3 text-left text-sm font-medium transition-all duration-200 hover:-translate-y-0.5"
                style={{
                  background: "linear-gradient(135deg, rgba(231,205,132,0.16), rgba(232,182,63,0.10))",
                  border: "1px solid rgba(232,182,63,0.34)",
                  color: "#a5b4fc",
                  fontFamily: "var(--font-body)",
                }}
              >
                {ASK_LABEL[lang]}
                <ArrowRight className="h-4 w-4 flex-shrink-0 transition-transform duration-200 group-hover:translate-x-1" />
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
