"use client";

/**
 * ThreeBackground — native Bindu "Living Void" orb, ported from
 * ios/App/App/Native/Bindu/Shaders.metal composeOrb().
 *
 * Single unified shader: turbulent rainbow plasma, deep black void at centre,
 * invisible gravity rings (displacement-only), rare neon threads in the void.
 * No starfield, no light rings, no separate orb — just the Living Void.
 */

import { useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";

// ── Port of the native Metal composeOrb to GLSL ──────────────────────────
// This is the EXACT same visual as the iOS native BinduMetalView.
// The noise substrate (snoise 3D, fbm) is the same Ashima/webgl-noise lineage.

const BINDU_VS = /* glsl */ `#version 300 es
in vec2 a_pos;
out vec2 v_uv;
void main() {
  v_uv = a_pos * 0.5 + 0.5;
  gl_Position = vec4(a_pos, 0.0, 1.0);
}`;

const BINDU_FS = /* glsl */ `#version 300 es
precision highp float;
in vec2 v_uv;
out vec4 o;
uniform float u_t;
uniform vec2 u_res;
uniform float u_lv;

// ── Noise substrate (Ashima/webgl-noise, shared with Metal port) ─────────
vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
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
  vec4 p = permute(permute(permute(i.z + vec4(0.0, i1.z, i2.z, 1.0)) + i.y + vec4(0.0, i1.y, i2.y, 1.0)) + i.x + vec4(0.0, i1.x, i2.x, 1.0));
  vec4 j = p - 49.0 * floor(p / 49.0);
  vec4 x_ = floor(j / 7.0);
  vec4 y_ = floor(j - 7.0 * x_);
  vec4 x = x_ * 2.0 / 7.0 + 0.5 / 7.0 - 1.0;
  vec4 y = y_ * 2.0 / 7.0 + 0.5 / 7.0 - 1.0;
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
  float v = 0.0, a = 0.5;
  for (int i = 0; i < 5; i++) { v += a * snoise(p); p *= 2.01; a *= 0.5; }
  return v;
}
float fbm4(vec3 p) { return fbm(p) + 0.0625 * snoise(p * 8.05); }

// IQ cosine palette — full rainbow as h sweeps 0..1
vec3 rainbow(float h) {
  return 0.5 + 0.5 * cos(6.28318 * (h + vec3(0.0, 0.33, 0.67)));
}

// ═══════════════════════════════════════════════════════════════════════════
//  composeOrb — the EXACT Metal port. Returns unpremultiplied RGBA.
//  uv: normalized 0..1, aspect-corrected by caller.
//  t:  seconds, lv: 0..1 chat activity.
// ═══════════════════════════════════════════════════════════════════════════
vec4 composeOrb(vec2 uv, float t, float lv) {
  vec2 st = (uv - 0.5) * 2.0;
  lv = clamp(lv, 0.0, 1.0);
  float r = length(st) + 1e-4;
  float fl = 0.7;

  // void openness — slow auto-cycle, pushed open by chat activity
  float cyc = sin(t * 0.30) + 0.55 * snoise(vec3(t * 0.08, 3.0, 0.0));
  float openness = clamp(smoothstep(0.30, 0.95, cyc) + lv * 0.7, 0.0, 1.0);

  // plasma drawn inward as the void opens (accretion)
  float2 pull = -(st / r) * openness * 0.16 * smoothstep(0.7, 0.1, r);

  // GRAVITY PULSE — invisible displacement ripple (no colour of its own)
  float gwave  = sin(r * 24.0 - t * 1.15);
  float gwenv  = exp(-r * 1.3) * smoothstep(0.05, 0.20, r);
  float2 gdisp = (st / r) * gwave * gwenv * 0.032;
  float2 sp = st + pull + gdisp;

  // formless turbulence — fbm folded through itself twice, advecting in time
  float3 P  = float3(sp * 1.5, t * 0.09 * fl);
  float a1  = fbm4(P);
  float3 P2 = P + (1.1 + 0.7 * fl) * float3(a1, fbm4(P + float3(3.1, 1.2, 4.0)), 0.0) + float3(0.0, 0.0, t * 0.04 * fl);
  float a2  = fbm4(P2 * 1.25);
  float3 P3 = P2 + (0.9 + 0.5 * fl) * float3(a2, fbm4(P2 + float3(8.3, 2.8, 0.0)), 0.0);
  float f   = fbm4(P3);
  float fil = clamp(1.0 - abs(f * 1.5), 0.0, 1.0); fil = pow(fil, 1.5);
  float dens = smoothstep(0.04, 0.72, a2);
  float energy = fil * dens;

  // full-rainbow plasma hue, drifting slowly
  float3 plasmaHue = pow(rainbow(fract(t * 0.013 + a1 * 0.5)), float3(0.8));
  float3 col = plasmaHue * energy * 2.8;
  float alpha = energy;

  // gravity pulse catches plasma's own light on its crest (tinted by local hue)
  float crest = max(gwave, 0.0) * gwenv;
  col   += plasmaHue * crest * (0.25 + energy) * 0.6;
  alpha  = max(alpha, crest * 0.5);

  // the void forming in the middle
  float voidR = mix(0.05, 0.42, openness);
  float wdist = r + 0.22 * f;
  float voidMask = smoothstep(voidR - 0.06, voidR + 0.18, wdist);
  col *= voidMask; alpha *= voidMask;

  // deep BLACK interior, rare threads of slow-cycling rainbow + distant glints
  float inside = 1.0 - voidMask;
  if (inside > 0.002) {
    float2 iv = st / max(voidR, 0.06);
    float ir = length(iv);
    float zdepth = 0.5 / (ir * ir + 0.15);
    float3 dp = float3(iv * 1.8, zdepth * 0.4 - t * 0.15);
    float dneb  = fbm4(dp);
    float dneb2 = fbm4(dp * 2.3 + 5.0);
    float3 deepCol = float3(0.004, 0.006, 0.014);
    float3 neon = pow(rainbow(fract(t * 0.016 + dneb2 * 0.6 + zdepth * 0.08)), float3(0.8));
    float tinge = smoothstep(0.60, 0.95, 0.5 + 0.5 * dneb);
    deepCol += neon * tinge * 0.32 * smoothstep(1.15, 0.1, ir);
    deepCol *= smoothstep(1.2, 0.05, ir);
    float glint = smoothstep(0.74, 0.90, fbm4(float3(iv * 6.0, zdepth * 0.3 - t * 0.2)));
    deepCol += neon * glint * 0.68 * smoothstep(1.0, 0.3, ir);
    col = mix(col, deepCol, inside);
    alpha = max(alpha, inside * 0.72);
  }

  return float4(col, alpha);
}

void main() {
  float ar = u_res.x / u_res.y;
  float2 uv = v_uv;
  uv.x *= ar;
  float4 orb = composeOrb(uv, u_t, u_lv);
  // premultiply alpha (matches Metal behaviour)
  float3 outCol = orb.rgb * orb.a;
  o = float4(outCol, orb.a);
}`;

// ── The full-viewport Bindu orb ───────────────────────────────────────────

function BinduShader({ phase }: { phase: string; reduceMotion: boolean }) {
  const materialRef = useRef<THREE.ShaderMaterial>(null);
  const { size } = useThree();

  useFrame((state) => {
    if (!materialRef.current) return;
    const m = materialRef.current;
    m.uniforms.u_t.value = state.clock.elapsedTime;
    m.uniforms.u_res.value.set(size.width, size.height);
    const thinking = phase === "thinking" ? 1.0 : 0.0;
    const speaking = phase === "listening" || phase === "speaking" ? 1.0 : 0.0;
    const lv = max(thinking, speaking);
    m.uniforms.u_lv.value += (lv - m.uniforms.u_lv.value) * 0.04;
  });

  return (
    <mesh frustumCulled={false} renderOrder={-100}>
      <planeGeometry args={[2, 2]} />
      <shaderMaterial
        ref={materialRef}
        vertexShader={BINDU_VS}
        fragmentShader={BINDU_FS}
        uniforms={{
          u_t: { value: 0 },
          u_res: { value: new THREE.Vector2(size.width, size.height) },
          u_lv: { value: 0 },
        }}
        depthWrite={false}
        depthTest={false}
        transparent={true}
      />
    </mesh>
  );
}

// ── Export ─────────────────────────────────────────────────────────────────

export type BackgroundPhase = "resting" | "thinking" | "listening" | "speaking";

export default function ThreeBackground({
  phase = "resting",
  reduceMotion = false,
}: {
  phase?: BackgroundPhase;
  reduceMotion?: boolean;
}) {
  return (
    <>
    {/* CSS fallback layer — always renders even if WebGL fails */}
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 0,
        background: "radial-gradient(ellipse 60% 80% at 50% 50%, rgba(76,29,149,0.15) 0%, rgba(49,30,81,0.10) 40%, #000000 100%)",
      }}
    />
    <Canvas
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance", preferWebGL2: true, failIfMajorPerformanceCaveat: false }}
      camera={{ position: [0, 0, 4.2], fov: 44 }}
      dpr={[1, 2]}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 0,
        background: "radial-gradient(ellipse 55% 70% at 50% 45%, rgba(76,29,149,0.25) 0%, rgba(49,30,81,0.18) 35%, rgba(15,8,30,0.30) 65%, #000000 100%)",
      }}
    >
      <BinduShader phase={phase} reduceMotion={reduceMotion} />
    </Canvas>
    </>
  );
}
