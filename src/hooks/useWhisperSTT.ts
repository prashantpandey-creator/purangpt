"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Whisper-backed speech-to-text for the Voice Darshan.
 *
 * Drop-in replacement for useSpeechToText — same interface
 * ({ supported, listening, error, start, stop, toggle }), same onTranscript
 * callback. Uses OpenAI gpt-4o-transcribe via /api/transcribe so recognition
 * works on iOS Safari and gives quality far above the browser Web Speech API.
 *
 * Flow:
 *   start() → MediaRecorder streams audio into chunks
 *          → AudioContext AnalyserNode watches amplitude (VAD)
 *          → SILENCE_MS of quiet below threshold → flush chunk → POST /api/transcribe
 *          → onTranscript(text, true) → re-arm if still listening
 *   stop()  → MediaRecorder + AudioContext closed; no pending calls
 *
 * The hook does NOT hold state between utterances — each flush is independent.
 * The caller owns endpointing logic (darshan uses its own silence timer).
 */

type Opts = {
  lang?: string;
  /** continuous is accepted for API compat but internally the hook always re-arms after flush. */
  continuous?: boolean;
  onTranscript: (text: string, isFinal: boolean) => void;
  onError?: (message: string) => void;
};

const SILENCE_MS = 350;          // quiet before flush (was 800 — too sluggish)
const SILENCE_THRESHOLD = 0.01;  // RMS below this = silence (0–1 scale, linear)
const VAD_INTERVAL_MS = 80;      // how often we check amplitude (was 100)
const MIN_AUDIO_MS = 150;        // discard clips shorter than this (breath noise)

export function useWhisperSTT({ lang = "en-US", onTranscript, onError }: Opts) {
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [supported, setSupported] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cbRef = useRef(onTranscript);
  const errRef = useRef(onError);
  cbRef.current = onTranscript;
  errRef.current = onError;

  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const vadTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const silenceCounterRef = useRef(0);
  const recordingStartRef = useRef(0);
  const listeningRef = useRef(false); // stable ref for callbacks

  useEffect(() => {
    if (typeof window !== "undefined" && !!navigator?.mediaDevices?.getUserMedia) {
      setSupported(true);
    }
  }, []);

  const fail = useCallback((msg: string) => {
    setListening(false);
    setSpeaking(false);
    listeningRef.current = false;
    setError(msg);
    errRef.current?.(msg);
  }, []);

  const _clearVAD = useCallback(() => {
    if (vadTimerRef.current) {
      clearInterval(vadTimerRef.current);
      vadTimerRef.current = null;
    }
  }, []);

  const _flush = useCallback(async (mimeType: string) => {
    const chunks = chunksRef.current.splice(0);
    if (!chunks.length) return;
    const elapsed = Date.now() - recordingStartRef.current;
    if (elapsed < MIN_AUDIO_MS) return; // just noise

    const blob = new Blob(chunks, { type: mimeType });
    const fd = new FormData();
    fd.append("file", blob, "audio.webm");
    fd.append("lang", lang);
    try {
      const res = await fetch("/api/transcribe", { method: "POST", body: fd });
      if (!res.ok) return;
      const data = (await res.json()) as { text?: string };
      const text = (data.text || "").trim();
      if (text) cbRef.current(text, true);
    } catch {
      // network hiccup — silent. VAD re-arms for the next utterance.
    }
  }, [lang]);

  const _arm = useCallback(async () => {
    if (!listeningRef.current) return;
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
    } catch {
      fail("Microphone access was denied. Enable it in your browser settings.");
      return;
    }

    const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : "audio/webm";

    const rec = new MediaRecorder(stream, { mimeType });
    mediaRef.current = rec;
    chunksRef.current = [];
    recordingStartRef.current = Date.now();
    rec.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };
    rec.start(200); // 200ms timeslice → small chunks, low memory

    // VAD via AudioContext AnalyserNode
    const ctx = new AudioContext();
    audioCtxRef.current = ctx;
    const src = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    src.connect(analyser);
    analyserRef.current = analyser;

    const data = new Uint8Array(analyser.frequencyBinCount);
    silenceCounterRef.current = 0;

    _clearVAD();
    vadTimerRef.current = setInterval(async () => {
      if (!listeningRef.current) return;
      analyser.getByteTimeDomainData(data);
      // RMS: root mean square of (sample - 128) / 128
      let sum = 0;
      for (let i = 0; i < data.length; i++) {
        const d = (data[i] - 128) / 128;
        sum += d * d;
      }
      const rms = Math.sqrt(sum / data.length);

      if (rms < SILENCE_THRESHOLD) {
        setSpeaking(false);
        silenceCounterRef.current += VAD_INTERVAL_MS;
        if (silenceCounterRef.current >= SILENCE_MS) {
          silenceCounterRef.current = 0;
          // Flush what we have, then re-arm
          rec.stop();
          stream.getTracks().forEach((t) => t.stop());
          ctx.close().catch(() => {});
          _clearVAD();
          await _flush(mimeType);
          // Re-arm for the next utterance (continuous mode)
          if (listeningRef.current) void _arm();
        }
      } else {
        setSpeaking(true);
        silenceCounterRef.current = 0;
      }
    }, VAD_INTERVAL_MS);
  }, [fail, _flush, _clearVAD]);

  const start = useCallback(async () => {
    if (listeningRef.current) return;
    setError(null);
    setListening(true);
    setSpeaking(false);
    listeningRef.current = true;
    await _arm();
  }, [_arm]);

  const stop = useCallback(() => {
    listeningRef.current = false;
    setListening(false);
    setSpeaking(false);
    _clearVAD();
    try { mediaRef.current?.stop(); } catch {}
    mediaRef.current = null;
    chunksRef.current = [];
    try { audioCtxRef.current?.close(); } catch {}
    audioCtxRef.current = null;
    analyserRef.current = null;
  }, [_clearVAD]);

  const toggle = useCallback(() => {
    if (listeningRef.current) stop();
    else void start();
  }, [start, stop]);

  useEffect(() => () => stop(), [stop]);

  return { supported, listening, speaking, error, start, stop, toggle };
}
