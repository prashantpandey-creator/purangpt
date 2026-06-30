"use client";

import { useEffect, useRef, useState, useId } from "react";
import { VS, ITER_E2 } from "@/lib/binduShaders";

export type BinduState = "resting" | "listening" | "thinking" | "manifesting";

// ─── ShaktiBindu ────────────────────────────────────────────────────────
//
// The live center emblem: the "Prāṇa Breath" Shakti void (Bindu Lab iteration
// E2). Enormous, slow flame-breaths condense out of the void, swell like lungs,
// drift on their orbit, and dissolve back — a golden ring encircles the dark
// bindu core. Same single-draw WebGL2 contract as GurujiBindu (u_t, u_lv) and
// the same drop-in props, so it replaces it cleanly in the chat. Shader source
// is shared from src/lib/binduShaders.mjs (also used by the screenshot harness).

const VS_SRC = VS;
const FS_SRC = ITER_E2;

function compile(gl: WebGL2RenderingContext, type: number, src: string) {
  const s = gl.createShader(type);
  if (!s) return null;
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
    if (process.env.NODE_ENV !== "production")
      console.warn("Shakti shader:", gl.getShaderInfoLog(s));
    gl.deleteShader(s);
    return null;
  }
  return s;
}

function link(gl: WebGL2RenderingContext, vs: WebGLShader, fs: WebGLShader) {
  const p = gl.createProgram();
  if (!p) return null;
  gl.attachShader(p, vs);
  gl.attachShader(p, fs);
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) {
    if (process.env.NODE_ENV !== "production")
      console.warn("Shakti link:", gl.getProgramInfoLog(p));
    gl.deleteProgram(p);
    return null;
  }
  return p;
}

export function ShaktiBindu({
  state = "resting",
  size = 200,
  className,
  ariaLabel = "Guruji",
}: {
  state?: BinduState;
  size?: number;
  className?: string;
  ariaLabel?: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef<BinduState>(state);
  const [fallback, setFallback] = useState(false);
  const uid = useId();

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    // Reduced-motion users still get the FULL shader, frozen at a pleasing phase
    // (rich visual, no looping motion) — the flat SVG is reserved strictly for
    // devices where WebGL2 is genuinely unavailable.
    const reduced =
      typeof window !== "undefined" &&
      !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const gl = canvas.getContext("webgl2", {
      alpha: true,
      premultipliedAlpha: true,
      antialias: false,
      depth: false,
      stencil: false,
      powerPreference: "low-power",
    });
    if (!gl) {
      setFallback(true);
      return;
    }

    const vs = compile(gl, gl.VERTEX_SHADER, VS_SRC);
    const fs = compile(gl, gl.FRAGMENT_SHADER, FS_SRC);
    if (!vs || !fs) {
      setFallback(true);
      return;
    }

    const prog = link(gl, vs, fs);
    if (!prog) {
      setFallback(true);
      return;
    }

    const uT = gl.getUniformLocation(prog, "u_t");
    const uLv = gl.getUniformLocation(prog, "u_lv");

    const buf = gl.createBuffer()!;
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
      gl.STATIC_DRAW,
    );

    const vao = gl.createVertexArray()!;
    gl.bindVertexArray(vao);
    const aPos = gl.getAttribLocation(prog, "a_pos");
    gl.enableVertexAttribArray(aPos);
    gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);
    gl.bindVertexArray(null);

    let level = 0;
    const t0 = performance.now();
    let raf = 0;

    const loop = () => {
      const t = reduced ? 6.0 : (performance.now() - t0) * 0.001;
      const st = stateRef.current;
      const target =
        st === "thinking" || st === "manifesting"
          ? 1.0
          : st === "listening"
            ? 0.45
            : 0.0;
      level = reduced ? target : level + (target - level) * 0.06;

      const dpr = devicePixelRatio || 1;
      const w = Math.round(canvas.clientWidth * dpr);
      const h = Math.round(canvas.clientHeight * dpr);
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }

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

      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(raf);
      gl.deleteProgram(prog);
      gl.deleteShader(vs);
      gl.deleteShader(fs);
      gl.deleteBuffer(buf);
      gl.deleteVertexArray(vao);
    };
  }, []);

  if (fallback) {
    // Only reached when WebGL2 is genuinely unavailable — a static sacred Bindu:
    // a golden ring encircling a glowing bindu core over the void.
    const id = uid.replace(/:/g, "");
    const halo = `sh${id}`;
    const core = `sc${id}`;
    return (
      <svg
        viewBox="0 0 320 320"
        width={size}
        height={size}
        className={className}
        role="img"
        aria-label={ariaLabel}
        style={{ display: "block", overflow: "visible" }}
      >
        <defs>
          <radialGradient id={halo}>
            <stop offset="0%" stopColor="#e8b63f" stopOpacity="0.4" />
            <stop offset="55%" stopColor="#3a5bd0" stopOpacity="0.14" />
            <stop offset="100%" stopColor="#3a5bd0" stopOpacity="0" />
          </radialGradient>
          <radialGradient id={core}>
            <stop offset="0%" stopColor="#fff4d6" />
            <stop offset="45%" stopColor="#f6d27a" />
            <stop offset="100%" stopColor="#e8b63f" stopOpacity="0" />
          </radialGradient>
        </defs>
        <style>{`
          @media (prefers-reduced-motion: no-preference) {
            .shakti-breathe-${id} { animation: shaktiPulse${id} 5s ease-in-out infinite; transform-origin: 160px 160px; }
          }
          @keyframes shaktiPulse${id} { 0%,100% { opacity: .85; transform: scale(1); } 50% { opacity: 1; transform: scale(1.04); } }
        `}</style>
        <g className={`shakti-breathe-${id}`}>
          <circle cx="160" cy="160" r="150" fill={`url(#${halo})`} />
          <circle cx="160" cy="160" r="96" fill="none" stroke="#e8b63f" strokeWidth={1.6} opacity="0.6" />
          <circle cx="160" cy="160" r="40" fill={`url(#${core})`} opacity="0.8" />
          <circle cx="160" cy="160" r="11" fill="#fff4d6" />
        </g>
      </svg>
    );
  }

  return (
    <canvas
      ref={canvasRef}
      style={{ width: size, height: size, display: "block" }}
      className={className}
      role="img"
      aria-label={ariaLabel}
    />
  );
}
