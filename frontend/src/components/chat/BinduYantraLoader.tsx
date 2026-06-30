"use client";

import { useEffect, useRef } from "react";

/**
 * BinduYantraLoader — a standalone loader mode.
 *
 * A single pulsing bindu sits at rest. Every 6–14 s it bursts outward into a
 * full yantra bloom (shatkona + flower-of-life petals + outer ring) that slowly
 * rotates at peak, then dissolves back into the bindu. All animation is driven
 * via requestAnimationFrame writing DOM styles directly — zero React re-renders
 * in the hot path, consistent with the project's 60fps animation guideline.
 */

const BLOOM_RISE  = 600;   // ms — bindu → full yantra
const BLOOM_HOLD  = 1400;  // ms — full yantra held, slowly spinning
const BLOOM_FALL  = 800;   // ms — yantra dissolves outward back to void
const BLOOM_TOTAL = BLOOM_RISE + BLOOM_HOLD + BLOOM_FALL;

const FLOWER_PETALS = Array.from({ length: 6 }, (_, i) => {
  const a = (Math.PI / 3) * i;
  return { cx: 100 + 34 * Math.cos(a), cy: 100 + 34 * Math.sin(a) };
});

const SPOKES = Array.from({ length: 12 }, (_, i) => {
  const a = (Math.PI / 6) * i;
  return {
    x1: 100 + 30 * Math.cos(a), y1: 100 + 30 * Math.sin(a),
    x2: 100 + 70 * Math.cos(a), y2: 100 + 70 * Math.sin(a),
  };
});

export function BinduYantraLoader() {
  const wrapRef    = useRef<HTMLDivElement>(null);
  const bloomRef   = useRef<SVGGElement>(null);
  const binduRef   = useRef<SVGCircleElement>(null);
  const spinRef    = useRef<SVGGElement>(null);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    let raf: number;

    const triggerBloom = () => {
      const bloom  = bloomRef.current;
      const bindu  = binduRef.current;
      const spin   = spinRef.current;
      if (!bloom || !bindu || !spin) return;

      const start = performance.now();
      let holdSpin = 0;

      const step = (now: number) => {
        const t = now - start;

        if (t < BLOOM_RISE) {
          const p    = t / BLOOM_RISE;
          const ease = 1 - Math.pow(1 - p, 3); // ease-out-cubic

          // Bloom grows from 0 → 1
          bloom.setAttribute("opacity", String(ease));
          bloom.setAttribute("transform", `scale(${0.08 + ease * 0.92}) translate(${(1 - ease) * 92} ${(1 - ease) * 92})`);

          // Bindu flares bright and large
          bindu.setAttribute("r", String(5 + ease * 7));
          bindu.setAttribute("opacity", String(0.6 + ease * 0.4));

          raf = requestAnimationFrame(step);
        } else if (t < BLOOM_RISE + BLOOM_HOLD) {
          // Hold — bloom at full opacity, slowly spinning
          holdSpin += 0.18;
          bloom.setAttribute("opacity", "1");
          bloom.setAttribute("transform", `rotate(${holdSpin}, 100, 100)`);
          spin.setAttribute("transform", `rotate(${-holdSpin * 0.6}, 100, 100)`);

          bindu.setAttribute("r", "12");
          bindu.setAttribute("opacity", "1");

          raf = requestAnimationFrame(step);
        } else if (t < BLOOM_TOTAL) {
          const p    = (t - BLOOM_RISE - BLOOM_HOLD) / BLOOM_FALL;
          const ease = p * p; // ease-in-quad — accelerates outward

          // Bloom expands and fades
          const scale = 1 + ease * 0.55;
          bloom.setAttribute("opacity", String(1 - ease));
          bloom.setAttribute("transform", `rotate(${holdSpin + ease * 20}, 100, 100) scale(${scale})`);

          // Bindu contracts back
          bindu.setAttribute("r", String(12 - ease * 7));
          bindu.setAttribute("opacity", String(1 - ease * 0.4));

          raf = requestAnimationFrame(step);
        } else {
          // Reset everything
          bloom.setAttribute("opacity", "0");
          bloom.setAttribute("transform", "");
          spin.setAttribute("transform", "");
          bindu.setAttribute("r", "5");
          bindu.setAttribute("opacity", "0.8");

          // Schedule next bloom: 6–14 s
          timer = setTimeout(triggerBloom, 6000 + Math.random() * 8000);
        }
      };

      raf = requestAnimationFrame(step);
    };

    // First bloom after 3–7 s
    timer = setTimeout(triggerBloom, 3000 + Math.random() * 4000);
    return () => { clearTimeout(timer); cancelAnimationFrame(raf); };
  }, []);

  return (
    <div
      ref={wrapRef}
      className="flex items-center justify-center"
      style={{ width: 200, height: 200 }}
    >
      <svg
        viewBox="0 0 200 200"
        className="w-full h-full"
        aria-hidden="true"
        style={{ filter: "drop-shadow(0 0 12px rgba(232,182,63,0.35))" }}
      >
        <defs>
          <radialGradient id="byBindu" cx="50%" cy="50%" r="50%">
            <stop offset="0%"   stopColor="#fff3d6" />
            <stop offset="100%" stopColor="#e8b63f" />
          </radialGradient>
          <radialGradient id="byBurst" cx="50%" cy="50%" r="50%">
            <stop offset="0%"   stopColor="#fff3d6" stopOpacity="0.22" />
            <stop offset="100%" stopColor="#e8b63f" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* Yantra bloom — hidden at rest, erupts on triggerBloom */}
        <g ref={bloomRef} opacity="0" style={{ transformOrigin: "100px 100px" }}>
          {/* Soft radial glow at center */}
          <circle cx="100" cy="100" r="64" fill="url(#byBurst)" />

          {/* Outer dashed ring */}
          <circle cx="100" cy="100" r="86" fill="none"
            stroke="#e8b63f" strokeWidth="1.1" strokeDasharray="3 9" opacity="0.6" />

          {/* Shatkona — two interlocking triangles */}
          <polygon points="100,38 156,130 44,130" fill="none"
            stroke="#f6d27a" strokeWidth="1.4" opacity="0.85" />
          <polygon points="100,162 44,70 156,70" fill="none"
            stroke="#f6d27a" strokeWidth="1.4" opacity="0.7" />

          {/* Flower of Life — center circle + six petals */}
          <g ref={spinRef} style={{ transformOrigin: "100px 100px" }}>
            <circle cx="100" cy="100" r="34" fill="none"
              stroke="#e8b63f" strokeWidth="1" opacity="0.75" />
            {FLOWER_PETALS.map((p, i) => (
              <circle key={i} cx={p.cx} cy={p.cy} r="34" fill="none"
                stroke="#e8b63f" strokeWidth="1" opacity="0.55" />
            ))}
            {/* Spokes */}
            {SPOKES.map((s, i) => (
              <line key={i}
                x1={s.x1} y1={s.y1} x2={s.x2} y2={s.y2}
                stroke="#e8b63f" strokeWidth="0.7" opacity="0.4" />
            ))}
          </g>
        </g>

        {/* Bindu — always present, flares during bloom */}
        <circle
          ref={binduRef}
          cx="100" cy="100" r="5"
          fill="url(#byBindu)"
          opacity="0.8"
          className="sacred-bindu"
          style={{ transformBox: "fill-box", transformOrigin: "center" }}
        />
      </svg>
    </div>
  );
}
