"use client";

import { useEffect, useRef, useState } from "react";
import { useLanguage } from "@/context/LanguageContext";
import { Globe, Check, ChevronDown } from "lucide-react";

const LANGS = [
  { code: "en", short: "EN", label: "English" },
  { code: "hi", short: "HI", label: "हिन्दी" },
  { code: "sa", short: "SA", label: "संस्कृतम्" },
  { code: "ru", short: "RU", label: "Русский" },
  { code: "fr", short: "FR", label: "Français" },
] as const;

/**
 * Language switcher. A compact globe + current-language button that opens a
 * labelled menu, so the control reads clearly as "change language" and the
 * active choice is obvious (checkmark). Selecting persists via context.
 */
export function LanguageSelector({ openDirection = "down", compact = false }: { openDirection?: "up" | "down"; compact?: boolean }) {
  const { language, setLanguage } = useLanguage();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const current = LANGS.find((l) => l.code === language) ?? LANGS[0];

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className={
          compact
            ? "flex items-center justify-center w-7 h-7 rounded-lg transition-colors hover:bg-white/[0.04]"
            : "flex items-center gap-2 rounded-full border border-[#a78bfa]/20 bg-[#141121] px-3 py-1.5 transition-colors hover:border-[#a78bfa]/40"
        }
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Language: ${current.label}`}
        title={compact ? `${current.short} — ${current.label}` : undefined}
        style={{
          fontFamily: "var(--font-ui)",
          ...(compact ? { background: 'rgba(139,92,246,0.10)', border: '1px solid rgba(139,92,246,0.22)' } : {}),
        }}
      >
        <Globe className={compact ? "h-4 w-4 text-[#a78bfa]/70" : "h-3.5 w-3.5 text-[#a78bfa]/70"} />
        {!compact && <span className="text-[11px] font-bold uppercase text-[#e5e2e1]">{current.short}</span>}
        {!compact && <ChevronDown className={`h-3 w-3 text-[#a38d7c] transition-transform ${open ? "rotate-180" : ""}`} />}
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Select language"
          className={`absolute left-1/2 z-50 w-40 -translate-x-1/2 overflow-hidden rounded-2xl border shadow-2xl ${
            openDirection === "up" ? "bottom-full mb-2" : "top-full mt-2"
          }`}
          style={{ background: "rgba(20,20,20,0.98)", borderColor: "rgba(139,92,246,0.25)", backdropFilter: "blur(16px)" }}
        >
          {LANGS.map((l) => (
            <button
              key={l.code}
              role="menuitemradio"
              aria-checked={language === l.code}
              onClick={() => {
                setLanguage(l.code);
                setOpen(false);
              }}
              className={`flex w-full items-center justify-between px-3.5 py-2.5 text-left text-sm transition-colors ${
                language === l.code ? "bg-[#a78bfa]/10 text-[#a78bfa]" : "text-[#a38d7c] hover:bg-white/5 hover:text-[#e5e2e1]"
              }`}
              style={{ fontFamily: "var(--font-ui)" }}
            >
              <span>
                <span className="mr-2 text-[10px] font-bold uppercase opacity-60">{l.short}</span>
                {l.label}
              </span>
              {language === l.code && <Check className="h-3.5 w-3.5 flex-shrink-0" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
