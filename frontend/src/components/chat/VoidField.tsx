"use client";

import { useEffect, useRef, useState } from "react";
import { getPulse } from "@/lib/binduPulse";

// ─────────────────────────────────────────────────────────────────────────
//  VoidField — a full-viewport living void behind the entire chat.
//
//  A deep indigo-aubergine field with slow dimensional fog, a few drifting
//  "concentrated voids" (gravity pools where the dark deepens), and a faint
//  warm breath near the top where the Bindu lives. Rendered in a single
//  fullscreen-quad fragment shader (one draw call), at capped/low resolution
//  because the field is low-frequency — cheap even inside the mobile WebView.
//
//  Falls back to a static CSS gradient when WebGL2 is unavailable, and renders
//  a single frozen frame (no rAF loop) under prefers-reduced-motion.
// ─────────────────────────────────────────────────────────────────────────

const VS_SRC = /*glsl*/ `#version 300 es
in vec2 a_pos;
out vec2 v_uv;
void main() {
  v_uv = a_pos * 0.5 + 0.5;
  gl_Position = vec4(a_pos, 0.0, 1.0);
}`;

const FS_SRC = /*glsl*/ `#version 300 es
precision highp float;
in vec2 v_uv;
out vec4 o;
uniform float u_t;
uniform float u_aspect;
uniform vec2 u_center;
uniform float u_intensity; // 0 resting → 1 thinking (shared intelligence signal)
uniform float u_breath;    // shared breathing phase, 0..1

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

float fbm(vec3 p) {
  return 0.5 * snoise(p) + 0.25 * snoise(p * 2.03) + 0.125 * snoise(p * 4.01);
}

// 4-octave fbm (plasma substrate) + IQ cosine rainbow palette — the two helpers
// the Living Void needs on top of the shared snoise/fbm substrate above.
float fbm4(vec3 p) { return fbm(p) + 0.0625 * snoise(p * 8.05); }
vec3 rainbow(float h) { return 0.5 + 0.5 * cos(6.28318 * (h + vec3(0.0, 0.33, 0.67))); }

// ── THE LIVING VOID ──────────────────────────────────────────────────────────
// A verbatim port of the owner-approved native composeOrb (Shaders.metal), made
// a FIELD not a disc: centred on the live #bindu-anchor, its turbulent rainbow
// plasma + invisible gravity pulse + deep black void + sharp bindu DISSOLVE
// outward into the deep void (no hard circle edge) so the whole screen is ONE
// continuous void — the orb is just where the field is brightest. u_intensity is
// the chat-activity signal (the native lv): it tears the void open + surfaces
// the bindu. (2026-06-28, replaces the cool gravitational-strain field.)
void main() {
  // Aspect-correct centred coordinates (origin at screen centre, +y up).
  vec2 p = (v_uv - 0.5);
  p.x *= u_aspect;
  float t = u_t;
  float lv = clamp(u_intensity, 0.0, 1.0);

  // OLED near-black field. Everything below is ADDED onto this; far from the
  // anchor the orb's light fades back to it, so text areas stay true-black.
  vec3 base = vec3(0.006, 0.005, 0.013);

  // Orb space, centred on the anchor. ORB_SCALE maps field distance into the
  // native composeOrb's -1..1 domain.
  const float ORB_SCALE = 2.15;
  vec2 st = (p - u_center) * ORB_SCALE;
  float r = length(st) + 1e-4;
  float fl = 0.7;

  // void openness: a slow irregular auto-cycle (opens SELDOM at idle), pushed
  // open by chat activity so the void tears + the bindu rises on answers.
  float cyc = sin(t * 0.15) + 0.55 * snoise(vec3(t * 0.04, 3.0, 0.0));
  float openness = clamp(smoothstep(0.30, 0.95, cyc) + lv * 0.7, 0.0, 1.0);

  // accretion pull toward the anchor as the void opens.
  vec2 pull = -(st / r) * openness * 0.16 * smoothstep(0.7, 0.1, r);

  // ── GRAVITY: a BREATHING radial distortion, NOT an outward march ──
  // The phase OSCILLATES (travel swings +/-) so the rings expand, ease to a stop
  // (sin velocity to 0 at the turns), contract and vibrate, then expand again —
  // meaningful restructuring of the field, never a one-way sonar ping. It
  // emanates from the anchor (just above the answer) and fades with distance, and
  // it RESPONDS to chat activity (lv): subtle at rest, restructuring strongly
  // while an answer streams. (owner 2026-06-28)
  float act = smoothstep(0.0, 1.0, lv);
  float travel = (1.2 + 2.6 * act) * sin(t * 0.12)
               + (0.25 + 0.7 * act) * sin(t * 0.44 + 1.0);
  float ring  = sin(r * 18.0 - travel);
  float gwenv = exp(-r * 1.15) * smoothstep(0.04, 0.18, r);
  float gamp  = 0.030 + 0.055 * act;                        // meaningful warp when active
  vec2 gdisp  = (st / r) * ring * gwenv * gamp;
  vec2 sp = st + pull + gdisp;

  // formless turbulence — fbm folded through itself twice, advecting in time.
  vec3 P  = vec3(sp * 0.9, t * 0.045 * fl);
  float a1 = fbm4(P);
  vec3 P2 = P + (1.1 + 0.7 * fl) * vec3(a1, fbm4(P + vec3(3.1, 1.2, 4.0)), 0.0)
              + vec3(0.0, 0.0, t * 0.020 * fl);
  float a2 = fbm4(P2 * 0.95);
  vec3 P3 = P2 + (0.9 + 0.5 * fl) * vec3(a2, fbm4(P2 + vec3(8.3, 2.8, 0.0)), 0.0);
  float f = fbm4(P3);
  float fil = clamp(1.0 - abs(f * 1.5), 0.0, 1.0); fil = pow(fil, 1.5);
  float dens = smoothstep(0.04, 0.72, a2);
  float energy = fil * dens;

  // full-rainbow plasma hue, drifting so it eventually visits every colour.
  vec3 plasmaHue = pow(rainbow(fract(t * 0.006 + a1 * 0.5)), vec3(0.8));

  // the void tearing open around the anchor (formless, opens with the cycle).
  float voidR = mix(0.05, 0.42, openness);
  float voidMask = smoothstep(voidR - 0.04, voidR + 0.14, r + 0.22 * f); // 1 out, 0 in
  float inside = 1.0 - voidMask;

  vec3 col = base;
  // plasma lives OUTSIDE the void.
  col += plasmaHue * energy * 1.15 * voidMask;
  float crest = max(ring, 0.0) * gwenv;
  col += plasmaHue * crest * (0.18 + energy) * (0.28 + 0.32 * act) * voidMask;

  // inside the void: near-black with rare EVER-TRANSFORMING neon threads.
  if (inside > 0.002) {
    vec2 iv = st / max(voidR, 0.06);
    float ir = length(iv);
    float zd = 0.5 / (ir * ir + 0.15);
    vec3 dp = vec3(iv * 1.8, zd * 0.4 - t * 0.07);
    float dneb  = fbm4(dp);
    float dneb2 = fbm4(dp * 2.3 + 5.0);
    vec3 neon = pow(rainbow(fract(t * 0.008 + dneb2 * 0.6 + zd * 0.08)), vec3(0.8));
    float tinge = smoothstep(0.60, 0.95, 0.5 + 0.5 * dneb);
    vec3 deep = neon * tinge * 0.11 * smoothstep(1.15, 0.1, ir);
    float glint = smoothstep(0.74, 0.90, fbm4(vec3(iv * 6.0, zd * 0.3 - t * 0.10)));
    deep += neon * glint * 0.22 * smoothstep(1.0, 0.3, ir);
    col += deep * inside;
  }

  // SMALL SHARP BINDU at the anchor's heart — a quiet needle in a dark pocket.
  float bp = (0.55 + 0.30 * sin(t * 0.30)) * (0.7 + 0.3 * openness);
  float pocket = 1.0 - 0.58 * exp(-pow(r / 0.035, 2.0));
  col *= pocket;
  float bcore = exp(-r * r * 11000.0);
  float bhalo = exp(-r * 72.0);
  float bang = atan(st.y, st.x);
  float bwavy = 1.0 + 0.45 * sin(bang * 8.0 - t * 1.0) * exp(-r * 60.0);
  float bindu = (bcore * 4.0 + bhalo * 0.13) * bwavy * bp;
  vec3 binduCol = mix(vec3(1.0, 0.99, 0.95), vec3(1.0, 0.82, 0.46), smoothstep(0.0, 0.04, r));
  col += binduCol * bindu;

  // FIELD falloff (NOT a disc): the orb's light dissolves into the deep void so
  // text areas settle to OLED black, but it reaches far — "one void", no edge.
  float fieldFade = exp(-r * 0.78);
  col = base + (col - base) * fieldFade;

  // gentle screen-edge vignette to true OLED black (keeps corners dark for text).
  float vig = 1.0 - smoothstep(0.25, 0.95, length(p));
  col *= mix(0.50, 1.0, vig);

  // tonemap — brighter midtones so the plasma patterns read; void stays deep.
  col = col / (col + vec3(0.68));
  col = max(col, vec3(0.0));
  o = vec4(col, 1.0);
}`;

function compile(gl: WebGL2RenderingContext, type: number, src: string) {
  const s = gl.createShader(type);
  if (!s) return null;
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
    if (process.env.NODE_ENV !== "production")
      console.warn("VoidField shader:", gl.getShaderInfoLog(s));
    gl.deleteShader(s);
    return null;
  }
  return s;
}

// Static fallback that always paints (behind the canvas, and the whole field
// when WebGL2 is unavailable) so the void never flashes to flat black.
const CSS_VOID =
  "radial-gradient(ellipse 95% 65% at 50% 30%, rgba(22,26,44,0.22), transparent 60%)," +
  "radial-gradient(circle at 50% 28%, rgba(48,36,16,0.22), transparent 38%)," +
  "radial-gradient(circle at 18% 82%, rgba(0,0,0,0.96), transparent 58%)," +
  "radial-gradient(circle at 82% 24%, rgba(0,0,0,0.94), transparent 58%)," +
  "#000000";

export function VoidField({ className = "" }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [webglFailed, setWebglFailed] = useState(false);

  useEffect(() => {
    const reduced =
      typeof window !== "undefined" &&
      !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const gl = canvas.getContext("webgl2", {
      alpha: false,
      antialias: false,
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
    gl.bindAttribLocation(prog, 0, "a_pos");
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
      setWebglFailed(true);
      return;
    }
    gl.useProgram(prog);

    const quad = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, quad);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 3, -1, -1, 3]),
      gl.STATIC_DRAW,
    );
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);

    const uT = gl.getUniformLocation(prog, "u_t");
    const uAspect = gl.getUniformLocation(prog, "u_aspect");
    const uCenter = gl.getUniformLocation(prog, "u_center");
    const uIntensity = gl.getUniformLocation(prog, "u_intensity");
    const uBreath = gl.getUniformLocation(prog, "u_breath");

    let anchorEl: HTMLElement | null = null;

    // The field is low-frequency, so cap the drawing buffer at CSS resolution
    // (DPR 1) — keeps the fragment count tiny on retina phones with no visible
    // softness.
    const resize = () => {
      const w = Math.max(1, Math.round(canvas.clientWidth));
      const h = Math.max(1, Math.round(canvas.clientHeight));
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
        gl.viewport(0, 0, w, h);
      }
      return w / h;
    };

    const t0 = performance.now();
    let raf = 0;
    let running = true;

    const draw = () => {
      const aspect = resize();
      const t = reduced ? 12.0 : (performance.now() - t0) * 0.001;
      gl.uniform1f(uT, t);
      gl.uniform1f(uAspect, aspect);

      if (!anchorEl) anchorEl = document.getElementById("bindu-anchor");
      if (anchorEl) {
        const rect = anchorEl.getBoundingClientRect();
        const sx = (rect.left + rect.width * 0.5) / canvas.clientWidth;
        const sy = (rect.top + rect.height * 0.5) / canvas.clientHeight;
        gl.uniform2f(uCenter, (sx - 0.5) * aspect, 0.5 - sy);
      } else {
        gl.uniform2f(uCenter, 0.0, 0.18);
      }

      // The shared intelligence signal — the same value that swells the hum.
      const pulse = getPulse();
      gl.uniform1f(uIntensity, pulse.intensity);
      gl.uniform1f(uBreath, pulse.breath);

      gl.drawArrays(gl.TRIANGLES, 0, 3);
      if (!reduced && running) raf = requestAnimationFrame(draw);
    };

    // Reduced motion: draw a single static frame and a couple of resize-safe
    // redraws; otherwise run the animation loop.
    if (reduced) {
      draw();
      const onResize = () => draw();
      window.addEventListener("resize", onResize);
      return () => {
        window.removeEventListener("resize", onResize);
        gl.getExtension("WEBGL_lose_context")?.loseContext();
      };
    }

    raf = requestAnimationFrame(draw);

    // Pause the loop when the tab is hidden — no point burning the GPU.
    const onVis = () => {
      if (document.hidden) {
        running = false;
        cancelAnimationFrame(raf);
      } else if (!running) {
        running = true;
        raf = requestAnimationFrame(draw);
      }
    };
    document.addEventListener("visibilitychange", onVis);

    return () => {
      running = false;
      cancelAnimationFrame(raf);
      document.removeEventListener("visibilitychange", onVis);
      gl.getExtension("WEBGL_lose_context")?.loseContext();
    };
  }, []);

  return (
    <div
      className={`pointer-events-none fixed inset-0 ${className}`}
      style={{ background: CSS_VOID, zIndex: 0 }}
      aria-hidden
    >
      {!webglFailed && (
        <canvas
          ref={canvasRef}
          className="h-full w-full"
          style={{ display: "block" }}
        />
      )}
    </div>
  );
}
