"use client";

/**
 * Voice Darshan — the immersive, hands-free "talking to Guruji" mode.
 *
 * Interaction model:
 *  - At rest the bindu breathes a ripple of light and a bilingual Sanskrit
 *    invocation (Jijñāsā…) — no buttons, no instructions. The pulsing IS the
 *    invitation to touch.
 *  - Touch the bindu to begin (also unlocks browser audio). After that, simply
 *    speak — VAD silence (useWhisperSTT, 350ms quiet) ends your turn.
 *  - NO ECHO: the mic is stopped while the Guru speaks, re-armed only when his
 *    audio's `ended` fires.
 *  - The spoken question is drawn UP into the flame; his answer EMERGES from it
 *    in gold (and is spoken). The whole field — DarshanVoid — leans in as he
 *    thinks and warms as he speaks.
 *  - Touch while he speaks = interrupt. Exit returns to chat.
 *  - No mic / unsupported (iOS Safari) → a text line, reply still spoken.
 *
 * Voice pipeline (2026-06-30 latency pass):
 *  - STT: WhisperSTT with 350ms VAD silence → /api/transcribe (gpt-4o-transcribe)
 *  - Speculative: interim transcripts ≥30 chars fire early LLM; tokens buffered,
 *    pushed to VoiceEngine only on final confirmation — instant audio, zero risk
 *    of speaking wrong content.
 *  - TTS: VoiceEngine streaming (20-char first flush, 40-char steady), Modal GPU
 *    "guruji" voice (XTTS→RVC chain), browser SpeechSynthesis fallback.
 *  - Budget: silence(350ms) → transcript(1-3s) → LLM think(1-3s, speculative
 *    overlap) → 20-char audio(0.5-1s) = 2-8s to first word (was 5-13s).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { X } from "lucide-react";
import { GurujiBindu, type BinduState } from "@/components/guruji/GurujiBindu";
import { DarshanVoid } from "@/components/guruji/DarshanVoid";
import { useWhisperSTT } from "@/hooks/useWhisperSTT";
import { streamChat } from "@/lib/api";
import { useLanguage } from "@/context/LanguageContext";
import { VoiceEngine } from "@/lib/voiceEngine";

const STT_LANG: Record<string, string> = { en: "en-US", hi: "hi-IN", ru: "ru-RU", fr: "fr-FR" };
const TTS_LANG: Record<string, string> = { en: "en", hi: "hi", ru: "ru", fr: "fr" };

// Bilingual Sanskrit invocation — each term carries its English gloss. Drifts
// gently while the bindu waits, opening the conversation instead of labelling a
// button.
const INVITES: Record<string, string[]> = {
  en: [
    "Jijñāsā — what do you wish to know?",
    "Praśna — bring your question.",
    "Ask, and the flame will answer.",
    "Mauna — even silence is heard.",
    "What do you seek?",
  ],
  hi: [
    "जिज्ञासा — आप क्या जानना चाहते हैं?",
    "प्रश्न — अपना प्रश्न लाइए।",
    "पूछिए, और ज्योति उत्तर देगी।",
    "मौन — मौन भी सुना जाता है।",
    "आप क्या खोजते हैं?",
  ],
  ru: [
    "Jijñāsā — что ты желаешь узнать?",
    "Praśna — задай свой вопрос.",
    "Спроси, и пламя ответит.",
    "Mauna — даже тишину слышно.",
    "Чего ты ищешь?",
  ],
};

export default function VoiceDarshanPage() {
  const router = useRouter();
  const { language } = useLanguage();
  const lang = (language || "en").toLowerCase();

  const [phase, setPhase] = useState<BinduState>("resting");
  const [started, setStarted] = useState(false);
  const [liveText, setLiveText] = useState("");
  const [answer, setAnswer] = useState("");
  const [typed, setTyped] = useState("");
  const [invI, setInvI] = useState(0);
  const [orbSize, setOrbSize] = useState(320);

  const phaseRef = useRef<BinduState>("resting");
  const setPhaseSafe = useCallback((p: BinduState) => { phaseRef.current = p; setPhase(p); }, []);
  const abortRef = useRef<AbortController | null>(null);
  const sessionRef = useRef<string>("");
  if (!sessionRef.current && typeof window !== "undefined") {
    sessionRef.current = "darshan-" + Math.random().toString(36).slice(2) + Date.now().toString(36);
  }

  // ── VoiceEngine with ElevenLabs primary → XTTS → browser cascade ──────────
  const voiceRef = useRef<VoiceEngine | null>(null);
  if (!voiceRef.current) {
    voiceRef.current = new VoiceEngine({
      voice: "guruji",
      lang: TTS_LANG[lang] || "en",
      elevenlabsKey: process.env.NEXT_PUBLIC_ELEVENLABS_API_KEY || "",
      elevenlabsVoiceId: process.env.NEXT_PUBLIC_ELEVENLABS_VOICE_ID || "",
    });
  }

  // ── Speculative execution ─────────────────────────────────────────────────
  // Interim transcripts fire an early LLM call; tokens are buffered, NOT spoken.
  // On final: if the query matches AND the speculative call completed → push the
  // buffered tokens into VoiceEngine (instant audio, LLM time was hidden). If
  // mismatched or still running → discard + restart with the final transcript.
  const specAbortRef = useRef<AbortController | null>(null);
  const specQueryRef = useRef("");
  const specActiveRef = useRef(false);
  const specDoneRef = useRef(false);
  const specTokensRef = useRef<string[]>([]);
  const lastSpecTimeRef = useRef(0);

  // ── Silence endpointing ───────────────────────────────────────────────────
  const finalsRef = useRef("");
  const SILENCE_FALLBACK_MS = 1000; // was 2400 — only fires if isFinal never arrives
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const clearSilence = useCallback(() => {
    if (silenceTimerRef.current) { clearTimeout(silenceTimerRef.current); silenceTimerRef.current = null; }
  }, []);

  // ── Responsive orb ────────────────────────────────────────────────────────
  useEffect(() => {
    const fit = () => {
      const vmin = Math.min(window.innerWidth, window.innerHeight);
      setOrbSize(Math.round(Math.max(260, Math.min(440, vmin * 0.82))));
    };
    fit();
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, []);

  // Drift the invocation only while the bindu waits at rest.
  useEffect(() => {
    if (phase !== "resting") return;
    const set = INVITES[lang] || INVITES.en;
    const id = setInterval(() => setInvI((i) => (i + 1) % set.length), 6400);
    return () => clearInterval(id);
  }, [phase, lang]);

  // ── Stop speaking (interrupt) ─────────────────────────────────────────────
  const stopSpeaking = useCallback(() => {
    voiceRef.current?.disable();
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
  }, []);

  // ── One full turn: user's words → his spoken reply → re-arm the mic ───────
  const speechRef = useRef<ReturnType<typeof useWhisperSTT> | null>(null);

  // Refs for barge-in — the mic stays open during TTS so the seeker can
  // interrupt by speaking, exactly like a real conversation. No tap needed.
  const bargeInRef = useRef(false);
  const bargeInTextRef = useRef("");

  const armListening = useCallback((forBargeIn = false) => {
    clearSilence();
    finalsRef.current = "";
    setLiveText("");
    setAnswer("");
    setMicError(null);
    if (!forBargeIn) setPhaseSafe("listening");
    bargeInRef.current = forBargeIn;
    bargeInTextRef.current = "";
    speechRef.current?.start();
  }, [setPhaseSafe, clearSilence]);

  const handleTurn = useCallback(async (userText: string) => {
    const q = userText.trim();
    if (!q) { armListening(); return; }
    speechRef.current?.stop();
    setPhaseSafe("thinking");

    // Abort any previous stream — main and speculative.
    abortRef.current?.abort();
    abortSpeculative();

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    // Enable streaming TTS — the VoiceEngine will flush at 20 chars (first
    // sentence) then 40 chars (steady), so audio starts ~1s into the LLM stream.
    voiceRef.current?.enable();

    // Arm barge-in listening: the mic stays open while Guruji speaks. If the
    // seeker starts talking, we interrupt TTS and process the new utterance —
    // exactly like a real conversation. No tap needed.
    armListening(true); // forBargeIn = true — keeps phase as "manifesting"

    let reply = "";
    try {
      for await (const ev of streamChat(
        { query: q, mode: "darshan", session_id: sessionRef.current, verbosity: "concise", language: lang },
        ctrl.signal,
      )) {
        if (ctrl.signal.aborted) break;
        if (ev.type === "token") {
          reply += ev.content;
          voiceRef.current?.pushToken(ev.content);
        } else if (ev.type === "error") break;
        else if (ev.type === "done") break;
      }
    } catch { /* aborted or network */ }

    if (ctrl.signal.aborted) {
      voiceRef.current?.disable();
      return;
    }

    // Stop barge-in listening — the turn completed normally
    bargeInRef.current = false;
    speechRef.current?.stop();

    voiceRef.current?.flushFinal();
    await voiceRef.current?.waitForDrain();

    if (ctrl.signal.aborted || phaseRef.current !== "thinking") return;

    setLiveText("");
    setAnswer(reply);
    setPhaseSafe("manifesting");
    // Brief breath before the mic opens again — lets the last syllable land.
    await new Promise((r) => setTimeout(r, 600));
    // TS narrows phaseRef to "thinking" after the guard above, but setPhaseSafe
    // mutated it to "manifesting" — widen so the interruption check is meaningful.
    if (ctrl.signal.aborted || (phaseRef.current as BinduState) !== "manifesting") return;
    armListening();
  }, [armListening, lang, setPhaseSafe]);

  // ── Speculative helpers ───────────────────────────────────────────────────
  const abortSpeculative = useCallback(() => {
    specActiveRef.current = false;
    specDoneRef.current = false;
    specTokensRef.current = [];
    try { specAbortRef.current?.abort(); } catch {}
    specAbortRef.current = null;
    specQueryRef.current = "";
  }, []);

  const fireSpeculative = useCallback(async (query: string) => {
    if (specActiveRef.current) return;
    specActiveRef.current = true;
    specDoneRef.current = false;
    specQueryRef.current = query;
    specTokensRef.current = [];

    const ctrl = new AbortController();
    specAbortRef.current = ctrl;

    try {
      for await (const ev of streamChat(
        { query, mode: "darshan", session_id: sessionRef.current, verbosity: "concise", language: lang },
        ctrl.signal,
      )) {
        if (!specActiveRef.current) break;
        if (ev.type === "token") specTokensRef.current.push(ev.content);
        else if (ev.type === "done") { specDoneRef.current = true; break; }
        else if (ev.type === "error") break;
      }
    } catch { /* aborted — the final transcript will handle it */ }
  }, [lang]);

  // ── Transcript handler ────────────────────────────────────────────────────
  const onTranscript = useCallback((text: string, isFinal: boolean) => {
    // ── Barge-in: seeker speaks while Guruji is responding ──────────────────
    if (bargeInRef.current && isFinal) {
      const q = (bargeInTextRef.current + " " + text).trim();
      if (q.length < 3) return; // too short — likely TTS echo
      bargeInRef.current = false;
      // Stop Guruji's current speech and abort the LLM
      stopSpeaking();
      abortRef.current?.abort();
      abortSpeculative();
      speechRef.current?.stop();
      clearSilence();
      // Process the barge-in utterance immediately
      void handleTurn(q);
      return;
    }
    if (bargeInRef.current && !isFinal) {
      bargeInTextRef.current = (bargeInTextRef.current + " " + text).trim();
      return; // accumulate, wait for isFinal
    }

    if (phaseRef.current !== "listening") return;
    const full = (finalsRef.current + " " + text).trim();
    setLiveText(full);

    if (isFinal) {
      // VAD has already waited 350ms silence — fire immediately.
      finalsRef.current = "";
      clearSilence();
      if (!full) return;

      // ── Check speculative match ─────────────────────────────────────────
      if (specActiveRef.current) {
        const specQ = specQueryRef.current;
        const qWords = new Set(full.toLowerCase().split(/\s+/));
        const sWords = specQ.toLowerCase().split(/\s+/);
        const shared = sWords.filter((w) => qWords.has(w)).length;
        const close =
          full.startsWith(specQ) || specQ.startsWith(full) ||
          shared >= sWords.length * 0.7;

        if (close && specDoneRef.current && specTokensRef.current.length > 0) {
          // Match! Push the buffered speculative tokens into VoiceEngine NOW
          // — instant audio, the LLM time was completely hidden.
          specActiveRef.current = false;
          specQueryRef.current = "";
          voiceRef.current?.enable();
          for (const t of specTokensRef.current) voiceRef.current?.pushToken(t);
          voiceRef.current?.flushFinal();
          // Display the speculative answer and wait for audio to drain.
          const specReply = specTokensRef.current.join("");
          setLiveText("");
          setAnswer(specReply);
          setPhaseSafe("manifesting");
          voiceRef.current?.waitForDrain().then(() => {
            if (phaseRef.current === "manifesting") {
              setTimeout(() => armListening(), 600);
            }
          });
          return;
        }
        // Mismatch — discard speculative, proceed with fresh send.
        abortSpeculative();
      }

      void handleTurn(full);
      return;
    }

    // ── Interim: maybe fire speculative send ──────────────────────────────
    const q = full.trim();
    if (
      q.length >= 30 &&
      !specActiveRef.current &&
      Date.now() - lastSpecTimeRef.current > 2000
    ) {
      lastSpecTimeRef.current = Date.now();
      specQueryRef.current = q;
      void fireSpeculative(q);
    }

    // Partial result — accumulate and arm a fallback in case isFinal never
    // arrives (network drop, mic cut, etc.).
    finalsRef.current = full;
    clearSilence();
    silenceTimerRef.current = setTimeout(() => {
      finalsRef.current = "";
      abortSpeculative();
      if (full) void handleTurn(full);
    }, SILENCE_FALLBACK_MS);
  }, [handleTurn, clearSilence, abortSpeculative, fireSpeculative, armListening]);

  const [micError, setMicError] = useState<string | null>(null);
  const onSTTError = useCallback((msg: string) => setMicError(msg), []);

  // ── Push-to-talk (PTT) — deterministic fallback, no VAD guessing ──────────
  const [pttRecording, setPttRecording] = useState(false);
  const pttRecorderRef = useRef<MediaRecorder | null>(null);
  const pttChunksRef = useRef<Blob[]>([]);
  const pttStreamRef = useRef<MediaStream | null>(null);
  const pttMimeRef = useRef("audio/webm;codecs=opus");

  const startPTT = useCallback(async () => {
    if (pttRecording || phaseRef.current !== "listening") return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      pttStreamRef.current = stream;
      const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus" : "audio/webm";
      pttMimeRef.current = mime;
      const rec = new MediaRecorder(stream, { mimeType: mime });
      pttRecorderRef.current = rec;
      pttChunksRef.current = [];
      rec.ondataavailable = (e) => { if (e.data.size > 0) pttChunksRef.current.push(e.data); };
      rec.start(200);
      setPttRecording(true);
      // Also stop the VAD-based STT while PTT is active so they don't race
      speechRef.current?.stop();
    } catch {
      setMicError("Microphone access was denied. Enable it in your browser settings.");
    }
  }, [pttRecording]);

  const stopPTT = useCallback(async () => {
    if (!pttRecording) return;
    setPttRecording(false);
    const rec = pttRecorderRef.current;
    const stream = pttStreamRef.current;
    const mime = pttMimeRef.current;
    pttRecorderRef.current = null;
    pttStreamRef.current = null;
    if (!rec) return;
    // Collect any final data then stop
    await new Promise<void>((resolve) => {
      rec.onstop = () => resolve();
      try { rec.stop(); } catch { resolve(); }
    });
    stream?.getTracks().forEach((t) => t.stop());
    const blob = new Blob(pttChunksRef.current, { type: mime });
    pttChunksRef.current = [];
    if (blob.size < 800) return; // too small — likely just a tap, no speech
    try {
      const fd = new FormData();
      fd.append("file", blob, "audio.webm");
      fd.append("lang", STT_LANG[lang] || "en-US");
      const res = await fetch("/api/transcribe", { method: "POST", body: fd });
      if (!res.ok) { setMicError("Speech recognition failed. Try again or type."); return; }
      const data = (await res.json()) as { text?: string };
      const text = (data.text || "").trim();
      if (text) void handleTurn(text);
      else setMicError("Didn't catch that. Try again or type.");
    } catch {
      setMicError("Network error. Check your connection.");
    }
  }, [pttRecording, lang, handleTurn]);

  const speech = useWhisperSTT({ lang: STT_LANG[lang] || "en-US", onTranscript, onError: onSTTError, continuous: true });
  speechRef.current = speech;

  // ── The single touch: begin · or interrupt ────────────────────────────────
  const onOrbTap = useCallback(() => {
    if (!started) {
      setStarted(true);
      try { const a = new Audio(); a.muted = true; void a.play().catch(() => {}); } catch {}
      armListening();
      return;
    }
    if (phaseRef.current === "manifesting" || phaseRef.current === "thinking") {
      abortRef.current?.abort();
      abortSpeculative();
      stopSpeaking();
      armListening();
    }
  }, [started, armListening, stopSpeaking, abortSpeculative]);

  const exit = useCallback(() => {
    abortRef.current?.abort();
    abortSpeculative();
    stopSpeaking();
    speechRef.current?.stop();
    router.push("/chat");
  }, [router, stopSpeaking, abortSpeculative]);

  useEffect(() => () => {
    clearSilence();
    abortRef.current?.abort();
    abortSpeculative();
    stopSpeaking();
    speechRef.current?.stop();
  }, [stopSpeaking, clearSilence, abortSpeculative]);

  const inviteSet = INVITES[lang] || INVITES.en;
  const showInvocation = phase === "resting";
  const showQuestion = (phase === "listening" || phase === "thinking") && !!liveText;
  const noVoice = started && !speech.supported;

  return (
    <div className="darshan-stage fixed inset-0 overflow-hidden bg-black">
      <DarshanVoid phase={phase} />

      <button
        onClick={exit}
        aria-label="Leave darshan"
        className="absolute z-30 rounded-full p-2.5 text-[#7a6a55] hover:text-[#e8b63f] transition-colors"
        style={{
          top: "max(1.1rem, env(safe-area-inset-top, 0px))",
          right: "max(1.1rem, env(safe-area-inset-right, 0px))",
        }}
      >
        <X className="h-5 w-5" />
      </button>

      {/* The bindu — edgeless, centered, the touch target */}
      <button
        type="button"
        onClick={onOrbTap}
        aria-label={!started ? "Touch to begin" : "Interrupt"}
        className="darshan-orb absolute left-1/2 z-10 outline-none"
        style={{ top: "42%", transform: "translate(-50%, -50%)", background: "transparent", border: "none", cursor: "pointer" }}
      >
        {/* Wordless invitation — a ripple of light that says: touch me */}
        {showInvocation && (
          <span className="darshan-ripplewrap" aria-hidden="true">
            <span className="darshan-ripple" />
            <span className="darshan-ripple darshan-ripple--delay" />
          </span>
        )}
        <GurujiBindu state={phase} size={orbSize} />
      </button>

      {/* The invocation the bindu breathes at rest */}
      <div className="darshan-invoke" data-show={showInvocation ? "1" : "0"} aria-live="polite">
        <span key={invI} className="darshan-invoke-line">{inviteSet[invI % inviteSet.length]}</span>
      </div>

      {/* The seeker's question — rises, then collapses into the flame */}
      <div className={`darshan-q ${showQuestion ? "is-on" : ""} ${phase === "thinking" ? "is-suck" : ""}`} aria-live="polite">
        {liveText}
      </div>

      {/* His answer — emerges from the flame in gold (and is spoken) */}
      {phase === "manifesting" && answer && (
        <>
          <div className="darshan-ascrim" aria-hidden="true" />
          <div className="darshan-a" aria-live="polite">
            {answer.split(" ").map((w, i) => (
              <span key={i} className={`darshan-aword${i === 0 ? " is-init" : ""}`} style={{ animationDelay: `${Math.min(i * 0.09, 3)}s` }}>
                {w}{" "}
              </span>
            ))}
          </div>
        </>
      )}

      {/* ── Unified status + input bar — always visible once started ──────── */}
      {started && (
        <div
          className="absolute bottom-[8%] left-1/2 z-20 w-[90%] max-w-md -translate-x-1/2"
          style={{ marginBottom: "env(safe-area-inset-bottom, 0px)" }}
          aria-live="polite"
        >
          {/* Status: what the system is doing RIGHT NOW */}
          <p className="text-center text-[11px] tracking-[0.1em] uppercase mb-2 transition-colors duration-300" style={{ fontFamily: "var(--font-ui)" }}>
            {micError ? (
              <span className="text-[#c99142]">{micError}</span>
            ) : pttRecording ? (
              <span className="text-[#e8b63f] animate-pulse">● Recording — release to send</span>
            ) : phase === "listening" && speech.speaking ? (
              <span className="text-[#e8b63f]">● Hearing you</span>
            ) : phase === "listening" ? (
              <span className="text-[#e8b63f]/60">Listening…</span>
            ) : phase === "thinking" ? (
              <span className="text-[#e8b63f]/50">Reflecting…</span>
            ) : phase === "manifesting" ? (
              <span className="text-[#e8b63f]/40">Speaking — talk to interrupt</span>
            ) : !speech.supported ? (
              <span className="text-[#7a6a55]">Voice unavailable — type below</span>
            ) : (
              <span className="text-[#7a6a55]">Speak, hold mic, or type</span>
            )}
          </p>

          {/* Heard words — shown when recognized, before they collapse into the flame */}
          {(phase === "listening" || phase === "thinking") && liveText && (
            <p className="text-center text-sm text-[#e2d4b2]/70 italic mb-2">"{liveText}"</p>
          )}

          {/* Text input + PTT mic */}
          <div className="flex items-center gap-2.5">
            <form onSubmit={(e) => { e.preventDefault(); const t = typed; setTyped(""); void handleTurn(t); }} className="flex-1">
              <input value={typed} onChange={(e) => setTyped(e.target.value)}
                placeholder="Type your question…"
                className="w-full rounded-full border border-[#e8b63f]/20 bg-black/40 px-4 py-2.5 text-center text-sm text-[#e2d4b2] outline-none backdrop-blur-sm focus:border-[#e8b63f]/50"
                style={{ fontFamily: "var(--font-body)" }} />
            </form>
            <button type="button"
              onMouseDown={(e) => { e.preventDefault(); void startPTT(); }}
              onMouseUp={(e) => { e.preventDefault(); void stopPTT(); }}
              onMouseLeave={() => { if (pttRecording) void stopPTT(); }}
              onTouchStart={(e) => { e.preventDefault(); void startPTT(); }}
              onTouchEnd={(e) => { e.preventDefault(); void stopPTT(); }}
              aria-label={pttRecording ? "Release to send" : "Hold to speak"}
              className={`flex-shrink-0 w-11 h-11 rounded-full flex items-center justify-center transition-all duration-200 ${pttRecording ? "bg-[#e8b63f]/25 border border-[#e8b63f]/60 shadow-[0_0_20px_rgba(232,182,63,0.4)]" : "border border-[#e8b63f]/20 bg-black/30 hover:border-[#e8b63f]/40"}`}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={pttRecording ? "#e8b63f" : "#7a6a55"} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={pttRecording ? "animate-pulse" : ""}>
                <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/>
              </svg>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
