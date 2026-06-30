"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, X } from "lucide-react";

/**
 * A gentle, *non-intrusive* nudge above the chat composer for logged-out users.
 *
 * Behaviour:
 *  - Appears after the user has had `threshold` assistant replies (default 3).
 *    At that point they're engaged enough that an invite is welcome, not jarring.
 *  - Manual dismissal is remembered for the browser session so it never re-nags.
 *  - `messageCount` is the number of completed assistant messages in the thread.
 */
export function SignupNudge({
  messageCount,
  threshold = 3,
  onSignIn,
}: {
  messageCount: number;
  threshold?: number;
  onSignIn: () => void;
}) {
  const [dismissed, setDismissed] = useState(true); // start hidden → no SSR flash

  useEffect(() => {
    try {
      setDismissed(sessionStorage.getItem("purangpt:nudge-dismissed") === "1");
    } catch {
      setDismissed(false);
    }
  }, []);

  const close = () => {
    setDismissed(true);
    try {
      sessionStorage.setItem("purangpt:nudge-dismissed", "1");
    } catch {
      /* ignore */
    }
  };

  const show = messageCount >= threshold && !dismissed;

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 8 }}
          transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
          className="mx-auto mb-2 flex w-full max-w-2xl items-center gap-2.5 rounded-xl px-3 py-2"
          style={{
            background: "rgba(232,182,63,0.06)",
            border: "1px solid rgba(232,182,63,0.22)",
            backdropFilter: "blur(8px)",
          }}
        >
          <Sparkles className="w-3.5 h-3.5 flex-shrink-0 text-[#e8b63f]" />
          <span
            className="flex-1 text-xs leading-snug text-[#d8c594]"
            style={{ fontFamily: "var(--font-ui)" }}
          >
            Create a free account to save your conversations.
          </span>
          <button
            onClick={onSignIn}
            className="flex-shrink-0 rounded-lg px-3 py-1 text-xs font-semibold transition-colors"
            style={{ background: "rgba(232,182,63,0.15)", border: "1px solid rgba(232,182,63,0.35)", color: "#e8b63f", fontFamily: "var(--font-ui)" }}
          >
            Get started
          </button>
          <button
            onClick={close}
            aria-label="Dismiss"
            className="flex-shrink-0 p-1 rounded-md text-[#94a3b8] transition-colors hover:bg-white/5 hover:text-[#e5e2e1]"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
