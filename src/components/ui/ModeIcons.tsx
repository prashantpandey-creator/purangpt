import type { SVGProps } from "react";

/**
 * Custom, on-brand SVG glyphs for the two answer modes. Both are stroke/fill
 * driven by `currentColor` so the parent's accent (saffron for Guru, gold for
 * Scholar) flows straight through, and they read cleanly down to ~16px.
 *
 * - GuruMode  → a lit diya (oil lamp). The guru as the one who dispels darkness
 *   with light — warm guidance.
 * - ScholarMode → an open grantha (palm-leaf manuscript) crowned by a radiant
 *   bindu — text-grounded, cited knowledge.
 */

export function GuruModeIcon({ className, ...props }: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      className={className}
      aria-hidden="true"
      {...props}
    >
      {/* flame */}
      <path
        d="M12 3.2c1.6 1.7 2.4 3 2.4 4.3a2.4 2.4 0 1 1-4.8 0c0-.8.3-1.5.9-2.2.3.5.6.7 1 .7-.4-1-.3-1.9.5-2.8z"
        fill="currentColor"
      />
      {/* bowl of the diya */}
      <path
        d="M4 13c0 2.2 3.6 3.8 8 3.8s8-1.6 8-3.8"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <path
        d="M4 13c2 1 4.9 1.6 8 1.6s6-.6 8-1.6"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        opacity="0.45"
      />
      {/* aura */}
      <path
        d="M12 9.5v1.3"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
        opacity="0.5"
      />
    </svg>
  );
}

export function ScholarModeIcon({ className, ...props }: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      className={className}
      aria-hidden="true"
      {...props}
    >
      {/* spine */}
      <path d="M12 7v13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      {/* left page */}
      <path
        d="M12 7C10.3 5.7 8 5.2 5 5.6c-.6.1-1 .6-1 1.1v9.6c0 .6.5 1.1 1.2 1 2.8-.3 5 .3 6.8 1.7"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      {/* right page */}
      <path
        d="M12 7c1.7-1.3 4-1.8 7-1.4.6.1 1 .6 1 1.1v9.6c0 .6-.5 1.1-1.2 1-2.8-.3-5 .3-6.8 1.7"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      {/* text lines */}
      <path
        d="M6.5 8.8c1.4-.2 2.6-.1 3.6.4M6.5 11.2c1.4-.2 2.6-.1 3.6.4M17.5 8.8c-1.4-.2-2.6-.1-3.6.4M17.5 11.2c-1.4-.2-2.6-.1-3.6.4"
        stroke="currentColor"
        strokeWidth="1.1"
        strokeLinecap="round"
        opacity="0.5"
      />
      {/* radiant bindu of knowledge */}
      <circle cx="12" cy="3" r="1.1" fill="currentColor" />
      <path
        d="M9.4 2.1l-.5-.4M14.6 2.1l.5-.4"
        stroke="currentColor"
        strokeWidth="1.1"
        strokeLinecap="round"
        opacity="0.55"
      />
    </svg>
  );
}
