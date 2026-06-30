"use client";

import { useEffect, useRef, useState, useMemo } from "react";

const CAPTIONS = [
  "Tapping into the void…",
  "Travelling through the multiverse…",
  "Consulting the akashic archive…",
  "Untangling karma's algorithm…",
  "Asking the rishis for a second opinion…",
  "Decoding the cosmic syntax…",
  "Folding the lotus of a thousand petals…",
  "Listening for the unstruck sound…",
  "Om Namah Shivaya…",
  "Tamaso ma jyotirgamaya…",
  "Aham Brahmasmi…",
  "Tat Tvam Asi…",
  "Ekam sat vipra bahudha vadanti…",
  "Satyam Shivam Sundaram…",
];

/** Six outer points of the Flower of Life ring. */
const FLOWER = Array.from({ length: 6 }, (_, i) => {
  const a = (Math.PI / 3) * i - Math.PI / 2;
  return { cx: 100 + 26 * Math.cos(a), cy: 100 + 26 * Math.sin(a) };
});

/** Generate vortex spiral points — logarithmic spiral from center outward. */
function spiralPoints(
  cx: number, cy: number,
  startAngle: number,
  turns: number,
  segments: number,
  maxR: number,
): string {
  const pts: string[] = [];
  const b = 0.18;
  for (let i = 0; i <= segments; i++) {
    const t = i / segments;
    const angle = startAngle + t * turns * Math.PI * 2;
    const r = maxR * Math.pow(t, 0.65) * (1 + b * t * turns);
    pts.push(`${(cx + r * Math.cos(angle)).toFixed(2)},${(cy + r * Math.sin(angle)).toFixed(2)}`);
  }
  return pts.join(" ");
}

const SPIRAL_ARMS = Array.from({ length: 5 }, (_, i) => ({
  startAngle: (Math.PI * 2 / 5) * i + Math.PI / 6,
  points: spiralPoints(100, 100, (Math.PI * 2 / 5) * i + Math.PI / 6, 2.2, 80, 52),
}));

const ORBITERS = Array.from({ length: 4 }, (_, i) => ({
  startPhase: i * 0.23,
  speed: 0.6 + i * 0.35,
  r: 1 + i * 0.3,
}));

function makeParticles(count: number) {
  const seed = (s: number) => {
    let x = Math.sin(s * 127.1 + 311.7) * 43758.5453;
    return x - Math.floor(x);
  };
  return Array.from({ length: count }, (_, i) => {
    const angle = seed(i * 3) * Math.PI * 2;
    const dist = seed(i * 7 + 1) * 210;
    return {
      id: i,
      cx: 100 + Math.cos(angle) * dist * 0.6,
      cy: 100 + Math.sin(angle) * dist * 0.8,
      r: 0.3 + seed(i * 11 + 2) * 1.2,
      opacityMin: (0.06 + seed(i * 13 + 3) * 0.12).toFixed(3),
      opacityMax: (0.14 + seed(i * 17 + 4) * 0.22).toFixed(3),
      dx: ((seed(i * 19 + 5) - 0.5) * 22).toFixed(1),
      dy: ((seed(i * 23 + 6) - 0.5) * 26).toFixed(1),
      driftDur: (8 + seed(i * 29 + 7) * 14).toFixed(1),
      delay: (seed(i * 31 + 8) * -9).toFixed(1),
    };
  });
}

type AnchorPos = {
  top?: string; bottom?: string;
  left?: string; right?: string;
  textAlign: "left" | "right";
};
const ANCHORS: AnchorPos[] = [
  { top: "8%",    left: "3%",   textAlign: "left" },
  { top: "8%",    right: "3%",  textAlign: "right" },
  { bottom: "8%", left: "3%",   textAlign: "left" },
  { bottom: "8%", right: "3%",  textAlign: "right" },
];

const SLOT_A = [0, 3];
const SLOT_B = [1, 2];

function FloatingCaption({
  startDelay,
  anchorIndices,
}: {
  startDelay: number;
  anchorIndices: number[];
}) {
  const [text, setText] = useState("");
  const [visible, setVisible] = useState(false);
  const [anchor, setAnchor] = useState<AnchorPos>(ANCHORS[0]);
  const stepRef = useRef(0);
  const phraseIdxRef = useRef(Math.floor(Math.random() * CAPTIONS.length));

  useEffect(() => {
    let t: ReturnType<typeof setTimeout>;
    let mounted = true;

    const cycle = () => {
      if (!mounted) return;
      phraseIdxRef.current =
        (phraseIdxRef.current + 1 + Math.floor(Math.random() * 3)) %
        CAPTIONS.length;
      const anchorIdx = anchorIndices[stepRef.current % anchorIndices.length];
      stepRef.current++;
      setText(CAPTIONS[phraseIdxRef.current]);
      setAnchor(ANCHORS[anchorIdx]);
      setVisible(true);
      t = setTimeout(() => {
        if (!mounted) return;
        setVisible(false);
        t = setTimeout(cycle, 560);
      }, 2450);
    };

    t = setTimeout(cycle, startDelay);
    return () => {
      mounted = false;
      clearTimeout(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!text) return null;

  const { textAlign, ...posStyles } = anchor;
  return (
    <span
      style={{
        position: "absolute",
        ...posStyles,
        textAlign,
        opacity: visible ? 0.7 : 0,
        transition: "opacity 0.55s ease",
        fontFamily: "var(--font-display)",
        fontSize: "10.5px",
        color: "#9c8150",
        maxWidth: "30%",
        lineHeight: 1.5,
        letterSpacing: "0.06em",
        pointerEvents: "none",
        zIndex: 2,
      }}
    >
      {text}
    </span>
  );
}

/**
 * Sacred-geometry "thinking" visualization.
 *
 * Layers (back → front):
 *  1. Void aura — breathing indigo/violet/ember radial gradients (CSS-only
 *     echo of the DarshanVoid aurora), encircling the centre with slow
 *     colour-shift.
 *  2. Void particle field — 55 indigo + 18 slate drifting motes.
 *  3. Void halo — a pulsing ring-shadow that wraps the yantra, making the
 *     void feel present and enveloping.
 *  4. Dark radial pool — edges crushed to OLED black, a tighter dark ring
 *     around the yantra so the void reads as encircling it.
 *  5. The yantra itself — spiral vortex arms, counter-rotating mandala rings,
 *     Shatkona hexagram, Flower of Life, pulsing bindu, orbiting motes.
 *     Scaled to 150×150 (75%) — a tight, focused sacred instrument rather
 *     than filling the view.
 *  6. Floating Sanskrit captions cycle diagonally.
 *
 * All fast-looping rotation via requestAnimationFrame on SVG attributes.
 * Honours prefers-reduced-motion.
 */
export function SacredGeometryLoader() {
  const ringOuter = useRef<SVGGElement>(null);
  const ringMid = useRef<SVGGElement>(null);
  const hexA = useRef<SVGGElement>(null);
  const hexB = useRef<SVGGElement>(null);
  const flower = useRef<SVGGElement>(null);
  const spiralRefs = useRef<(SVGPolylineElement | null)[]>([]);
  const svgWrapRef = useRef<HTMLDivElement>(null);

  // Only render after client mount — random particle positions
  // differ between SSR and hydration, causing attribute mismatches.
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);
  if (!mounted) return null;

  const particles = useMemo(() => makeParticles(55), []);

  useEffect(() => {
    let a = Math.random() * 360;        // already spinning on first frame
    let yPhase = Math.random() * Math.PI * 2;  // already rocking on Y
    let xPhase = Math.PI / 4 + Math.random();  // slight X tilt variation
    let raf: number;

    const tick = () => {
      a += 0.4;
      yPhase = (yPhase + 0.009) % (Math.PI * 2);
      xPhase = (xPhase + 0.0055) % (Math.PI * 2);

      ringOuter.current?.setAttribute("transform", `rotate(${a * 0.6}, 100, 100)`);
      ringMid.current?.setAttribute("transform", `rotate(${-a * 0.9}, 100, 100)`);
      hexA.current?.setAttribute("transform", `rotate(${a * 0.5}, 100, 100)`);
      hexB.current?.setAttribute("transform", `rotate(${-a * 0.5}, 100, 100)`);
      flower.current?.setAttribute("transform", `rotate(${a * 1.2}, 100, 100)`);

      for (let i = 0; i < SPIRAL_ARMS.length; i++) {
        const speed = 0.45 + i * 0.25;
        spiralRefs.current[i]?.setAttribute(
          "transform", `rotate(${a * speed}, 100, 100)`,
        );
        spiralRefs.current[5 + i]?.setAttribute(
          "transform", `rotate(${-a * speed * 0.7}, 100, 100)`,
        );
      }

      if (svgWrapRef.current) {
        const yAngle = (Math.sin(yPhase) * 16).toFixed(1);
        const xAngle = (Math.sin(xPhase) * 6).toFixed(1);
        svgWrapRef.current.style.transform =
          `perspective(500px) rotateY(${yAngle}deg) rotateX(${xAngle}deg)`;
      }

      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  // Yantra size — 150px (75% of the original 200), a tighter focal instrument.
  const YANTRA = 150;

  return (
    <div
      className="relative flex w-full items-center justify-center"
      style={{ minHeight: 380 }}
    >
      {/* ── Layer 1: Void aura — breathing indigo/violet/ember encircling ── */}
      <div className="void-aura" />

      {/* ── Layer 2: Void particle field — drifting motes ────────────────── */}
      <svg
        className="absolute inset-0 w-full h-full pointer-events-none"
        viewBox="0 0 200 200"
        preserveAspectRatio="xMidYMid slice"
        aria-hidden="true"
        style={{ zIndex: 0 }}
      >
        {particles.map((p) => (
          <circle
            key={p.id}
            cx={p.cx} cy={p.cy} r={p.r}
            fill="#a78bfa"
            className="void-particle"
            style={{
              "--dx": `${p.dx}px`,
              "--dy": `${p.dy}px`,
              "--drift-dur": `${p.driftDur}s`,
              "--opacity-min": p.opacityMin,
              "--opacity-max": p.opacityMax,
              animationDelay: `${p.delay}s`,
            } as React.CSSProperties}
          />
        ))}
        {particles.slice(0, 18).map((p, i) => (
          <circle
            key={`s-${i}`}
            cx={100 - (p.cx - 100) * 0.7}
            cy={100 - (p.cy - 100) * 0.7}
            r={p.r * 0.7}
            fill="#7e92b8"
            className="void-particle"
            style={{
              "--dx": `${-parseFloat(p.dx) * 0.8}px`,
              "--dy": `${-parseFloat(p.dy) * 0.8}px`,
              "--drift-dur": `${parseFloat(p.driftDur) + 3}s`,
              "--opacity-min": (parseFloat(p.opacityMin) * 0.7).toFixed(3),
              "--opacity-max": (parseFloat(p.opacityMax) * 0.7).toFixed(3),
              animationDelay: `${parseFloat(p.delay) - 3}s`,
            } as React.CSSProperties}
          />
        ))}
      </svg>

      {/* ── Layer 3: Void halo — encircling ring-shadow around the yantra ── */}
      <div
        className="void-halo"
        style={{
          width: YANTRA + 64,
          height: YANTRA + 64,
          top: `calc(50% - ${(YANTRA + 64) / 2}px)`,
          left: `calc(50% - ${(YANTRA + 64) / 2}px)`,
          zIndex: 0,
        }}
      />

      {/* ── Layer 4: Dark radial pool — crushes edges, tighter ring at centre */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          zIndex: 1,
          background:
            "radial-gradient(ellipse 45% 40% at 50% 50%, transparent 22%, rgba(0,0,0,0.35) 48%, rgba(0,0,0,0.70) 72%, #000000 100%)",
        }}
      />

      {/* ── Layer 6: Floating captions ──────────────────────────────────── */}
      <FloatingCaption startDelay={400}  anchorIndices={SLOT_A} />
      <FloatingCaption startDelay={1700} anchorIndices={SLOT_B} />

      {/* ── Layer 5: The yantra — tighter, at 75% scale ─────────────────── */}
      <div
        ref={svgWrapRef}
        style={{
          width: YANTRA,
          height: YANTRA,
          filter: "drop-shadow(0 0 14px rgba(139,92,246,0.38))",
          willChange: "transform",
          transformOrigin: "center center",
          zIndex: 2,
        }}
      >
        <div className="sacred-glitch h-full w-full">
          <svg viewBox="0 0 200 200" className="h-full w-full" aria-hidden="true">
            <defs>
              <linearGradient id="sgGold" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#a5b4fc">
                  <animate attributeName="stop-color" dur="7s" repeatCount="indefinite"
                    values="#a5b4fc;#f1dda3;#a78bfa;#a5b4fc" />
                </stop>
                <stop offset="55%" stopColor="#a78bfa">
                  <animate attributeName="stop-color" dur="7s" repeatCount="indefinite"
                    values="#a78bfa;#8b5cf6;#a78bfa;#a78bfa" />
                </stop>
                <stop offset="100%" stopColor="#a78bfa" />
              </linearGradient>
              <linearGradient id="sgSlate" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#9fb0d4">
                  <animate attributeName="stop-color" dur="7s" repeatCount="indefinite"
                    values="#9fb0d4;#7e92b8;#6f84ad;#9fb0d4" />
                </stop>
                <stop offset="100%" stopColor="#7e92b8" />
              </linearGradient>
              <radialGradient id="sgSpiral" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#a5b4fc" stopOpacity="0.9" />
                <stop offset="25%" stopColor="#a78bfa" stopOpacity="0.55" />
                <stop offset="60%" stopColor="#8b5cf6" stopOpacity="0.15" />
                <stop offset="100%" stopColor="#a78bfa" stopOpacity="0" />
              </radialGradient>
              <radialGradient id="sgBindu" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#fff3d6" />
                <stop offset="40%" stopColor="#a5b4fc" />
                <stop offset="100%" stopColor="#a78bfa" />
              </radialGradient>
            </defs>

            {/* Vortex spiral arms */}
            <g fill="none">
              {SPIRAL_ARMS.map((arm, i) => (
                <polyline
                  key={i}
                  ref={(el) => { spiralRefs.current[i] = el; }}
                  points={arm.points}
                  stroke="url(#sgSpiral)"
                  strokeWidth={i < 2 ? 0.7 : 0.5}
                  opacity={0.55 + i * 0.06}
                  strokeLinecap="round" strokeLinejoin="round"
                />
              ))}
              {SPIRAL_ARMS.map((arm, i) => (
                <polyline
                  key={`cs-${i}`}
                  ref={(el) => { spiralRefs.current[5 + i] = el; }}
                  points={arm.points}
                  stroke="url(#sgSlate)"
                  strokeWidth={0.4} opacity={0.28}
                  strokeLinecap="round" strokeLinejoin="round"
                />
              ))}
            </g>

            <g stroke="url(#sgGold)" fill="none">
              <g ref={ringOuter}>
                <circle cx="100" cy="100" r="92" strokeWidth="1" strokeDasharray="3 10" opacity="0.55" />
                <circle cx="100" cy="100" r="84" strokeWidth="1.5" strokeDasharray="14 6" opacity="0.8" />
              </g>
              <g ref={ringMid} opacity="0.7" stroke="url(#sgSlate)">
                <circle cx="100" cy="100" r="72" strokeWidth="1" strokeDasharray="2 6" />
                {Array.from({ length: 12 }).map((_, j) => {
                  const ang = (Math.PI / 6) * j;
                  return (
                    <line key={j}
                      x1={100 + 62 * Math.cos(ang)} y1={100 + 62 * Math.sin(ang)}
                      x2={100 + 72 * Math.cos(ang)} y2={100 + 72 * Math.sin(ang)}
                      strokeWidth="1"
                    />
                  );
                })}
              </g>
              <g ref={hexA} opacity="0.9">
                <polygon points="100,42 150,128 50,128" strokeWidth="1.5" />
              </g>
              <g ref={hexB} opacity="0.75" stroke="url(#sgSlate)">
                <polygon points="100,158 50,72 150,72" strokeWidth="1.5" />
              </g>
              <g ref={flower} opacity="0.85">
                <circle cx="100" cy="100" r="26" strokeWidth="1" />
                {FLOWER.map((p, j) => (
                  <circle key={j} cx={p.cx} cy={p.cy} r="26" strokeWidth="1" />
                ))}
              </g>
            </g>

            {/* Orbiting motes */}
            {ORBITERS.map((o, i) => (
              <circle key={`orb-${i}`} cx="100" cy="100" r={o.r} fill="#a5b4fc" opacity="0.45">
                <animateMotion
                  dur={`${4 + i * 2.2}s`} repeatCount="indefinite"
                  path="M100,48 C140,70 130,120 100,130 C70,120 60,70 100,48"
                  begin={`${o.startPhase * 3}s`}
                />
              </circle>
            ))}

            {/* Pulsing bindu */}
            <circle className="sacred-bindu" cx="100" cy="100" r="4.5" fill="url(#sgBindu)" />
            <circle cx="100" cy="100" r="8" fill="none" stroke="#a5b4fc" strokeWidth="0.4" opacity="0.3" className="sacred-bindu" />
          </svg>
        </div>
      </div>
    </div>
  );
}
