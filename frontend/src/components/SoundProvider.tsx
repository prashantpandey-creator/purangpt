"use client";

import { useEffect, useRef } from "react";

export function SoundProvider() {
  const audioCtxRef = useRef<AudioContext | null>(null);

  useEffect(() => {
    // Initialize AudioContext on first user interaction to comply with browser autoplay policies
    const initAudio = () => {
      if (!audioCtxRef.current) {
        audioCtxRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      }
    };

    const playClickSound = (e: MouseEvent) => {
      initAudio();
      
      // Check if clicked element or parent is a button or link
      const target = e.target as HTMLElement;
      const isClickable = target.closest('button') || target.closest('a') || target.closest('[role="button"]') || target.closest('input[type="submit"]') || target.closest('input[type="button"]');
      
      if (isClickable && audioCtxRef.current) {
        const ctx = audioCtxRef.current;
        if (ctx.state === 'suspended') {
          ctx.resume();
        }
        
        // Create a short, subtle "macbook trackpad" like click using an oscillator
        const osc = ctx.createOscillator();
        const gainNode = ctx.createGain();
        
        // A very quick, low-pitched pop
        osc.type = 'sine';
        osc.frequency.setValueAtTime(150, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.03);
        
        // Very quick envelope
        gainNode.gain.setValueAtTime(0, ctx.currentTime);
        gainNode.gain.linearRampToValueAtTime(0.1, ctx.currentTime + 0.005);
        gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.03);
        
        osc.connect(gainNode);
        gainNode.connect(ctx.destination);
        
        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + 0.03);
      }
    };

    // Use capture phase so we hear it instantly before React event handlers potentially block/redirect
    window.addEventListener('click', playClickSound, true);

    return () => {
      window.removeEventListener('click', playClickSound, true);
      if (audioCtxRef.current) {
        audioCtxRef.current.close();
      }
    };
  }, []);

  return null;
}
