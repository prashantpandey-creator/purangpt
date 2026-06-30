'use client';

import { useCallback, useRef, useEffect, useState } from 'react';
import { Capacitor } from '@capacitor/core';

// Audio feedback (ASMR taps, thinking pulse) is a NATIVE-APP-ONLY feature.
// On the web we stay silent — many users find unprompted sound on a website
// jarring — but inside the iOS/Android app the chimes are part of the feel.
function soundsAvailable(): boolean {
  if (typeof window === 'undefined') return false;
  return Capacitor.isNativePlatform();
}

// Read mute preference from localStorage (only meaningful inside the app).
function getMuted(): boolean {
  if (typeof window === 'undefined') return false;
  return localStorage.getItem('purangpt:muted') === 'true';
}

// Sound plays only when running natively AND the user hasn't muted it.
function soundsEnabled(): boolean {
  return soundsAvailable() && !getMuted();
}

export function useSound() {
  const audioCtxRef = useRef<AudioContext | null>(null);
  const [muted, setMutedState] = useState(false);
  const [available, setAvailable] = useState(false);
  const thinkingNodeRef = useRef<{ osc: OscillatorNode; gain: GainNode } | null>(null);

  // Initialise mute + availability state from environment on mount
  useEffect(() => {
    setMutedState(getMuted());
    setAvailable(soundsAvailable());
  }, []);

  const getCtx = useCallback((): AudioContext | null => {
    try {
      if (!audioCtxRef.current) {
        audioCtxRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      }
      const ctx = audioCtxRef.current;
      if (ctx.state === 'suspended') ctx.resume();
      return ctx;
    } catch {
      return null;
    }
  }, []);

  useEffect(() => {
    const initAudio = () => { getCtx(); };
    window.addEventListener('mousedown', initAudio, { once: true });
    window.addEventListener('keydown', initAudio, { once: true });
    return () => {
      window.removeEventListener('mousedown', initAudio);
      window.removeEventListener('keydown', initAudio);
      if (audioCtxRef.current?.state !== 'closed') {
        audioCtxRef.current?.close().catch(() => {});
      }
    };
  }, [getCtx]);

  /**
   * Temple-bell tap — sent on every user message.
   * Layered sine + harmonic at 600/1200Hz, 90ms decay, clearly audible.
   */
  const playClick = useCallback(() => {
    if (!soundsEnabled()) return;
    const ctx = getCtx();
    if (!ctx) return;
    try {
      // Fundamental
      const osc1 = ctx.createOscillator();
      const gain1 = ctx.createGain();
      osc1.connect(gain1);
      gain1.connect(ctx.destination);
      osc1.type = 'sine';
      osc1.frequency.setValueAtTime(600, ctx.currentTime);
      osc1.frequency.exponentialRampToValueAtTime(280, ctx.currentTime + 0.09);
      gain1.gain.setValueAtTime(0.38, ctx.currentTime);
      gain1.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.09);
      osc1.start(ctx.currentTime);
      osc1.stop(ctx.currentTime + 0.10);

      // Harmonic shimmer
      const osc2 = ctx.createOscillator();
      const gain2 = ctx.createGain();
      osc2.connect(gain2);
      gain2.connect(ctx.destination);
      osc2.type = 'sine';
      osc2.frequency.setValueAtTime(1200, ctx.currentTime);
      gain2.gain.setValueAtTime(0.12, ctx.currentTime);
      gain2.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.06);
      osc2.start(ctx.currentTime);
      osc2.stop(ctx.currentTime + 0.07);
    } catch (e) {
      console.warn('playClick failed:', e);
    }
  }, [getCtx]);

  /**
   * Two-tone completion chime — plays when the first token arrives (answer begun).
   * Low note followed immediately by a higher note, like a door-bell ding.
   */
  const playAccepted = useCallback(() => {
    if (!soundsEnabled()) return;
    const ctx = getCtx();
    if (!ctx) return;
    try {
      // First note — lower
      const osc1 = ctx.createOscillator();
      const gain1 = ctx.createGain();
      osc1.connect(gain1);
      gain1.connect(ctx.destination);
      osc1.type = 'sine';
      osc1.frequency.setValueAtTime(880, ctx.currentTime);
      gain1.gain.setValueAtTime(0.28, ctx.currentTime);
      gain1.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.12);
      osc1.start(ctx.currentTime);
      osc1.stop(ctx.currentTime + 0.13);

      // Second note — higher, delayed
      const osc2 = ctx.createOscillator();
      const gain2 = ctx.createGain();
      osc2.connect(gain2);
      gain2.connect(ctx.destination);
      osc2.type = 'sine';
      osc2.frequency.setValueAtTime(1320, ctx.currentTime + 0.07);
      gain2.gain.setValueAtTime(0, ctx.currentTime);
      gain2.gain.setValueAtTime(0.22, ctx.currentTime + 0.07);
      gain2.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.22);
      osc2.start(ctx.currentTime);
      osc2.stop(ctx.currentTime + 0.23);
    } catch (e) {
      console.warn('playAccepted failed:', e);
    }
  }, [getCtx]);

  /**
   * "Thinking" pulse — starts when the AI begins generating.
   * A low sine wave at 80Hz shaped with a slow attack/release envelope,
   * looping silently in the gain curve.  Call stopThinking() when done.
   */
  const playThinking = useCallback(() => {
    if (!soundsEnabled()) return;
    const ctx = getCtx();
    if (!ctx) return;
    // Don't stack multiple thinking sounds
    if (thinkingNodeRef.current) return;
    try {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = 'sine';
      osc.frequency.setValueAtTime(110, ctx.currentTime);

      // Rhythmic breathing pulse: 0 → 0.12 → 0 every 0.8s — clearly felt
      gain.gain.setValueAtTime(0, ctx.currentTime);
      for (let i = 0; i < 6; i++) {
        const t = ctx.currentTime + i * 0.8;
        gain.gain.setValueAtTime(0, t);
        gain.gain.linearRampToValueAtTime(0.12, t + 0.3);
        gain.gain.linearRampToValueAtTime(0, t + 0.7);
      }

      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 6 * 0.8 + 0.1); // max 4.9s auto-stop safety
      thinkingNodeRef.current = { osc, gain };
    } catch (e) {
      console.warn('playThinking failed:', e);
    }
  }, [getCtx]);

  const stopThinking = useCallback(() => {
    if (!thinkingNodeRef.current) return;
    try {
      const { osc, gain } = thinkingNodeRef.current;
      const ctx = audioCtxRef.current;
      if (ctx) {
        gain.gain.cancelScheduledValues(ctx.currentTime);
        gain.gain.setValueAtTime(gain.gain.value, ctx.currentTime);
        gain.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.1);
        osc.stop(ctx.currentTime + 0.15);
      }
    } catch {
      /* ignore */
    } finally {
      thinkingNodeRef.current = null;
    }
  }, []);

  const toggleMute = useCallback(() => {
    const next = !getMuted();
    localStorage.setItem('purangpt:muted', String(next));
    setMutedState(next);
    // Stop any in-flight thinking sound immediately on mute
    if (next) stopThinking();
  }, [stopThinking]);

  return { playClick, playAccepted, playThinking, stopThinking, muted, toggleMute, available };
}
