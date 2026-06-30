"use client";

import Link from "next/link";
import { ConcentricBindu } from "./ConcentricBindu";

interface LogoProps {
  /** Pixel size (width = height). Default 44. */
  size?: number;
  /** Wrap in a Link to home. Default true. */
  href?: string | null;
  /** Strength of the saffron glow: 'sm' | 'md' | 'lg'. Default 'md'. */
  glow?: "sm" | "md" | "lg";
  /** Extra classes on the outermost wrapper. */
  className?: string;
  /** Accessible label. */
  label?: string;
  priority?: boolean;
  /** Kept for API compatibility — the mark always lives on its own now. */
  spinning?: boolean;
  /** True while AI is generating — the cell churns harder + the field pulses. */
  isThinking?: boolean;
}

const GLOW = {
  sm: "drop-shadow-[0_0_8px_rgba(139,92,246,0.26)] hover:drop-shadow-[0_0_13px_rgba(139,92,246,0.4)]",
  md: "drop-shadow-[0_0_14px_rgba(139,92,246,0.34)] hover:drop-shadow-[0_0_20px_rgba(139,92,246,0.5)]",
  lg: "drop-shadow-[0_0_26px_rgba(139,92,246,0.42)] hover:drop-shadow-[0_0_38px_rgba(139,92,246,0.58)]",
} as const;

/**
 * The single, global PuranGPT logo — the Concentric Bindu: a living
 * gravitational mandala-eye. Clickable (links home by default), sized via
 * `size`, with the project's signature candlelit-gold aura.
 *
 * `isThinking`/`spinning` make the central cell churn harder while AI generates.
 */
export function Logo({
  size = 44,
  href = "/",
  glow = "md",
  className = "",
  label = "PuranGPT home",
  spinning = false,
  isThinking = false,
}: LogoProps) {
  const inner = (
    <span
      className={`inline-block transition-all duration-300 ${GLOW[glow]} ${className}`}
      style={{ width: size, height: size }}
    >
      <ConcentricBindu size={size} alive={isThinking || spinning} ariaLabel={label} />
    </span>
  );

  if (href === null) {
    return <span className="inline-flex flex-shrink-0">{inner}</span>;
  }

  return (
    <Link
      href={href}
      aria-label={label}
      className="inline-flex flex-shrink-0 transition-transform duration-300 hover:scale-105 active:scale-95"
    >
      {inner}
    </Link>
  );
}

interface WordmarkProps {
  /** Tagline under the wordmark. Pass null to hide. */
  tagline?: string | null;
  className?: string;
}

/**
 * The PuranGPT wordmark lockup: "PuranGPT" set in Marcellus, plus an optional
 * tagline. Pair with <Logo /> for the full brand lockup.
 */
export function Wordmark({ tagline = "Sacred Texts AI", className = "" }: WordmarkProps) {
  return (
    <div className={className}>
      <h1
        className="text-xl font-bold leading-tight text-[#e2d4b2]"
        style={{ fontFamily: "var(--font-display)" }}
      >
        PuranGPT
      </h1>
      {tagline && (
        <p
          className="text-center text-[9px] uppercase tracking-widest"
          style={{ fontFamily: "var(--font-ui)", color: "#6b5a3a" }}
        >
          {tagline}
        </p>
      )}
    </div>
  );
}
