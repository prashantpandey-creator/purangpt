/**
 * SacredIcons — a bespoke line-icon set drawn for PuranGPT's "Twilight Sanctum".
 *
 * One visual language: 24×24 grid, 1.6 stroke, `currentColor` so each icon takes
 * the candlelit-gold of an active row and the dim-brass of a resting one — exactly
 * like the lucide icons they replace. Motifs are Vedic, not generic:
 *   FlameIcon  — a diya flame (new inquiry)
 *   YantraEyeIcon — circle + downward trikona + bindu (deep seeing)
 *   SanghaIcon — three linked souls (community)
 *   PothiIcon  — bound palm-leaf manuscript (the text library)
 *   ScrollIcon — an unfurled scroll on its rollers (your workspace)
 *   LotusIcon  — a lotus in bloom (about / the source)
 */
import * as React from "react";

type IconProps = { className?: string };

const base = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

export function FlameIcon({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M12 2.5c2.6 3.4 4 5.6 4 8.3a4 4 0 0 1-8 0c0-1.3.5-2.5 1.5-3.7C10.6 8.8 11.3 6.4 12 2.5Z" />
      <path d="M12 13.6c1 0 1.8-.8 1.8-1.8 0-1-.8-1.8-1.8-3.2-1 1.4-1.8 2.2-1.8 3.2 0 1 .8 1.8 1.8 1.8Z" />
    </svg>
  );
}

export function YantraEyeIcon({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <circle cx="12" cy="12" r="8.4" />
      <path d="M6.6 9.6h10.8L12 17.4Z" />
      <circle cx="12" cy="11.4" r="1.05" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function SanghaIcon({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <circle cx="12" cy="6" r="2.3" />
      <circle cx="6.4" cy="16" r="2.3" />
      <circle cx="17.6" cy="16" r="2.3" />
      <path d="M10.9 7.9 7.5 13.9M13.1 7.9 16.5 13.9M8.7 16h6.6" />
    </svg>
  );
}

export function PothiIcon({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <rect x="3.6" y="6.6" width="16.8" height="2.7" rx="0.9" />
      <rect x="3.6" y="10.65" width="16.8" height="2.7" rx="0.9" />
      <rect x="3.6" y="14.7" width="16.8" height="2.7" rx="0.9" />
      <path d="M8 5.4v13.2" />
      <circle cx="8" cy="5.4" r="0.9" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function ScrollIcon({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <rect x="3.8" y="6" width="2.8" height="12" rx="1.4" />
      <rect x="17.4" y="6" width="2.8" height="12" rx="1.4" />
      <path d="M6.6 7.4h10.8v9.2H6.6Z" />
      <path d="M9.2 10.6h5.6M9.2 13.4h4" />
    </svg>
  );
}

export function NadaIcon({ className }: IconProps) {
  // Nāda — the sacred sound: a bindu with waves radiating out (voice darshan).
  return (
    <svg className={className} {...base}>
      <circle cx="6.4" cy="12" r="1.5" fill="currentColor" stroke="none" />
      <path d="M10.4 8.4a5 5 0 0 1 0 7.2" />
      <path d="M13.4 6.2a8.5 8.5 0 0 1 0 11.6" />
      <path d="M16.4 4.2a12 12 0 0 1 0 15.6" />
    </svg>
  );
}

export function LotusIcon({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M12 5c1.6 2 2.4 4 2.4 6.4 0 1.5-1 2.8-2.4 2.8s-2.4-1.3-2.4-2.8C9.6 9 10.4 7 12 5Z" />
      <path d="M9.2 9.4C7.4 10 6 11.2 5.2 13c1.8.6 3.6.4 5-.6M14.8 9.4c1.8.6 3.2 1.8 4 3.6-1.8.6-3.6.4-5-.6" />
      <path d="M5 14.5c2 2 4.4 3 7 3s5-1 7-3" />
    </svg>
  );
}
