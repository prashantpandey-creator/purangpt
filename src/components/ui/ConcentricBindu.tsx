"use client";

import { useEffect, useRef, useState } from "react";

// ─────────────────────────────────────────────────────────────────────────
//  ConcentricBindu — the PuranGPT brand mark.
//
//  The sacred fire at the centre is the SAME domain-warped, turbulent flame
//  render as the Guruji emblem (a real WebGL2 shader — it licks, curls and
//  flickers with that living, "peculiar" movement), framed by ordered
//  concentric rings — the gravitational field — drawn as crisp SVG that ripples
//  outward like gravitational waves. Restrained candlelit gold on transparent.
//
//  The flame is a tiny per-instance WebGL2 canvas; the rings + ripple are SVG
//  on top (transparent centre so the fire shows through). Falls back to a still
//  SVG flame where WebGL2 is unavailable, and freezes under reduced-motion.
// ─────────────────────────────────────────────────────────────────────────

const C = 50; // centre of the 0..100 viewBox
const RING_BASE = [21, 30, 39, 46]; // resting radii of the gravitational rings

const VS_SRC = /*glsl*/ `#version 300 es
in vec2 a_pos;
out vec2 v_uv;
void main() {
  v_uv = a_pos * 0.5 + 0.5;
  gl_Position = vec4(a_pos, 0.0, 1.0);
}`;

// The Guruji flame — domain-warped fire (no rings here; the SVG provides those).
const FS_SRC = /*glsl*/ `#version 300 es
precision highp float;
in vec2 v_uv;
out vec4 o;
uniform float u_t, u_lv;

float hash(float n) { return fract(sin(n * 127.1) * 43758.5453); }
vec3 mod289(vec3 x) { return x - floor(x / 289.0) * 289.0; }
vec4 mod289(vec4 x) { return x - floor(x / 289.0) * 289.0; }
vec4 permute(vec4 x) { return mod289((x * 34.0 + 1.0) * x); }
vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }
float snoise(vec3 v) {
  const vec2 C = vec2(1.0 / 6.0, 1.0 / 3.0);
  vec3 i = floor(v + dot(v, C.yyy));
  vec3 x0 = v - i + dot(i, C.xxx);
  vec3 g = step(x0.yzx, x0.xyz);
  vec3 l = 1.0 - g;
  vec3 i1 = min(g.xyz, l.zxy);
  vec3 i2 = max(g.xyz, l.zxy);
  vec3 x1 = x0 - i1 + C.xxx;
  vec3 x2 = x0 - i2 + C.yyy;
  vec3 x3 = x0 - 0.5;
  i = mod289(i);
  vec4 p = permute(permute(permute(
    i.z + vec4(0.0, i1.z, i2.z, 1.0))
    + i.y + vec4(0.0, i1.y, i2.y, 1.0))
    + i.x + vec4(0.0, i1.x, i2.x, 1.0));
  vec4 j = p - 49.0 * floor(p / 49.0);
  vec4 x_ = floor(j / 7.0);
  vec4 y_ = j - 7.0 * x_;
  vec4 x = x_ / 7.0 + 0.5 / 7.0 - 0.5;
  vec4 y = y_ / 7.0 + 0.5 / 7.0 - 0.5;
  vec4 h = 1.0 - abs(x) - abs(y);
  vec4 b0 = vec4(x.xy, y.xy);
  vec4 b1 = vec4(x.zw, y.zw);
  vec4 s0 = floor(b0) * 2.0 + 1.0;
  vec4 s1 = floor(b1) * 2.0 + 1.0;
  vec4 sh = -step(h, vec4(0.0));
  vec4 a0 = b0.xzyw + s0.xzyw * sh.xxyy;
  vec4 a1 = b1.xzyw + s1.xzyw * sh.zzww;
  vec3 p0 = vec3(a0.xy, h.x);
  vec3 p1 = vec3(a0.zw, h.y);
  vec3 p2 = vec3(a1.xy, h.z);
  vec3 p3 = vec3(a1.zw, h.w);
  vec4 norm = taylorInvSqrt(vec4(dot(p0, p0), dot(p1, p1), dot(p2, p2), dot(p3, p3)));
  p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
  vec4 m = max(0.6 - vec4(dot(x0, x0), dot(x1, x1), dot(x2, x2), dot(x3, x3)), 0.0);
  m = m * m;
  return 42.0 * dot(m * m, vec4(dot(p0, x0), dot(p1, x1), dot(p2, x2), dot(p3, x3)));
}
float fbm(vec3 p) { return 0.5 * snoise(p) + 0.25 * snoise(p * 2.03) + 0.125 * snoise(p * 4.01); }

// One Shakti aura wisp — the approved Prāṇa-aura energy: condenses, orbits the
// fire, drifts blue→pink→gold, dissolves back. Output is premultiplied.
vec4 auraWisp(vec2 st, float t, float lv, float fi) {
  float prog = t * (0.06 + fi * 0.012) + fi * 0.4;
  float ph = fract(prog);
  float cyc = floor(prog);
  float life = sin(ph * 3.14159); life *= life;
  float s1 = hash(fi * 13.0 + cyc * 7.3 + 1.0);
  float s2 = hash(fi * 5.7 + cyc * 3.1 + 2.0);
  float ang = s1 * 6.2831 + (ph - 0.5) * 0.7 + t * (0.16 + fi * 0.03);
  float rad = 0.5 + 0.16 * s2;
  vec2 cen = vec2(cos(ang), sin(ang)) * rad;
  vec2 q = st - cen;
  float n1 = fbm(vec3(q * 6.0, t * 0.6 + fi * 2.0));
  vec2 warp = vec2(n1, n1 * 0.6 + 0.1) * 0.12;
  float fd = length(q + warp);
  float e = (smoothstep(0.095, 0.0, fd) * 0.9 + exp(-fd * 8.5) * 0.6) * life;
  vec3 aBlue = vec3(0.30, 0.55, 1.0);
  vec3 aPink = vec3(1.0, 0.50, 0.82);
  vec3 aGold = vec3(1.0, 0.82, 0.44);
  float m = fract(s1 * 0.6 + t * 0.04 + fi * 0.2);
  vec3 ec = m < 0.5 ? mix(aBlue, aPink, m * 2.0) : mix(aPink, aGold, (m - 0.5) * 2.0);
  float g = 0.66 + lv * 0.45;
  return vec4(ec * e * g, e * g);
}

void main() {
  vec2 stRaw = (v_uv - 0.5) * 2.0;
  vec2 st = stRaw * 1.45; // zoom so the fire sits within the rings
  float t = u_t, lv = u_lv;

  vec3 cWhite  = vec3(1.0, 0.97, 0.88);
  vec3 cGoldBr = vec3(1.0, 0.914, 0.659);
  vec3 cGold   = vec3(0.796, 0.643, 0.333);
  vec3 cEmber  = vec3(1.0, 0.541, 0.239);

  // ── The Guruji flame (the fiery heart) ──
  float n1 = fbm(vec3(st * 2.6, t * 0.16));
  float n2 = fbm(vec3(st * 3.0 + n1 * 0.5, t * 0.12 + 4.0));
  float n3 = fbm(vec3(st * 6.8 + n2 * 0.7, t * 0.38 + 9.0));
  vec2 warp = vec2(n1, n2 - 0.06) * (0.07 + lv * 0.13)
            + vec2(n3 * 0.5, n3) * (0.022 + lv * 0.03);
  vec2 fst = st * vec2(1.0, 0.9);
  float wd = length(fst + warp) * (1.0 + sin(t * 0.5) * (0.03 + lv * 0.03));
  float flicker = 0.9 + 0.1 * sin(t * 7.3 + n3 * 6.28) * (0.5 + 0.5 * sin(t * 2.1));
  float coreR = 0.055 + lv * 0.04;
  float core = smoothstep(coreR, coreR * 0.08, wd) * flicker;
  float corona = smoothstep(coreR * 2.8, coreR * 0.55, wd) * 0.5 * flicker;
  float inR = 0.2 + lv * 0.06;
  float inner = smoothstep(inR + 0.12, inR * 0.25, wd) * 0.62 * (0.9 + 0.22 * n3);
  float outR = 0.4 + lv * 0.12;
  float outer = smoothstep(outR + 0.25, outR * 0.12, wd) * 0.3 * (0.85 + 0.3 * n3);
  float bloom = smoothstep(0.85, 0.05, wd) * 0.09;
  vec3 fcol = core * cWhite
    + corona * mix(cWhite, cGoldBr, 0.5)
    + inner * mix(cGoldBr, cEmber, 0.35 + n1 * 0.2)
    + outer * mix(cEmber, cGold, 0.30 + n2 * 0.25)
    + bloom * cGold;
  fcol = clamp(fcol, 0.0, 1.0);
  float fa = clamp(core + corona * 0.8 + inner + outer * 0.7 + bloom, 0.0, 1.0);

  vec3 outRGB = fcol * fa; // premultiplied flame
  float outA = fa;

  // ── The Shakti aura — orbiting flame-energy wisps wrapping the fire ──
  for (int i = 0; i < 5; i++) {
    vec4 w = auraWisp(stRaw, t, lv, float(i));
    outRGB += w.rgb;
    outA += w.a;
  }

  outRGB = clamp(outRGB, 0.0, 1.0);
  outA = clamp(outA, 0.0, 1.0);
  o = vec4(outRGB, outA);
}`;

function compile(gl: WebGL2RenderingContext, type: number, src: string) {
  const s = gl.createShader(type);
  if (!s) return null;
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
    gl.deleteShader(s);
    return null;
  }
  return s;
}

export function ConcentricBindu({
  size = 44,
  className = "",
  alive = false,
  ariaLabel = "PuranGPT",
}: {
  size?: number;
  className?: string;
  /** When true (AI generating), the flame leaps higher and the field pulses. */
  alive?: boolean;
  ariaLabel?: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const ringRefs = useRef<(SVGCircleElement | null)[]>([]);
  const haloRef = useRef<SVGCircleElement>(null);
  const aliveRef = useRef(alive);
  const [webglFailed, setWebglFailed] = useState(false);

  useEffect(() => {
    aliveRef.current = alive;
  }, [alive]);

  // ── The living flame (WebGL2) ──
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const reduced =
      typeof window !== "undefined" &&
      !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    const gl = canvas.getContext("webgl2", {
      alpha: true,
      premultipliedAlpha: true,
      antialias: true,
      depth: false,
      stencil: false,
      powerPreference: "low-power",
    });
    if (!gl) {
      setWebglFailed(true);
      return;
    }
    const vs = compile(gl, gl.VERTEX_SHADER, VS_SRC);
    const fs = compile(gl, gl.FRAGMENT_SHADER, FS_SRC);
    if (!vs || !fs) {
      setWebglFailed(true);
      return;
    }
    const prog = gl.createProgram()!;
    gl.attachShader(prog, vs);
    gl.attachShader(prog, fs);
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
      setWebglFailed(true);
      return;
    }
    gl.useProgram(prog);

    const buf = gl.createBuffer()!;
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]), gl.STATIC_DRAW);
    const vao = gl.createVertexArray()!;
    gl.bindVertexArray(vao);
    const aPos = gl.getAttribLocation(prog, "a_pos");
    gl.enableVertexAttribArray(aPos);
    gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);
    gl.bindVertexArray(null);

    const uT = gl.getUniformLocation(prog, "u_t");
    const uLv = gl.getUniformLocation(prog, "u_lv");

    let raf = 0;
    let level = 0;
    const t0 = performance.now();

    const draw = (now: number) => {
      const t = reduced ? 6.0 : (now - t0) * 0.001;
      const target = aliveRef.current ? 1 : 0;
      level = reduced ? target : level + (target - level) * 0.05;

      // Cap the device-pixel buffer — these marks are small and may be many.
      const dpr = Math.min(2, typeof devicePixelRatio === "number" ? devicePixelRatio : 1);
      const w = Math.max(1, Math.round(canvas.clientWidth * dpr));
      const h = Math.max(1, Math.round(canvas.clientHeight * dpr));
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

      if (!reduced) raf = requestAnimationFrame(draw);
    };
    if (reduced) draw(t0 + 6000);
    else raf = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(raf);
      gl.deleteProgram(prog);
      gl.deleteShader(vs);
      gl.deleteShader(fs);
      gl.deleteBuffer(buf);
      gl.deleteVertexArray(vao);
      gl.getExtension("WEBGL_lose_context")?.loseContext();
    };
  }, []);

  // ── The gravitational rings + halo (SVG ripple) ──
  useEffect(() => {
    const reduced =
      typeof window !== "undefined" &&
      !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    let raf = 0;
    let level = 0;
    const t0 = performance.now();

    const frame = (now: number) => {
      const t = (now - t0) * 0.001;
      level += ((aliveRef.current ? 1 : 0) - level) * 0.05;
      const wave = 0.9 + level * 1.6;
      ringRefs.current.forEach((ring, i) => {
        if (!ring) return;
        const r = RING_BASE[i] + Math.sin(t * 1.05 - i * 0.8) * wave;
        ring.setAttribute("r", r.toFixed(2));
        ring.setAttribute(
          "opacity",
          ((0.46 - i * 0.07) * (0.78 + 0.22 * Math.sin(t * 1.05 - i * 0.8))).toFixed(3),
        );
      });
      haloRef.current?.setAttribute("opacity", (0.2 + level * 0.22 + 0.05 * Math.sin(t * 1.5)).toFixed(3));
      if (!reduced) raf = requestAnimationFrame(frame);
    };
    if (reduced) frame(t0 + 6200);
    else raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <span
      className={className}
      style={{ position: "relative", display: "inline-block", width: size, height: size }}
      role="img"
      aria-label={ariaLabel}
    >
      {/* The living fire (WebGL) — behind the rings, glowing through the centre */}
      {!webglFailed && (
        <canvas
          ref={canvasRef}
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}
        />
      )}

      {/* The gravitational field — crisp SVG rings + halo, transparent centre */}
      <svg
        viewBox="0 0 100 100"
        width={size}
        height={size}
        style={{ position: "relative", display: "block", overflow: "visible" }}
        aria-hidden="true"
      >
        <defs>
          <radialGradient id="cb-halo">
            <stop offset="0%" stopColor="#a78bfa" stopOpacity="0.32" />
            <stop offset="60%" stopColor="#a78bfa" stopOpacity="0.08" />
            <stop offset="100%" stopColor="#a78bfa" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="cb-fb" x1="50" y1="66" x2="50" y2="30" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#fff4d6" />
            <stop offset="40%" stopColor="#a5b4fc" />
            <stop offset="100%" stopColor="#a78bfa" />
          </linearGradient>
        </defs>

        {/* Soft halo, behind the rings */}
        <circle ref={haloRef} cx={C} cy={C} r={47} fill="url(#cb-halo)" opacity={0.22} />

        {/* Fallback flame (only when WebGL2 is unavailable) — a still gold tongue */}
        {webglFailed && (
          <path
            d="M 50 64 C 43 64 41 56 41 51 C 41 44 47 40 50 32 C 53 40 59 44 59 51 C 59 56 57 64 50 64 Z"
            fill="url(#cb-fb)"
            fillOpacity={0.9}
            stroke="#8b5cf6"
            strokeWidth={0.6}
            strokeOpacity={0.5}
          />
        )}

        {/* Concentric gravitational rings, rippling outward */}
        {RING_BASE.map((r, i) => (
          <circle
            key={i}
            ref={(el) => {
              ringRefs.current[i] = el;
            }}
            cx={C}
            cy={C}
            r={r}
            fill="none"
            stroke={i === RING_BASE.length - 1 ? "#7e92b8" : "#a78bfa"}
            strokeWidth={i === 0 ? 1.4 : 1}
            opacity={0.4}
          />
        ))}
      </svg>
    </span>
  );
}
