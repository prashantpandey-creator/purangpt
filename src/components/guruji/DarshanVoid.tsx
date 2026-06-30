"use client";

import { useEffect, useRef } from "react";
import type { BinduState } from "./GurujiBindu";

// ─── Reactive living void ───────────────────────────────────────────────
//
// A full-field WebGL2 background for Voice Darshan: a deep, domain-warped aurora
// of indigo / violet / ember over true OLED black, with a fine drifting starfield.
// It is NOT a static backdrop — it reacts to the moment: as Guruji thinks the
// field leans inward and brightens (u_lv); as he speaks it warms toward gold and
// ignites faint god-rays from the heart (u_warm). The orb's glow dissolves into
// it with no edge, so the bindu, the void, and the words read as one atmosphere.

const VS_SRC = /*glsl*/ `#version 300 es
in vec2 a_pos;
out vec2 v_uv;
void main() {
  v_uv = a_pos * 0.5 + 0.5;
  gl_Position = vec4(a_pos, 0.0, 1.0);
}`;

const FS_SRC = /*glsl*/ `#version 300 es
precision highp float;
in vec2 v_uv; out vec4 o;
uniform float u_t; uniform vec2 u_res; uniform float u_lv; uniform float u_warm;
float h2(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vn(vec2 p){
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(h2(i), h2(i + vec2(1.0, 0.0)), u.x),
             mix(h2(i + vec2(0.0, 1.0)), h2(i + vec2(1.0, 1.0)), u.x), u.y);
}
float fbm(vec2 p){ float s = 0.0, a = 0.5; for (int i = 0; i < 5; i++){ s += a * vn(p); p *= 2.02; a *= 0.5; } return s; }
void main(){
  vec2 uv = v_uv; vec2 c = uv - 0.5; c.x *= u_res.x / u_res.y;
  float r = length(c); float ang = atan(c.y, c.x);
  vec3 base = vec3(0.009, 0.008, 0.016);
  vec2 q = c * 2.2;
  float warp = fbm(q * 1.3 + vec2(u_t * 0.03, u_t * 0.02));
  float aNear = pow(fbm(q + vec2(warp * 1.2 - u_t * 0.02, warp * 0.8 + u_t * 0.015)), 1.7);
  float aFar = pow(fbm(q * 0.55 + vec2(u_t * 0.008, -u_t * 0.011) + warp * 0.4), 2.0);
  float aur = aNear * 0.72 + aFar * 0.55;
  vec3 violet = vec3(0.17, 0.10, 0.32);
  vec3 indigo = vec3(0.06, 0.11, 0.27);
  vec3 ember = vec3(0.28, 0.12, 0.07);
  vec3 hue = mix(indigo, violet, 0.5 + 0.5 * sin(u_t * 0.05 + c.x * 1.5));
  hue = mix(hue, ember, 0.38 * (0.5 + 0.5 * sin(u_t * 0.04 + c.y * 1.2)));
  hue = mix(hue, vec3(0.46, 0.28, 0.10), u_warm * 0.6);
  float field = aur * (0.10 + 0.13 * u_lv);
  vec3 col = base + hue * field;
  float halo = exp(-r * (2.8 - 1.1 * u_lv)) * (0.04 + 0.16 * u_lv);
  col += vec3(0.32, 0.21, 0.08) * halo;
  float rays = (0.5 + 0.5 * sin(ang * 14.0 + u_t * 0.12)) * (0.5 + 0.5 * sin(ang * 5.0 - u_t * 0.07)) * exp(-r * 1.7) * u_warm * 0.16;
  col += vec3(0.5, 0.34, 0.12) * rays;
  float shim = (0.5 + 0.5 * sin(r * 24.0 - u_t * 0.35)) * smoothstep(0.25, 0.85, r) * 0.022 * (0.4 + 0.6 * u_lv);
  col += mix(vec3(0.16, 0.12, 0.26), vec3(0.30, 0.22, 0.10), u_warm) * shim;
  vec2 mg = uv * u_res * 0.6; mg.y += u_t * 6.0; float sd = h2(floor(mg));
  float tw = step(0.9986, sd) * (0.5 + 0.5 * sin(u_t * 1.6 + sd * 80.0));
  col += vec3(0.85, 0.8, 0.62) * tw * 0.5;
  col *= mix(0.38, 1.0, smoothstep(1.18, 0.10, r));
  o = vec4(col, 1.0);
}`;

function compile(gl: WebGL2RenderingContext, type: number, src: string) {
  const s = gl.createShader(type);
  if (!s) return null;
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
    if (process.env.NODE_ENV !== "production") console.warn("DarshanVoid shader:", gl.getShaderInfoLog(s));
    gl.deleteShader(s);
    return null;
  }
  return s;
}

export function DarshanVoid({ phase, className }: { phase: BinduState; className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const phaseRef = useRef<BinduState>(phase);
  useEffect(() => { phaseRef.current = phase; }, [phase]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const reduced =
      typeof window !== "undefined" &&
      !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    const gl = canvas.getContext("webgl2", {
      alpha: false, antialias: false, depth: false, stencil: false, powerPreference: "low-power",
    });
    if (!gl) return;

    const vs = compile(gl, gl.VERTEX_SHADER, VS_SRC);
    const fs = compile(gl, gl.FRAGMENT_SHADER, FS_SRC);
    if (!vs || !fs) return;
    const prog = gl.createProgram();
    if (!prog) return;
    gl.attachShader(prog, vs); gl.attachShader(prog, fs); gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
      if (process.env.NODE_ENV !== "production") console.warn("DarshanVoid link:", gl.getProgramInfoLog(prog));
      return;
    }

    const uT = gl.getUniformLocation(prog, "u_t");
    const uRes = gl.getUniformLocation(prog, "u_res");
    const uLv = gl.getUniformLocation(prog, "u_lv");
    const uWarm = gl.getUniformLocation(prog, "u_warm");

    const buf = gl.createBuffer()!;
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]), gl.STATIC_DRAW);
    const vao = gl.createVertexArray()!;
    gl.bindVertexArray(vao);
    const aPos = gl.getAttribLocation(prog, "a_pos");
    gl.enableVertexAttribArray(aPos);
    gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);
    gl.bindVertexArray(null);

    let level = 0, warm = 0, raf = 0;
    const t0 = performance.now();
    // Cap the void's backing-store scale: it covers the whole screen, so high DPR
    // over a 10-octave field is the one real perf trap on phones.
    const renderScale = Math.min(typeof devicePixelRatio === "number" ? devicePixelRatio : 1, 1.25);

    const loop = () => {
      const t = reduced ? 5.5 : (performance.now() - t0) * 0.001;
      const st = phaseRef.current;
      const lvTarget = st === "thinking" || st === "manifesting" ? 1.0 : st === "listening" ? 0.5 : 0.0;
      const warmTarget = st === "manifesting" ? 1.0 : 0.0;
      level = reduced ? lvTarget : level + (lvTarget - level) * 0.05;
      warm = reduced ? warmTarget : warm + (warmTarget - warm) * 0.04;

      const w = Math.round(canvas.clientWidth * renderScale);
      const h = Math.round(canvas.clientHeight * renderScale);
      if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
      gl.viewport(0, 0, w, h);
      gl.useProgram(prog);
      gl.bindVertexArray(vao);
      gl.uniform1f(uT, t);
      gl.uniform2f(uRes, w, h);
      gl.uniform1f(uLv, level);
      gl.uniform1f(uWarm, warm);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(raf);
      gl.deleteProgram(prog); gl.deleteShader(vs); gl.deleteShader(fs);
      gl.deleteBuffer(buf); gl.deleteVertexArray(vao);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className={className}
      aria-hidden="true"
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%", display: "block" }}
    />
  );
}
