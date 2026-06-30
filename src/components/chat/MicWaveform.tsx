"use client";

import { useEffect, useRef } from "react";
import { computeBarLevels } from "@/lib/audioLevels";

/**
 * MicWaveform — five gold bars that breathe with the seeker's actual voice.
 *
 * It opens its OWN getUserMedia stream + AnalyserNode (the Web Speech API never
 * exposes its audio), reads the live spectrum every animation frame, and writes
 * each bar's height STRAIGHT TO THE DOM — no React state in the loop, per the
 * 60fps rule (see CLAUDE.md / YantraLoader). The spectrum→height math is the
 * pure, unit-tested `computeBarLevels`.
 *
 * Graceful degradation: where a real mic tap isn't reachable (native iOS
 * WKWebView, where getUserMedia fights the SFSpeechRecognizer audio session, or
 * any permission/Web-Audio failure) it falls back to a sine-driven timer so the
 * bars still shimmer rather than freeze. A frozen waveform reads as "broken";
 * a shimmering one reads as "listening".
 */
interface Props {
  /** Render + animate only while true (listening + transcript + motion allowed). */
  active: boolean;
  barCount?: number;
  /** Bar height bounds in px. */
  minHeight?: number;
  maxHeight?: number;
  color?: string;
}

export function MicWaveform({
  active,
  barCount = 5,
  minHeight = 5,
  maxHeight = 18,
  color = "#e8b63f",
}: Props) {
  const barsRef = useRef<Array<HTMLSpanElement | null>>([]);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (!active) return;

    let cancelled = false;
    let ctx: AudioContext | null = null;
    let stream: MediaStream | null = null;
    let analyser: AnalyserNode | null = null;
    let data: Uint8Array<ArrayBuffer> | null = null;
    const smooth = new Array<number>(barCount).fill(0);

    const setBar = (i: number, level: number) => {
      const el = barsRef.current[i];
      if (el) el.style.height = `${(minHeight + level * (maxHeight - minHeight)).toFixed(1)}px`;
    };

    const realLoop = () => {
      if (cancelled || !analyser || !data) return;
      analyser.getByteFrequencyData(data);
      const targets = computeBarLevels(data, barCount, { gain: 1.5 });
      for (let i = 0; i < barCount; i++) {
        // One-pole lerp on top of the analyser's own smoothing → liquid, not jumpy.
        smooth[i] += (targets[i] - smooth[i]) * 0.35;
        setBar(i, smooth[i]);
      }
      rafRef.current = requestAnimationFrame(realLoop);
    };

    // Sine-timer fallback — distinct phases so the bars never move in lockstep.
    const startFallback = () => {
      const phases = [0, 0.8, 1.6, 2.4, 1.2];
      const t0 = performance.now();
      const tick = (now: number) => {
        if (cancelled) return;
        const t = (now - t0) / 1000;
        for (let i = 0; i < barCount; i++) {
          const v = 0.5 + 0.5 * Math.sin(t * 6 + phases[i % phases.length]);
          setBar(i, 0.12 + v * 0.7);
        }
        rafRef.current = requestAnimationFrame(tick);
      };
      rafRef.current = requestAnimationFrame(tick);
    };

    const startReal = async () => {
      try {
        const AC =
          typeof window !== "undefined"
            ? window.AudioContext ||
              (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
            : undefined;
        if (!navigator?.mediaDevices?.getUserMedia || !AC) throw new Error("unsupported");

        stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true },
        });
        if (cancelled) {
          stream.getTracks().forEach((tr) => tr.stop());
          stream = null;
          return;
        }
        ctx = new AC();
        // An AudioContext created here (inside the effect, not the mic-tap
        // gesture) can stay 'suspended' — resume() needs the page's sticky
        // activation. If it won't reach 'running', getByteFrequencyData returns
        // all-zeros and the bars would FREEZE (worse than the timer we
        // replaced). So shimmer via the fallback rather than show dead bars.
        await ctx.resume().catch(() => {});
        if (cancelled) return;
        if (ctx.state !== "running") {
          stream.getTracks().forEach((tr) => tr.stop());
          stream = null;
          void ctx.close().catch(() => {});
          ctx = null;
          startFallback();
          return;
        }
        analyser = ctx.createAnalyser();
        analyser.fftSize = 256; // 128 bins
        analyser.smoothingTimeConstant = 0.6;
        ctx.createMediaStreamSource(stream).connect(analyser);
        data = new Uint8Array(analyser.frequencyBinCount);
        realLoop();
      } catch {
        if (!cancelled) startFallback();
      }
    };

    void startReal();

    return () => {
      cancelled = true;
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
      stream?.getTracks().forEach((tr) => tr.stop());
      ctx?.close().catch(() => {});
    };
  }, [active, barCount, minHeight, maxHeight]);

  if (!active) return null;

  return (
    <div aria-hidden style={{ display: "flex", alignItems: "center", gap: 3, height: maxHeight }}>
      {Array.from({ length: barCount }).map((_, i) => (
        <span
          key={i}
          ref={(el) => {
            barsRef.current[i] = el;
          }}
          style={{
            width: 3,
            height: minHeight,
            borderRadius: 2,
            background: color,
            display: "block",
            // Heights are driven imperatively per-frame; no CSS transition so the
            // bars track the voice with zero lag.
            transition: "none",
            boxShadow: "0 0 6px rgba(232,182,63,0.45)",
          }}
        />
      ))}
    </div>
  );
}
