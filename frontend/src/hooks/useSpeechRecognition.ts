"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// ---------------------------------------------------------------------------
// useSpeechRecognition — thin wrapper around the Web Speech API
// (SpeechRecognition / webkitSpeechRecognition). Voice-to-text for the chat
// composer. Supported in Chrome, Edge, and Safari (incl. iOS WebView). Returns
// `supported: false` elsewhere so the UI can hide the mic gracefully.
//
// The recognizer streams interim results; we surface the live transcript via
// `onResult(text, isFinal)` so the caller can show speech mid-flight and commit
// the final text. We don't keep transcript state here — the composer owns the
// input value and decides how to merge.
// ---------------------------------------------------------------------------

// Minimal typings — the DOM lib doesn't ship SpeechRecognition types reliably.
interface ISpeechRecognition extends EventTarget {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: any) => void) | null;
  onerror: ((event: any) => void) | null;
  onend: (() => void) | null;
}

type SpeechRecognitionCtor = new () => ISpeechRecognition;

function getRecognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

// Map our app languages to BCP-47 locales the recognizer understands.
const LANG_MAP: Record<string, string> = {
  en: "en-US",
  hi: "hi-IN",
  ru: "ru-RU",
};

interface UseSpeechRecognitionOptions {
  lang?: string;
  /** Called with the running transcript. isFinal=true on a committed phrase. */
  onResult: (text: string, isFinal: boolean) => void;
  onError?: (error: string) => void;
}

export function useSpeechRecognition({ lang = "en", onResult, onError }: UseSpeechRecognitionOptions) {
  const [supported, setSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<ISpeechRecognition | null>(null);
  // Keep latest callbacks in refs so we don't recreate the recognizer each render.
  const onResultRef = useRef(onResult);
  const onErrorRef = useRef(onError);
  onResultRef.current = onResult;
  onErrorRef.current = onError;

  useEffect(() => {
    const Ctor = getRecognitionCtor();
    setSupported(!!Ctor);
  }, []);

  const stop = useCallback(() => {
    const rec = recognitionRef.current;
    if (rec) {
      try { rec.stop(); } catch { /* already stopped */ }
    }
    setListening(false);
  }, []);

  const start = useCallback(() => {
    const Ctor = getRecognitionCtor();
    if (!Ctor) return;

    // Tear down any previous instance before starting a fresh one.
    if (recognitionRef.current) {
      try { recognitionRef.current.abort(); } catch { /* noop */ }
      recognitionRef.current = null;
    }

    const rec = new Ctor();
    rec.lang = LANG_MAP[lang] || "en-US";
    rec.continuous = true;
    rec.interimResults = true;
    rec.maxAlternatives = 1;

    rec.onresult = (event: any) => {
      let interim = "";
      let final = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const transcript = result[0]?.transcript ?? "";
        if (result.isFinal) final += transcript;
        else interim += transcript;
      }
      if (final) onResultRef.current(final, true);
      else if (interim) onResultRef.current(interim, false);
    };

    rec.onerror = (event: any) => {
      const err = event?.error || "unknown";
      // "no-speech" / "aborted" are benign — don't surface them as errors.
      if (err !== "no-speech" && err !== "aborted") {
        onErrorRef.current?.(err);
      }
      setListening(false);
    };

    rec.onend = () => {
      setListening(false);
    };

    recognitionRef.current = rec;
    try {
      rec.start();
      setListening(true);
    } catch {
      setListening(false);
    }
  }, [lang]);

  const toggle = useCallback(() => {
    if (listening) stop();
    else start();
  }, [listening, start, stop]);

  // Clean up on unmount.
  useEffect(() => {
    return () => {
      const rec = recognitionRef.current;
      if (rec) { try { rec.abort(); } catch { /* noop */ } }
    };
  }, []);

  return { supported, listening, start, stop, toggle };
}
