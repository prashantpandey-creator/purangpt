"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Capacitor } from "@capacitor/core";

/**
 * Speech-to-text that works in BOTH targets:
 *  - Native iOS/Android (Capacitor): @capacitor-community/speech-recognition →
 *    SFSpeechRecognizer / Android SpeechRecognizer. This is the path that matters
 *    for the app, because iOS WKWebView has NO Web Speech API.
 *  - Desktop/web browser: window.(webkit)SpeechRecognition, so the mic works in
 *    the dev preview too (Chrome) for verification.
 *
 * `onTranscript(text, isFinal)` streams partial then final results. `onError(msg)`
 * surfaces WHY recognition failed (permission, unsupported, no mic, …) so the UI
 * never fails silently. The returned `error` is the same last message.
 */
type Opts = {
  lang?: string;
  continuous?: boolean;
  onTranscript: (text: string, isFinal: boolean) => void;
  onError?: (message: string) => void;
};

// Minimal shape we use off the web SpeechRecognition instance (no DOM lib types).
type WebRec = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onstart: (() => void) | null;
  onresult: ((ev: {
    resultIndex: number;
    results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }>;
  }) => void) | null;
  onend: (() => void) | null;
  onerror: ((ev: { error?: string }) => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};

function webErrorMessage(code: string): string {
  switch (code) {
    case "not-allowed":
    case "service-not-allowed":
      return "Microphone is blocked. Allow mic access for this site, then tap the mic again.";
    case "audio-capture":
      return "No microphone was found.";
    case "network":
      return "The speech service couldn't be reached — check your connection.";
    case "language-not-supported":
      return "Speech recognition isn't available for this language.";
    default:
      return `Speech recognition error: ${code}`;
  }
}

export function useSpeechToText({ lang = "en-US", continuous = false, onTranscript, onError }: Opts) {
  const [listening, setListening] = useState(false);
  const [supported, setSupported] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nativeRef = useRef<typeof import("@capacitor-community/speech-recognition").SpeechRecognition | null>(null);
  const webRef = useRef<WebRec | null>(null);
  const silenceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cbRef = useRef(onTranscript);
  const errRef = useRef(onError);
  cbRef.current = onTranscript;
  errRef.current = onError;

  const clearSilence = useCallback(() => {
    if (silenceRef.current) { clearTimeout(silenceRef.current); silenceRef.current = null; }
  }, []);

  const fail = useCallback((msg: string) => {
    setListening(false);
    setError(msg);
    clearSilence();
    errRef.current?.(msg);
  }, [clearSilence]);

  useEffect(() => {
    let alive = true;
    (async () => {
      if (Capacitor.isNativePlatform()) {
        try {
          const mod = await import("@capacitor-community/speech-recognition");
          nativeRef.current = mod.SpeechRecognition;
          const { available } = await mod.SpeechRecognition.available();
          if (alive) setSupported(!!available);
        } catch {
          if (alive) setSupported(false);
        }
      } else if (typeof window !== "undefined") {
        const w = window as unknown as { SpeechRecognition?: unknown; webkitSpeechRecognition?: unknown };
        const hasCtor = !!(w.SpeechRecognition || w.webkitSpeechRecognition);
        // Web Speech needs a secure context (https or localhost).
        if (alive) setSupported(hasCtor && (window.isSecureContext ?? true));
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const stop = useCallback(async () => {
    setListening(false);
    clearSilence();
    if (Capacitor.isNativePlatform() && nativeRef.current) {
      try {
        await nativeRef.current.stop();
        await nativeRef.current.removeAllListeners();
      } catch {
        /* already stopped */
      }
    } else if (webRef.current) {
      try {
        webRef.current.stop();
      } catch {
        /* already stopped */
      }
      webRef.current = null;
    }
  }, []);

  const start = useCallback(async () => {
    setError(null);
    if (Capacitor.isNativePlatform() && nativeRef.current) {
      const SR = nativeRef.current;
      try {
        const perm = await SR.requestPermissions();
        if (perm.speechRecognition !== "granted") {
          fail("Microphone / speech permission was denied. Enable it in Settings.");
          return;
        }
        await SR.removeAllListeners();
        await SR.addListener("partialResults", (data: { matches?: string[] }) => {
          if (data?.matches?.length) cbRef.current(data.matches[0], false);
        });
        setListening(true);
        const res = await SR.start({ language: lang, maxResults: 1, partialResults: true, popup: false });
        // On iOS, start() resolves with the final matches once recognition ends.
        const matches = (res as { matches?: string[] } | undefined)?.matches;
        if (matches?.length) cbRef.current(matches[0], true);
      } catch {
        fail("Couldn't start speech recognition on this device.");
      } finally {
        setListening(false);
      }
    } else if (typeof window !== "undefined") {
      const w = window as unknown as { SpeechRecognition?: new () => WebRec; webkitSpeechRecognition?: new () => WebRec };
      const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
      if (!Ctor) {
        fail("Voice input isn't supported in this browser — try Chrome.");
        return;
      }
      if (window.isSecureContext === false) {
        fail("Voice input needs a secure page (https or localhost).");
        return;
      }
      const rec = new Ctor();
      rec.lang = lang;
      rec.interimResults = true;
      rec.continuous = continuous;
      // Silence watchdog: the browser can take 1-2s to finalize after speech ends.
      // We force-stop after 600ms of no new results so the answer fires sooner.
      const SILENCE_WATCHDOG_MS = 600;
      const armSilence = () => {
        clearSilence();
        silenceRef.current = setTimeout(() => {
          // No result for 600ms — force the browser to finalize NOW
          try { rec.stop(); } catch { /* already stopping */ }
        }, SILENCE_WATCHDOG_MS);
      };
      rec.onstart = () => {
        setListening(true);
        setError(null);
        armSilence(); // start the watchdog
      };
      rec.onresult = (ev) => {
        armSilence(); // speech detected — reset the timer
        let txt = "";
        for (let i = ev.resultIndex; i < ev.results.length; i++) txt += ev.results[i][0].transcript;
        const last = ev.results[ev.results.length - 1];
        cbRef.current(txt, !!last.isFinal);
      };
      rec.onend = () => { clearSilence(); setListening(false); };
      rec.onerror = (ev) => {
        clearSilence();
        const code = ev?.error || "unknown";
        // no-speech / aborted are benign (user said nothing / we stopped it).
        if (code === "no-speech" || code === "aborted") {
          setListening(false);
          return;
        }
        fail(webErrorMessage(code));
      };
      webRef.current = rec;
      try {
        rec.start();
        setListening(true);
      } catch {
        // InvalidStateError (already running) — reset so the next tap works.
        try {
          rec.abort();
        } catch {
          /* ignore */
        }
        webRef.current = null;
        fail("The mic was busy — tap to try again.");
      }
    }
  }, [lang, fail]);

  const toggle = useCallback(() => {
    if (listening) void stop();
    else void start();
  }, [listening, start, stop]);

  useEffect(() => {
    return () => {
      void stop();
    };
  }, [stop]);

  return { supported, listening, error, start, stop, toggle };
}
