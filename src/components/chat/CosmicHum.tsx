"use client";

import { useEffect, useRef } from "react";
import { getPulse } from "@/lib/binduPulse";
import { getHumEnabled, onHumBoot, onHumComplete } from "@/lib/humControl";

// The Nāda — the primordial sound. A deep chanted "Aum" built from a harmonic
// stack on the sacred 108 Hz root, shaped by vowel-formant filters and tanpura
// beating. Crucially it is STATE-AWARE: the timbre itself transforms with the
// shared intelligence pulse (binduPulse), not merely the loudness —
//
//   · At rest  → a dark, distant, near-subliminal drone. Only the root + a
//                soft octave, heavily veiled by a low filter. Felt, not heard.
//   · Thinking → the veil opens, upper harmonics and the fifth bloom in, the
//                vowel formants emerge so the "Aum" voice forms, a high aura
//                whispers in, and the breath swells deeper. The sound blossoms
//                into presence, then recedes to stillness when at rest.
//
// It can be silenced from the topbar (humControl).

const ROOT = 108; // sacred root; its octave (216) sits in the Aum chant range

// Overall loudness envelope (master gain) — kept low; timbre carries the mood.
const GAIN_REST = 0.013; // distant, almost subliminal at rest
const GAIN_PEAK = 0.05;

// The veil — a lowpass cutoff. This is the single biggest lever between
// "distant / non-intrusive" (muffled) and "present" (open). Sweeps with state.
const CUTOFF_REST = 200; // very dark: even the octave is veiled
const CUTOFF_PEAK = 1500; // open: upper harmonics + formants ring through

export function CosmicHum() {
  const ctxRef = useRef<AudioContext | null>(null);
  const startedRef = useRef(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;

    let raf = 0;

    const boot = () => {
      if (startedRef.current) return;
      startedRef.current = true;

      const ctx = new AudioContext();
      ctxRef.current = ctx;
      // Contexts are created SUSPENDED even inside a gesture — resume or silence.
      ctx.resume().catch(() => {});

      const master = ctx.createGain();
      master.gain.setValueAtTime(0, ctx.currentTime);
      master.connect(ctx.destination);

      // The veil — a lowpass whose cutoff opens as the mind awakens. At rest it
      // muffles everything above the root into a distant hum; when thinking it
      // lifts so the harmonics and the Aum voice become present.
      const veil = ctx.createBiquadFilter();
      veil.type = "lowpass";
      veil.frequency.value = CUTOFF_REST;
      veil.Q.value = 0.6;
      veil.connect(master);

      // Source bus — every partial sums here, then passes through the veil.
      const src = ctx.createGain();
      src.gain.value = 1;
      src.connect(veil);

      // Vowel formants give the drone an "Aum" mouth. Their gains are driven by
      // intensity so the VOICE only emerges when the mind is thinking — at rest
      // there is no vocal colour, just dark tone.
      const formantGains: GainNode[] = [];
      const formant = (freq: number, q: number) => {
        const bp = ctx.createBiquadFilter();
        bp.type = "bandpass";
        bp.frequency.value = freq;
        bp.Q.value = q;
        const g = ctx.createGain();
        g.gain.value = 0;
        src.connect(bp);
        bp.connect(g);
        g.connect(master);
        formantGains.push(g);
      };
      formant(460, 6); // F1 of "O"
      formant(820, 7); // F2 of "O"

      // Harmonic partials. Each carries a REST volume and a BLOOM volume; the
      // drive loop crossfades between them on intensity, so the timbre itself
      // morphs with state — partials with rest:0 are silent until the mind
      // stirs, then fade in.
      type Partial = { g: GainNode; rest: number; bloom: number; osc: OscillatorNode };
      const partials: Partial[] = [];
      const add = (hz: number, rest: number, bloom: number, type: OscillatorType = "sine") => {
        const o = ctx.createOscillator();
        o.type = type;
        o.frequency.value = hz;
        const g = ctx.createGain();
        g.gain.value = rest;
        o.connect(g).connect(src);
        o.start();
        partials.push({ g, rest, bloom, osc: o });
      };
      //   frequency           rest   bloom
      add(ROOT, 0.5, 0.5); //                      Sa — the ground, always present
      add(ROOT + 0.35, 0.42, 0.5); //              detuned twin → slow tanpura beating
      add(ROOT * 2, 0.1, 0.34); //                 octave — soft at rest, blooms in
      add(ROOT * 2 + 0.5, 0.0, 0.22); //           octave twin → shimmer when active
      add(ROOT * 1.5, 0.0, 0.24); //               Pa (fifth) — only when thinking
      add(ROOT * 3, 0.0, 0.12); //                 12th
      add(ROOT * 4, 0.0, 0.08); //                 double octave (432 Hz)
      add(ROOT * 6, 0.0, 0.05, "triangle"); //     high aura — the highest mind
      add(ROOT * 5, 0.0, 0.045, "triangle"); //    upper vocal presence

      // Drive volume, brightness, timbre and voice from the shared pulse; the
      // toggle gates it. Startup envelope fades the Nāda in (no click-on).
      const t0 = ctx.currentTime;
      const drive = () => {
        const { intensity, breath } = getPulse();
        const on = getHumEnabled() ? 1 : 0;
        const startup = Math.min(1, (ctx.currentTime - t0) / 4.0);
        const now = ctx.currentTime;

        // The breath swells more deeply when the mind is active.
        const depth = 0.25 + 0.3 * intensity;
        const breathEnv = 1 - depth + depth * breath;
        const loud = GAIN_REST + (GAIN_PEAK - GAIN_REST) * intensity;
        const target = loud * breathEnv * startup * on;
        // Faster ease when muting so silence feels intentional, slow when rising.
        master.gain.setTargetAtTime(target, now, on ? 0.2 : 0.4);

        // Open the veil as the mind awakens — dark/distant → present.
        const cutoff = CUTOFF_REST + (CUTOFF_PEAK - CUTOFF_REST) * intensity;
        veil.frequency.setTargetAtTime(cutoff, now, 0.5);

        // Crossfade each partial rest→bloom on intensity (the timbre morphs).
        for (const p of partials) {
          const v = p.rest + (p.bloom - p.rest) * intensity;
          p.g.gain.setTargetAtTime(v, now, 0.45);
        }

        // The Aum voice emerges only when thinking — silent at rest.
        formantGains[0]?.gain.setTargetAtTime(0.5 * intensity, now, 0.45);
        formantGains[1]?.gain.setTargetAtTime(0.32 * intensity, now, 0.45);

        raf = requestAnimationFrame(drive);
      };
      raf = requestAnimationFrame(drive);
    };

    // Resume on tab return — browsers suspend backgrounded contexts.
    const onVis = () => {
      const ctx = ctxRef.current;
      if (ctx && !document.hidden && ctx.state === "suspended") {
        ctx.resume().catch(() => {});
      }
    };
    document.addEventListener("visibilitychange", onVis);

    // Register with humControl — the audio engine boots ONLY when the seeker
    // explicitly clicks the Nāda toggle (not on any generic interaction).
    onHumBoot(boot);

    // Completion warp: when the answer arrives, sweep partials up 2-3x
    // over 0.6s while the master gain dissolves over 0.8s — a meaningful,
    // pitched ending instead of an abrupt cut.
    onHumComplete(() => {
      if (!ctxRef.current) return;
      const ctx = ctxRef.current;
      const now = ctx.currentTime;
      // Sweep every partial up 2.5 octaves — the hum ascends into a high
      // shimmer before evaporating. Each partial gets its own target so
      // the chord warps together.
      for (const p of partials) {
        p.g.gain.cancelScheduledValues(now);
        p.g.gain.setTargetAtTime(p.g.gain.value, now, 0.01);
        p.g.gain.linearRampToValueAtTime(0, now + 0.7);
        if (p.g.gain.value > 0.01) {
          p.osc.frequency.cancelScheduledValues(now);
          p.osc.frequency.setTargetAtTime(p.osc.frequency.value, now, 0.01);
          p.osc.frequency.linearRampToValueAtTime(p.osc.frequency.value * 2.8, now + 0.55);
        }
      }
      // Open the veil fully — let the warp ring bright
      veil.frequency.cancelScheduledValues(now);
      veil.frequency.setTargetAtTime(CUTOFF_PEAK * 1.3, now, 0.1);
      veil.frequency.linearRampToValueAtTime(22000, now + 0.6);
      // Master gain: let it bloom briefly then dissolve
      master.gain.cancelScheduledValues(now);
      master.gain.setTargetAtTime(GAIN_PEAK * 0.7, now, 0.05);
      master.gain.linearRampToValueAtTime(0, now + 0.9);
      // Formants bloom then vanish
      formantGains[0]?.gain.cancelScheduledValues(now);
      formantGains[0]?.gain.setTargetAtTime(0.8, now, 0.05);
      formantGains[0]?.gain.linearRampToValueAtTime(0, now + 0.7);
      formantGains[1]?.gain.cancelScheduledValues(now);
      formantGains[1]?.gain.setTargetAtTime(0.5, now, 0.05);
      formantGains[1]?.gain.linearRampToValueAtTime(0, now + 0.7);
      // After the warp, restore disabled state so the rAF loop stays silent
      setTimeout(() => {
        import("@/lib/humControl").then(({ setHumEnabled }) => {
          setHumEnabled(false);
        });
      }, 950);
    });

    return () => {
      document.removeEventListener("visibilitychange", onVis);
      cancelAnimationFrame(raf);
      if (ctxRef.current && ctxRef.current.state !== "closed") {
        ctxRef.current.close().catch(() => {});
      }
    };
  }, []);

  return null; // audio-only — no DOM
}
