"use client";

import { useEffect, useRef } from "react";
import { setFlight } from "@/lib/binduPulse";

export type ConsumeTrigger = {
  id: string;
  text: string;
  fromX: number;
  fromY: number;
  toX: number;
  toY: number;
} | null;

/**
 * The "consume" effect — the living-particle version of the prototype.
 *
 * When a question is sent, its text is rendered into a field of gold particles
 * that collapse — symmetrically, as glowing fibers in a single uniform vortex —
 * into the Bindu orb's on-screen position. A transparent, full-viewport overlay:
 * trails fade via `destination-out` (which erases alpha) so the live chat shows
 * through and is NEVER darkened by a black wash. Fibers are drawn additively
 * (`lighter`) so the convergence point blooms as they pour in.
 */
export function ConsumeFibers({
  trigger,
  onDone,
}: {
  trigger: ConsumeTrigger;
  onDone: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);
  const doneRef = useRef(onDone);
  doneRef.current = onDone;

  useEffect(() => {
    if (!trigger) return;
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const W = window.innerWidth;
    const H = window.innerHeight;
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // ── Sample the question text into particle homes (viewport coords) ───────
    const fontPx = Math.max(15, Math.min(22, W * 0.045));
    const tc = document.createElement("canvas");
    tc.width = W;
    tc.height = H;
    const tcx = tc.getContext("2d");
    if (!tcx) {
      onDone();
      return;
    }
    tcx.font = `400 ${fontPx}px Marcellus, Georgia, serif`;
    tcx.textAlign = "center";
    tcx.textBaseline = "middle";
    tcx.fillStyle = "#fff";
    tcx.fillText(trigger.text, trigger.fromX, trigger.fromY, Math.min(W - 32, 560));

    const data = tcx.getImageData(0, 0, W, H).data;
    const cx = trigger.toX;
    const cy = trigger.toY;
    type Particle = { px: number; py: number; r0: number; a0: number; br: number };
    let pts: Particle[] = [];
    const step = 3;
    for (let y = 0; y < H; y += step) {
      for (let x = 0; x < W; x += step) {
        if (data[(y * W + x) * 4 + 3] > 110) {
          const dx = x - cx;
          const dy = y - cy;
          pts.push({
            px: x,
            py: y,
            r0: Math.hypot(dx, dy),
            a0: Math.atan2(dy, dx),
            br: 0.45 + Math.random() * 0.55,
          });
        }
      }
    }
    if (pts.length === 0) {
      onDone();
      return;
    }
    if (pts.length > 1500) {
      const keep: Particle[] = [];
      const s = Math.ceil(pts.length / 1500);
      for (let i = 0; i < pts.length; i += s) keep.push(pts[i]);
      pts = keep;
    }

    const dur = 1400;
    let start = 0;
    let cancelled = false;

    const frame = (ts: number) => {
      if (cancelled) return;
      if (!start) start = ts;
      const t = Math.min((ts - start) / dur, 1);
      setFlight(t);
      const k = t * t; // accelerate inward

      // Erase ~20% of existing alpha → trails fade, page stays visible.
      ctx.globalCompositeOperation = "destination-out";
      ctx.fillStyle = "rgba(0,0,0,0.20)";
      ctx.fillRect(0, 0, W, H);

      // Additive gold fibers — a single uniform swirl = symmetric vortex.
      ctx.globalCompositeOperation = "lighter";
      ctx.lineWidth = 1.2;
      for (let i = 0; i < pts.length; i++) {
        const p = pts[i];
        const r = p.r0 * (1 - k);
        const a = p.a0 + 1.15 * k;
        const nx = cx + r * Math.cos(a);
        const ny = cy + r * Math.sin(a);
        const b = Math.max(0, Math.min(1, (0.12 + 0.6 * (1 - r / Math.max(p.r0, 1))) * p.br));
        ctx.strokeStyle = `rgba(231,205,132,${b.toFixed(3)})`;
        ctx.beginPath();
        ctx.moveTo(p.px, p.py);
        ctx.lineTo(nx, ny);
        ctx.stroke();
        p.px = nx;
        p.py = ny;
      }

      if (t < 1) {
        rafRef.current = requestAnimationFrame(frame);
      } else {
        let fadeStart = 0;
        const fade = (ts2: number) => {
          if (cancelled) return;
          if (!fadeStart) fadeStart = ts2;
          const f = Math.min((ts2 - fadeStart) / 360, 1);
          ctx.globalCompositeOperation = "destination-out";
          ctx.fillStyle = "rgba(0,0,0,0.45)";
          ctx.fillRect(0, 0, W, H);
          if (f < 1) requestAnimationFrame(fade);
          else {
            ctx.clearRect(0, 0, W, H);
            doneRef.current();
          }
        };
        requestAnimationFrame(fade);
      }
    };
    rafRef.current = requestAnimationFrame(frame);

    return () => {
      cancelled = true;
      setFlight(0);
      cancelAnimationFrame(rafRef.current);
      const c = canvasRef.current?.getContext("2d");
      c?.clearRect(0, 0, window.innerWidth, window.innerHeight);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trigger?.id]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      className="pointer-events-none fixed inset-0 z-[55]"
      style={{ width: "100vw", height: "100vh" }}
    />
  );
}
