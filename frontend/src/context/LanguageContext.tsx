"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

type Language = "en" | "hi" | "ru" | "fr" | "sa";

const SUPPORTED: Language[] = ["en", "hi", "ru", "fr", "sa"];

/** Map a BCP 47 language tag (e.g. "hi-IN", "ru") to our supported Language set. */
function detectLang(): Language {
  if (typeof navigator === "undefined") return "en";
  const raw = (navigator.language || (navigator as any).userLanguage || "en").toLowerCase();
  // Exact match
  if (SUPPORTED.includes(raw as Language)) return raw as Language;
  // Prefix match: "hi-IN" → "hi", "ru-RU" → "ru", "fr-FR" → "fr", "sa-IN" → "sa"
  const prefix = raw.split("-")[0];
  if (SUPPORTED.includes(prefix as Language)) return prefix as Language;
  return "en";
}

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = useState<Language>("en");

  useEffect(() => {
    // 1. Saved preference takes priority
    const stored = localStorage.getItem("purangpt_lang") as Language | null;
    if (stored && SUPPORTED.includes(stored)) {
      setLanguageState(stored);
      return;
    }
    // 2. Auto-detect from browser/OS language on first visit
    const detected = detectLang();
    setLanguageState(detected);
    localStorage.setItem("purangpt_lang", detected);
  }, []);

  // Keep the document language in sync for accessibility / correct rendering.
  useEffect(() => {
    if (typeof document !== "undefined") {
      document.documentElement.lang = language;
    }
  }, [language]);

  const setLanguage = (lang: Language) => {
    setLanguageState(lang);
    localStorage.setItem("purangpt_lang", lang);
  };

  return (
    <LanguageContext.Provider value={{ language, setLanguage }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (context === undefined) {
    throw new Error("useLanguage must be used within a LanguageProvider");
  }
  return context;
}
