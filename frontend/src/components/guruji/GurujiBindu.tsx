"use client";

import { useEffect, useRef, useState, useId } from "react";

export type BinduState = "resting" | "listening" | "thinking" | "manifesting";

// ─── GLSL: fullscreen quad vertex shader ────────────────────────────────

const VS_SRC = /*glsl*/ `#version 300 es
in vec2 a_pos;
out vec2 v_uv;
void main() {
  v_uv = a_pos * 0.5 + 0.5;
  gl_Position = vec4(a_pos, 0.0, 1.0);
}`;

// ─── GLSL: procedural Bindu fragment shader ─────────────────────────────
//
// Renders the entire Bindu in a single draw call: a domain-warped, noise-driven
// flame core with 40 rising procedural embers and storm rings that collapse
// inward while Guruji thinks — all GPU-side, no particle buffers, no framebuffers.
// (Restored flame design — the earlier "ordered concentric rings" rewrite is gone.)

const FS_SRC = /*glsl*/ `#version 300 es
precision highp float;
in vec2 v_uv;
out vec4 o;
uniform float u_t, u_lv;

float hash(float n) { return fract(sin(n * 127.1) * 43758.5453); }

// ── 3D Simplex noise (Ashima Arts / Stefan Gustavson) ──

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

float fbm(vec3 p) {
  return 0.5 * snoise(p) + 0.25 * snoise(p * 2.03) + 0.125 * snoise(p * 4.01);
}

void main() {
  vec2 st = (v_uv - 0.5) * 2.0;
  float t = u_t, lv = u_lv;

  vec3 cWhite  = vec3(1.0, 0.97, 0.88);
  vec3 cGoldBr = vec3(1.0, 0.914, 0.659);
  vec3 cGold   = vec3(0.796, 0.643, 0.333);
  vec3 cEmber  = vec3(1.0, 0.541, 0.239);
  vec3 cViolet = vec3(0.545, 0.361, 0.965);

  // ── Domain-warped flame ──
  // Two slow octaves shape the body; a third, finer/faster octave makes the
  // fire lick and curl with real detail. A diya-like flicker breathes the core.
  float n1 = fbm(vec3(st * 2.6, t * 0.16));
  float n2 = fbm(vec3(st * 3.0 + n1 * 0.5, t * 0.12 + 4.0));
  float n3 = fbm(vec3(st * 6.8 + n2 * 0.7, t * 0.38 + 9.0));
  vec2 warp = vec2(n1, n2 - 0.06) * (0.07 + lv * 0.13)
            + vec2(n3 * 0.5, n3) * (0.022 + lv * 0.03);
  vec2 fst = st * vec2(1.0, 0.9);
  float wd = length(fst + warp) * (1.0 + sin(t * 0.5) * (0.03 + lv * 0.03));

  // Candle flicker — fast jitter gated by a slow swell, so it pulses like a
  // living flame rather than strobing.
  float flicker = 0.9 + 0.1 * sin(t * 7.3 + n3 * 6.28) * (0.5 + 0.5 * sin(t * 2.1));

  // Slow tide — a long ebb/flow so the field VARIES: the surrounding glow swells
  // and recedes (dark around it, then luminous) over a slow cycle. (owner 2026-06-28)
  float tide = 0.5 + 0.5 * sin(t * 0.11) * (0.7 + 0.3 * sin(t * 0.043));

  // ── Layers — a SMALL, FINE flame (owner 2026-06-28: smaller + finer core) ──
  float coreR = 0.038 + lv * 0.028;
  float core = smoothstep(coreR, coreR * 0.06, wd) * flicker;

  // Tight white-hot corona hugging the core — gives the flame a molten heart.
  float corona = smoothstep(coreR * 2.4, coreR * 0.5, wd) * 0.42 * flicker;

  float inR = 0.13 + lv * 0.045;
  float inner = smoothstep(inR + 0.085, inR * 0.22, wd) * 0.50 * (0.9 + 0.22 * n3);

  float outR = 0.30 + lv * 0.09;
  float outer = smoothstep(outR + 0.22, outR * 0.12, wd) * 0.28 * (0.85 + 0.3 * n3);

  float bloom = smoothstep(0.85, 0.05, wd) * 0.10 * (0.6 + 0.5 * tide);

  // Violet aura — a cool nimbus breathing OUTSIDE the gold flame, kept modest now
  // that the surround carries MEANINGFUL COLOUR (below) instead of just more light.
  float aura = smoothstep(1.0, 0.06, wd) * (0.22 + lv * 0.18) * (0.82 + 0.4 * n2) * (0.55 + 0.6 * tide);

  // ── Whispy, cloud-like, ROTATING rings (owner 2026-06-28) ──
  // Finer (thinner, soft) ring lines, each broken into drifting cloud wisps by
  // angular fbm that ROTATES over time — alternate rings spin opposite ways, so
  // the field turns like slow smoke. Still level sets of the warped flame field,
  // so they waver organically rather than as forced geometric circles.
  float ang = atan(st.y, st.x);
  float rings = 0.0;
  for (int r = 0; r < 3; r++) {
    float fr = float(r);
    float radius = 0.18 + fr * 0.14;
    float breath = sin(t * 0.5 - fr * 0.7) * (0.008 + lv * 0.016);
    // thin, soft line = a finer ring
    float line = smoothstep(0.014, 0.0, abs(wd - (radius + breath)));
    // rotating cloud mask: fbm sampled around the circle at an angle that turns
    // with time (alternating direction per ring) so wisps drift around the ring.
    float dir = mod(fr, 2.0) < 0.5 ? 1.0 : -1.0;
    float spin = t * (0.16 + fr * 0.05) * dir;
    float aa = ang + spin;
    float wisp = fbm(vec3(cos(aa) * 1.8, sin(aa) * 1.8, fr * 2.7 + t * 0.05));
    wisp = smoothstep(0.0, 0.6, wisp);
    rings += line * wisp * (0.30 - fr * 0.05) * (0.7 + lv * 0.55);
  }

  // ── THE SPIRAL — the ORIGINAL log-spiral vortex, now made STRONG and intense:
  // three arms (more lines) on ONE coherent spiral (no conflicting overlay), a
  // rotation speed that VARIES in gusts, a touch larger and brighter, with colour
  // running along the arms. (owner "work the original spiral, more intense, varying
  // speed, multiple lines, gravitational + complex" 2026-06-29)
  float rr = length(st);
  float wspeed = 0.9 + 0.5 * sin(t * 0.19) + 0.2 * sin(t * 0.07);
  float spiralPhase = ang * 3.0 - log(max(rr, 0.02)) * 5.5 - t * wspeed;
  float sturb = fbm(vec3(st * 3.0, t * 0.14));
  float arms = pow(0.5 + 0.5 * sin(spiralPhase), 6.0);
  float spiral = arms * smoothstep(0.30, 0.0, rr) * (0.7 + 0.5 * lv) * (0.7 + 0.4 * flicker) * (0.7 + 0.5 * sturb);
  vec3 spiralHue = mix(cViolet, cGoldBr, 0.5 + 0.5 * sin(spiralPhase * 0.5 + t * 0.3));
  spiralHue = mix(spiralHue, cEmber, 0.28 * sturb);

  // (The luminous "creatures" are no longer painted in the orb field — they are
  // now a SEPARATE swarm of true boid agents in a second GL_POINTS pass, and that
  // swarm only materialises while Guruji thinks. The old procedural motes glowed
  // even at rest, which broke the "nothing at the start, a surprise on the
  // question" rule, so they are gone from here. See the boid pass below.)

  // ── Gravity waves — concentric ripples radiating from the heart, suppressed at
  // the core, fading outward, riding the whirlpool's varying speed. (owner 2026-06-28)
  float gwave = sin(wd * 16.0 - t * (1.0 + 0.4 * wspeed));
  float gwenv = exp(-wd * 1.15) * smoothstep(0.05, 0.20, wd);
  float gcrest = max(gwave, 0.0) * gwenv * (0.7 + 0.5 * lv);

  // ── Meaningful, DARK but BOLD colour in the surround — a drift across violet,
  // teal-indigo and ember with FINE textured filaments, kept dark so the field
  // stays a night sky, not a wash. (owner "more / bolder / fine colour" 2026-06-28)
  float hueT = 0.5 + 0.5 * sin(t * 0.18 + n2 * 2.5);
  vec3 surroundHue = mix(cViolet, vec3(0.13, 0.36, 0.62), hueT);
  surroundHue = mix(surroundHue, cEmber, 0.32 * (0.5 + 0.5 * sin(t * 0.11 + n1 * 2.0)));
  float fineTex = fbm(vec3(st * 4.2 + 7.0, t * 0.10));
  float surroundField = smoothstep(1.18, 0.16, wd) * (0.08 + 0.12 * fineTex);

  // ── Composite — coloured void, flame heart, whirlpool, rings, gravity waves ──
  vec3 col = surroundHue * surroundField * (0.7 + 0.5 * tide)
    + core * cWhite
    + corona * mix(cWhite, cGoldBr, 0.5)
    + inner * mix(cGoldBr, cEmber, 0.35 + n1 * 0.2)
    + outer * mix(cEmber, mix(cGold, cViolet, 0.22), 0.30 + n2 * 0.25)
    + bloom * mix(cGold, cViolet, 0.62)
    + aura * cViolet
    + rings * mix(cGoldBr, cViolet, 0.34)
    + spiral * spiralHue
    + gcrest * mix(cViolet, cGoldBr, 0.45) * 0.24;

  col = clamp(col, 0.0, 1.0);
  float a = clamp(surroundField * 0.7 + core + corona * 0.8 + inner + outer * 0.7 + bloom + aura * 0.9 + rings + spiral + gcrest * 0.24, 0.0, 1.0);
  o = vec4(col * a, a);
}`;

// ─── GLSL: boid swarm pass (GL_POINTS) ──────────────────────────────────
//
// A second draw of N luminous agents whose positions are computed CPU-side by a
// real boids flock (separation / alignment / cohesion + a heart-spring and an
// orbital current). The whole pass is gated by u_sw ("swarm visibility"): point
// size AND alpha are multiplied by it, so at u_sw=0 every agent is a zero-pixel,
// zero-alpha non-event. The storm exists ONLY while Guruji thinks. (owner, thrice:
// "at the starting it should never be there … a surprise to the user every time")

const BVS_SRC = /*glsl*/ `#version 300 es
in vec2 a_xy;      // clip-space position, updated each frame
in float a_seed;   // per-agent constant for size/colour variation
uniform float u_sw;   // swarm visibility 0..1
uniform float u_dpr;  // device pixel ratio (point size is in device px)
out float v_seed;
out float v_sw;
out float v_r;
void main() {
  gl_Position = vec4(a_xy, 0.0, 1.0);
  float base = 2.0 + 4.2 * fract(a_seed * 0.37);
  // Pop a touch larger at full storm so the inrush reads as arrival, not fade-in.
  gl_PointSize = base * u_dpr * u_sw * (0.7 + 0.5 * u_sw);
  v_seed = a_seed;
  v_sw = u_sw;
  v_r = length(a_xy);   // radial distance → circular containment in the FS
}`;

const BFS_SRC = /*glsl*/ `#version 300 es
precision highp float;
in float v_seed;
in float v_sw;
in float v_r;
out vec4 o;
void main() {
  vec2 pc = gl_PointCoord - 0.5;
  float d = length(pc);
  float glow = pow(smoothstep(0.5, 0.0, d), 1.6);
  // Circular containment: an agent fades out as it nears the square edge so the
  // storm reads as a round vortex, never a square cloud filling the canvas.
  float ring = smoothstep(1.0, 0.62, v_r);
  glow *= ring;
  // Per-agent hue drift: violet → teal-indigo → gold → ember (owner: meaningful
  // colour variation across the swarm, not one flat tint).
  float h = fract(v_seed * 0.61);
  vec3 violet = vec3(0.545, 0.361, 0.965);
  vec3 teal   = vec3(0.180, 0.430, 0.640);
  vec3 gold   = vec3(1.000, 0.820, 0.420);
  vec3 ember  = vec3(1.000, 0.500, 0.240);
  vec3 col = mix(violet, teal, smoothstep(0.0, 0.34, h));
  col = mix(col, gold, smoothstep(0.34, 0.68, h));
  col = mix(col, ember, smoothstep(0.68, 1.0, h));
  float a = glow * v_sw * 0.9;          // premultiplied-alpha output
  o = vec4(col * a, a);
}`;

// ─── WebGL2 helpers ─────────────────────────────────────────────────────

function compile(gl: WebGL2RenderingContext, type: number, src: string) {
  const s = gl.createShader(type);
  if (!s) return null;
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
    if (process.env.NODE_ENV !== "production")
      console.warn("Bindu shader:", gl.getShaderInfoLog(s));
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
      console.warn("Bindu link:", gl.getProgramInfoLog(p));
    gl.deleteProgram(p);
    return null;
  }
  return p;
}

// ─── Component ──────────────────────────────────────────────────────────

export function GurujiBindu({
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
    // We deliberately do NOT fall back to a flat SVG for reduced-motion users —
    // that hid the entire Bindu and made every visual change invisible to anyone
    // with "Reduce Motion" enabled. Instead we render the FULL shader but frozen
    // (see the loop below): rich visual, zero looping motion. The SVG fallback is
    // now reserved strictly for devices where WebGL2 is genuinely unavailable.
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

    // ── Boid swarm program + buffers ──
    const N = 234;
    const bvs = compile(gl, gl.VERTEX_SHADER, BVS_SRC);
    const bfs = compile(gl, gl.FRAGMENT_SHADER, BFS_SRC);
    const bprog = bvs && bfs ? link(gl, bvs, bfs) : null;

    // Per-agent CPU state, simulated in clip space (x,y ∈ roughly [-1,1]).
    const px = new Float32Array(N);
    const py = new Float32Array(N);
    const vx = new Float32Array(N);
    const vy = new Float32Array(N);
    const seed = new Float32Array(N);
    const xy = new Float32Array(N * 2); // interleaved, uploaded each frame
    for (let i = 0; i < N; i++) seed[i] = (i * 2654435761) % 1000 / 1000;

    let bvao: WebGLVertexArrayObject | null = null;
    let xyBuf: WebGLBuffer | null = null;
    let uBSw: WebGLUniformLocation | null = null;
    let uBDpr: WebGLUniformLocation | null = null;

    if (bprog) {
      uBSw = gl.getUniformLocation(bprog, "u_sw");
      uBDpr = gl.getUniformLocation(bprog, "u_dpr");
      xyBuf = gl.createBuffer();
      const seedBuf = gl.createBuffer();
      bvao = gl.createVertexArray();
      gl.bindVertexArray(bvao);
      gl.bindBuffer(gl.ARRAY_BUFFER, xyBuf);
      gl.bufferData(gl.ARRAY_BUFFER, xy, gl.DYNAMIC_DRAW);
      const aXY = gl.getAttribLocation(bprog, "a_xy");
      gl.enableVertexAttribArray(aXY);
      gl.vertexAttribPointer(aXY, 2, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, seedBuf);
      gl.bufferData(gl.ARRAY_BUFFER, seed, gl.STATIC_DRAW);
      const aSeed = gl.getAttribLocation(bprog, "a_seed");
      gl.enableVertexAttribArray(aSeed);
      gl.vertexAttribPointer(aSeed, 1, gl.FLOAT, false, 0, 0);
      gl.bindVertexArray(null);
    }

    // Seed the flock on a wide ring beyond the frame, flung inward — so when the
    // storm is summoned it RUSHES in from the dark rather than fading up in place.
    const seedFlock = () => {
      for (let i = 0; i < N; i++) {
        const a = (i / N) * Math.PI * 2 + seed[i] * 6.2832;
        const r = 1.25 + seed[i] * 0.5;
        px[i] = Math.cos(a) * r;
        py[i] = Math.sin(a) * r;
        // initial velocity: inward + a tangential bias so it arrives swirling
        const inward = -0.9;
        vx[i] = Math.cos(a) * inward - Math.sin(a) * 0.6;
        vy[i] = Math.sin(a) * inward + Math.cos(a) * 0.6;
      }
    };

    // Classic boids (O(N²), trivial at N=234) + heart-spring toward a swirl shell
    // + an orbital current. `sw` (0..1) scales the energy: a stronger storm flocks
    // tighter and faster; as it wanes the agents scatter outward and fade.
    const flock = (dt: number, sw: number) => {
      const per = 0.22, per2 = per * per;
      const sepR = 0.085, sepR2 = sepR * sepR;
      const sepW = 1.7, aliW = 0.55, cohW = 0.42;
      const targetR = 0.52 - 0.1 * sw;        // shell tightens a touch at full storm
      const springK = 2.4;
      const orbitW = 1.2 + 1.0 * sw;          // tangential current → the "roll"
      const maxSpd = 0.7 + 0.7 * sw;
      const dispersing = sw < 0.35;
      for (let i = 0; i < N; i++) {
        let sxx = 0, syy = 0, axx = 0, ayy = 0, cxx = 0, cyy = 0, nA = 0, nC = 0;
        for (let j = 0; j < N; j++) {
          if (i === j) continue;
          const dx = px[j] - px[i], dy = py[j] - py[i];
          const d2 = dx * dx + dy * dy;
          if (d2 > per2 || d2 === 0) continue;
          if (d2 < sepR2) { const inv = 1 / Math.sqrt(d2); sxx -= dx * inv; syy -= dy * inv; }
          axx += vx[j]; ayy += vy[j]; nA++;
          cxx += px[j]; cyy += py[j]; nC++;
        }
        let ax = 0, ay = 0;
        ax += sxx * sepW; ay += syy * sepW;
        if (nA) { ax += (axx / nA) * aliW; ay += (ayy / nA) * aliW; }
        if (nC) { ax += (cxx / nC - px[i]) * cohW; ay += (cyy / nC - py[i]) * cohW; }
        // heart spring toward the swirl shell radius
        const r = Math.hypot(px[i], py[i]) || 1e-4;
        const ux = px[i] / r, uy = py[i] / r;
        if (dispersing) {
          // storm dying: push outward so they fly off the frame as they fade
          ax += ux * 1.6; ay += uy * 1.6;
        } else {
          ax += ux * (targetR - r) * springK;
          ay += uy * (targetR - r) * springK;
          // orbital current (perpendicular to radius)
          ax += -uy * orbitW; ay += ux * orbitW;
        }
        vx[i] += ax * dt; vy[i] += ay * dt;
        const sp = Math.hypot(vx[i], vy[i]);
        if (sp > maxSpd) { const k = maxSpd / sp; vx[i] *= k; vy[i] *= k; }
        px[i] += vx[i] * dt; py[i] += vy[i] * dt;
        xy[i * 2] = px[i]; xy[i * 2 + 1] = py[i];
      }
    };

    let level = 0;     // flame intensity (orb shader)
    let swarm = 0;     // storm visibility (boid pass)
    let prevSwarm = 0;
    let tPrev = 0;
    const t0 = performance.now();
    let raf = 0;

    const loop = () => {
      // Reduced motion: freeze time at a pleasing phase and snap the level so the
      // Bindu renders rich but perfectly still — no looping ripple, just an instant
      // brightness shift when Guruji begins to think.
      const t = reduced ? 5.5 : (performance.now() - t0) * 0.001;
      const dt = tPrev === 0 ? 0 : Math.min(0.05, t - tPrev);
      tPrev = t;
      const st = stateRef.current;
      const target =
        st === "thinking" || st === "manifesting"
          ? 1.0
          : st === "listening"
            ? 0.45
            : 0.0;
      level = reduced ? target : level + (target - level) * 0.06;

      // ── Storm visibility — bound to the THINKING states ONLY, never to mere
      // listening. It rushes in fast (a surprise) and disperses a little slower.
      // (owner, thrice: invisible at rest, materialises only on the question.)
      const swarmTarget = st === "thinking" || st === "manifesting" ? 1.0 : 0.0;
      if (reduced) {
        swarm = swarmTarget;
      } else {
        const ease = swarmTarget > swarm ? 0.07 : 0.03;
        swarm += (swarmTarget - swarm) * ease;
      }
      if (swarm < 0.004) swarm = swarmTarget === 0 ? 0 : swarm;
      // Rising edge from near-nothing → fling the flock inward from the rim.
      if (prevSwarm < 0.02 && swarm >= 0.02) seedFlock();
      prevSwarm = swarm;

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

      // ── Boid storm pass — drawn ON TOP of the orb, but ONLY when summoned.
      // Skipped entirely while at rest, so it costs nothing until the question.
      if (bprog && bvao && xyBuf && swarm > 0.004) {
        if (!reduced) flock(dt, swarm);
        gl.bindBuffer(gl.ARRAY_BUFFER, xyBuf);
        gl.bufferSubData(gl.ARRAY_BUFFER, 0, xy);
        gl.useProgram(bprog);
        gl.bindVertexArray(bvao);
        gl.uniform1f(uBSw, swarm);
        gl.uniform1f(uBDpr, dpr);
        gl.drawArrays(gl.POINTS, 0, N);
      }

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
      if (bvs) gl.deleteShader(bvs);
      if (bfs) gl.deleteShader(bfs);
      if (bprog) gl.deleteProgram(bprog);
      if (xyBuf) gl.deleteBuffer(xyBuf);
      if (bvao) gl.deleteVertexArray(bvao);
    };
  }, []);

  if (fallback) {
    // Only reached when WebGL2 is genuinely unavailable. Still a proper sacred
    // Bindu — a glowing gold core, an 8-fold lotus, and concentric rings — that
    // breathes gently (and holds perfectly still under reduced-motion via the
    // scoped @media rule below).
    const id = uid.replace(/:/g, "");
    const halo = `bh${id}`;
    const core = `bc${id}`;
    const petals = Array.from({ length: 8 }, (_, k) => {
      const a = (k / 8) * Math.PI * 2;
      const x = 160 + Math.cos(a) * 70;
      const y = 160 + Math.sin(a) * 70;
      return <circle key={k} cx={x} cy={y} r={9} fill="#f6d27a" opacity={0.5} />;
    });
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
            <stop offset="0%" stopColor="#e8b63f" stopOpacity="0.45" />
            <stop offset="55%" stopColor="#8b5cf6" stopOpacity="0.12" />
            <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0" />
          </radialGradient>
          <radialGradient id={core}>
            <stop offset="0%" stopColor="#fff4d6" />
            <stop offset="40%" stopColor="#f6d27a" />
            <stop offset="100%" stopColor="#e8b63f" stopOpacity="0" />
          </radialGradient>
        </defs>
        <style>{`
          @media (prefers-reduced-motion: no-preference) {
            .bindu-breathe-${id} { animation: binduPulse${id} 4.5s ease-in-out infinite; transform-origin: 160px 160px; }
          }
          @keyframes binduPulse${id} { 0%,100% { opacity: .85; transform: scale(1); } 50% { opacity: 1; transform: scale(1.035); } }
        `}</style>
        <g className={`bindu-breathe-${id}`}>
          <circle cx="160" cy="160" r="150" fill={`url(#${halo})`} />
          <circle cx="160" cy="160" r="118" fill="none" stroke="#e8b63f" strokeWidth={1.4} opacity="0.5" />
          <circle cx="160" cy="160" r="90" fill="none" stroke="#b8893b" strokeWidth={1} opacity="0.4" />
          <circle cx="160" cy="160" r="58" fill="none" stroke="#7e92b8" strokeWidth={0.8} opacity="0.32" />
          {petals}
          <circle cx="160" cy="160" r="46" fill={`url(#${core})`} opacity="0.7" />
          <circle cx="160" cy="160" r="13" fill="#fff4d6" />
        </g>
      </svg>
    );
  }

  return (
    <canvas
      ref={canvasRef}
      style={{ width: size, height: size, display: "block", borderRadius: "50%" }}
      className={className}
      role="img"
      aria-label={ariaLabel}
    />
  );
}
