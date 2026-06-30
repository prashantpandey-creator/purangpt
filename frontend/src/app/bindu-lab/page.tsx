"use client";

import { useEffect, useRef, useState } from "react";
import {
  VS,
  ITER_A, ITER_B, ITER_C, ITER_D, ITER_E,
  ITER_E1, ITER_E2, ITER_E3, ITER_E4, ITER_E5,
  ITER_4D,
} from "@/lib/binduShaders";

// ─────────────────────────────────────────────────────────────────────────
//  Bindu Lab — core forms (A–E) plus Shakti sub-variations (E1–E5).
//  Visit /bindu-lab to view. Shader source lives in src/lib/binduShaders.mjs
//  (shared with the offline screenshot harness, scripts/shotBindu.mjs).
// ─────────────────────────────────────────────────────────────────────────

function compileShader(gl: WebGL2RenderingContext, type: number, src: string) {
  const s = gl.createShader(type);
  if (!s) return null;
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
    console.warn("Shader:", gl.getShaderInfoLog(s));
    gl.deleteShader(s);
    return null;
  }
  return s;
}

function BinduCanvas({ fsSrc, size }: { fsSrc: string; size: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [ok, setOk] = useState(true);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const gl = canvas.getContext("webgl2", {
      alpha: true, premultipliedAlpha: true, antialias: false,
      depth: false, stencil: false, powerPreference: "low-power",
    });
    if (!gl) { setOk(false); return; }
    const vs = compileShader(gl, gl.VERTEX_SHADER, VS);
    const fs = compileShader(gl, gl.FRAGMENT_SHADER, fsSrc);
    if (!vs || !fs) { setOk(false); return; }
    const prog = gl.createProgram()!;
    gl.attachShader(prog, vs);
    gl.attachShader(prog, fs);
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) { setOk(false); return; }
    gl.useProgram(prog);

    const buf = gl.createBuffer()!;
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]), gl.STATIC_DRAW);
    const vao = gl.createVertexArray()!;
    gl.bindVertexArray(vao);
    const aPos = gl.getAttribLocation(prog, "a_pos");
    gl.enableVertexAttribArray(aPos);
    gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);
    gl.bindVertexArray(null);

    const uT = gl.getUniformLocation(prog, "u_t");
    const uLv = gl.getUniformLocation(prog, "u_lv");

    const t0 = performance.now();
    let raf = 0;
    let level = 0;
    let target = 0;

    const animate = () => {
      const t = (performance.now() - t0) * 0.001;
      target = (Math.sin(t * 0.3) * 0.5 + 0.5);
      level += (target - level) * 0.04;

      const dpr = devicePixelRatio || 1;
      const w = Math.round(canvas.clientWidth * dpr);
      const h = Math.round(canvas.clientHeight * dpr);
      if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }

      gl.viewport(0, 0, w, h);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
      gl.useProgram(prog);
      gl.bindVertexArray(vao);
      gl.uniform1f(uT, t);
      gl.uniform1f(uLv, level);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
      raf = requestAnimationFrame(animate);
    };
    raf = requestAnimationFrame(animate);
    return () => { cancelAnimationFrame(raf); gl.getExtension("WEBGL_lose_context")?.loseContext(); };
  }, [fsSrc]);

  if (!ok) return <div style={{ width: size, height: size, background: "#1a1018", borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", color: "#666" }}>No WebGL2</div>;
  return <canvas ref={canvasRef} style={{ width: size, height: size, display: "block" }} />;
}

const CORE_ITERATIONS = [
  { key: "A", label: "Bold Rings, Compact Flame", desc: "Tighter singularity, 7 thicker rings extending well past the flame. Gravitational wave crests are bold and bright.", src: ITER_A },
  { key: "B", label: "Amoeba Membrane", desc: "The flame lives inside a wobbling organic cell boundary. Rings contained within the living membrane. Biological intelligence.", src: ITER_B },
  { key: "C", label: "Gravitational Burst", desc: "Rings PROPAGATE outward from the core like pulses. A white-hot singularity point at center. Speed intensifies when thinking.", src: ITER_C },
  { key: "D", label: "Spiral Galaxy", desc: "The rings twist into spirals via angular displacement — a galaxy or living fingerprint. Flame warp feeds the twist organically.", src: ITER_D },
  { key: "E", label: "Aurora Void (Shakti)", desc: "The original: 6 flame-energy wisps that condense out of the void, lick, and dissolve back. Blue → pink → gold over a nebular wash.", src: ITER_E },
];

const SHAKTI_VARIATIONS = [
  { key: "E1", label: "Quantum Foam", desc: "14 tiny rapid sparks — quantum vacuum fluctuations. The void seethes with micro-births and micro-deaths. No single wisp dominates; the field itself is alive.", src: ITER_E1 },
  { key: "E2", label: "Prāṇa Breath", desc: "3 enormous slow flame-breaths with rich multi-layered structure. Each swells and recedes like lungs. Majestic, meditative pace — white-hot cores bleeding through. (★ live emblem)", src: ITER_E2 },
  { key: "E3", label: "Saṅgam (Confluence)", desc: "Wisps that interact: when two drift close, a luminous energy-bridge arcs between them. The Shakti meeting itself — overlaps flare with flickering light.", src: ITER_E3 },
  { key: "E4", label: "Aurora Curtains", desc: "A continuous field of flowing aurora curtains that fold, dissolve and re-form around the centre — a transformative, ever-shifting atmosphere rather than discrete entities.", src: ITER_E4 },
  { key: "E5", label: "Comet Trails (Dhūmāvalī)", desc: "Wisps with directional flame-tails trailing behind like shooting stars circling the void. Each leaves an ephemeral luminous trace that fades into the dark.", src: ITER_E5 },
];

const DIMENSIONAL = [
  { key: "4D", label: "Hyperdimensional Void", desc: "A raymarched 3D orb: a dark void at the heart (with the Bindu seed) wrapped in a luminous halo of fire whose field rotates through the 4th dimension — it churns and turns inside-out hyperdimensionally. Gold Fresnel rim + glassy specular + antialiased edge give real depth.", src: ITER_4D },
];

const ALL = [...CORE_ITERATIONS, ...SHAKTI_VARIATIONS, ...DIMENSIONAL];

export default function BinduLabPage() {
  const [active, setActive] = useState<string | null>(null);

  const renderGrid = (items: typeof CORE_ITERATIONS) => (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 32, maxWidth: 1100, marginInline: "auto" }}>
      {items.map(it => (
        <div
          key={it.key}
          onClick={() => setActive(it.key)}
          style={{
            display: "flex", flexDirection: "column", alignItems: "center", gap: 12,
            cursor: "pointer", padding: 20, borderRadius: 16,
            background: active === it.key ? "rgba(232,182,63,0.08)" : "rgba(20,17,33,0.6)",
            border: active === it.key ? "1px solid rgba(232,182,63,0.4)" : "1px solid rgba(232,182,63,0.12)",
            transition: "all 0.3s ease",
          }}
        >
          <BinduCanvas fsSrc={it.src} size={220} />
          <div style={{ textAlign: "center" }}>
            <h2 style={{ fontFamily: "Marcellus, serif", color: "#f6d27a", fontSize: "1.05rem", margin: "4px 0" }}>
              {it.key}. {it.label}
            </h2>
            <p style={{ color: "#7e92b8", fontSize: "0.78rem", lineHeight: 1.45, maxWidth: 260 }}>
              {it.desc}
            </p>
          </div>
        </div>
      ))}
    </div>
  );

  return (
    <div style={{ minHeight: "100dvh", background: "#0A0810", padding: "2rem 1rem" }}>
      <h1 style={{ fontFamily: "Marcellus, serif", color: "#f6d27a", textAlign: "center", fontSize: "1.75rem", marginBottom: 8 }}>
        Bindu Lab
      </h1>
      <p style={{ textAlign: "center", color: "#7e92b8", fontSize: "0.85rem", marginBottom: 40, maxWidth: 520, marginInline: "auto" }}>
        Living iterations of the Bindu emblem. Core forms (A–E) and 5 Shakti sub-variations exploring flame-energy from the void. They auto-oscillate between resting and thinking. Tap to enlarge.
      </p>

      {active && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", marginBottom: 40 }}>
          <BinduCanvas fsSrc={ALL.find(i => i.key === active)!.src} size={360} />
          <p style={{ color: "#f6d27a", fontFamily: "Marcellus, serif", fontSize: "1.1rem", marginTop: 12 }}>
            {ALL.find(i => i.key === active)!.key}. {ALL.find(i => i.key === active)!.label}
          </p>
          <button
            onClick={() => setActive(null)}
            style={{ marginTop: 12, color: "#e8b63f", background: "rgba(232,182,63,0.1)", border: "1px solid rgba(232,182,63,0.3)", borderRadius: 999, padding: "6px 20px", cursor: "pointer", fontSize: "0.8rem" }}
          >
            Back to grid
          </button>
        </div>
      )}

      {/* Core Iterations */}
      <h2 style={{ fontFamily: "Marcellus, serif", color: "#7e92b8", textAlign: "center", fontSize: "1rem", marginBottom: 20, letterSpacing: "0.12em", textTransform: "uppercase" }}>
        Core Forms
      </h2>
      {renderGrid(CORE_ITERATIONS)}

      {/* Shakti Variations */}
      <div style={{ margin: "48px auto 20px", maxWidth: 400, borderTop: "1px solid rgba(232,182,63,0.15)", paddingTop: 32 }}>
        <h2 style={{ fontFamily: "Marcellus, serif", color: "#f6d27a", textAlign: "center", fontSize: "1.15rem", marginBottom: 4 }}>
          Shakti Variations
        </h2>
        <p style={{ textAlign: "center", color: "#7e92b8", fontSize: "0.78rem", lineHeight: 1.5 }}>
          Five interpretations of E&rsquo;s flame-energy void — from quantum foam to comet trails
        </p>
      </div>
      {renderGrid(SHAKTI_VARIATIONS)}

      {/* Dimensional */}
      <div style={{ margin: "48px auto 20px", maxWidth: 440, borderTop: "1px solid rgba(232,182,63,0.15)", paddingTop: 32 }}>
        <h2 style={{ fontFamily: "Marcellus, serif", color: "#f6d27a", textAlign: "center", fontSize: "1.15rem", marginBottom: 4 }}>
          Dimensional
        </h2>
        <p style={{ textAlign: "center", color: "#7e92b8", fontSize: "0.78rem", lineHeight: 1.5 }}>
          A 3D void-orb whose fire rotates through the 4th dimension
        </p>
      </div>
      {renderGrid(DIMENSIONAL)}

      <div style={{ height: 60 }} />
    </div>
  );
}
