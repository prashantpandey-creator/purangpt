// ─────────────────────────────────────────────────────────────────────────
//  binduShaders — single source of truth for every Bindu Lab fragment shader.
//
//  Both the live page (src/app/bindu-lab/page.tsx) AND the offline screenshot
//  harness (scripts/shotBindu.mjs) import these exact strings, so what I tune
//  and screenshot is byte-for-byte what ships. Plain .mjs (with a sibling
//  .d.ts) so Node can import it natively for rendering while TS still types it.
// ─────────────────────────────────────────────────────────────────────────

export const VS = /*glsl*/ `#version 300 es
in vec2 a_pos;
out vec2 v_uv;
void main() {
  v_uv = a_pos * 0.5 + 0.5;
  gl_Position = vec4(a_pos, 0.0, 1.0);
}`;

// ── Shared GLSL preamble (noise functions) ──────────────────────────────

export const NOISE = /*glsl*/ `
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

float fbm(vec3 p) {
  return 0.5 * snoise(p) + 0.25 * snoise(p * 2.03) + 0.125 * snoise(p * 4.01);
}

vec3 cWhite  = vec3(1.0, 0.97, 0.88);
vec3 cGoldBr = vec3(1.0, 0.914, 0.659);
vec3 cGold   = vec3(0.796, 0.643, 0.333);
vec3 cEmber  = vec3(1.0, 0.541, 0.239);
`;

// ── ITERATION A: "Bold Rings, Compact Flame" ───────────────────────────

export const ITER_A = /*glsl*/ `#version 300 es
${NOISE}
void main() {
  vec2 st = (v_uv - 0.5) * 2.0;
  float t = u_t, lv = u_lv;

  float n1 = fbm(vec3(st * 3.0, t * 0.18));
  float n2 = fbm(vec3(st * 3.4 + n1 * 0.6, t * 0.14 + 4.0));
  vec2 warp = vec2(n1, n2 - 0.05) * (0.06 + lv * 0.11);
  vec2 fst = st * vec2(1.0, 0.88);
  float wd = length(fst + warp) * (1.0 + sin(t * 0.45) * (0.02 + lv * 0.03));

  float core = smoothstep(0.05 + lv * 0.03, 0.005, wd);
  float inner = smoothstep(0.16 + lv * 0.04, 0.03, wd) * 0.65;
  float outer = smoothstep(0.32 + lv * 0.08, 0.02, wd) * 0.25;
  float bloom = smoothstep(0.65, 0.04, wd) * 0.07;

  float rings = 0.0;
  for (int r = 0; r < 7; r++) {
    float fr = float(r);
    float radius = 0.12 + fr * 0.12;
    float breath = sin(t * 0.55 - fr * 0.6) * (0.012 + lv * 0.024);
    float thick = 0.007 + fr * 0.001;
    float edge = smoothstep(thick + 0.004, 0.0, abs(wd - (radius + breath)) - thick);
    float fade = max(0.0, 0.65 - fr * 0.06) * (0.8 + lv * 0.5);
    rings += edge * fade;
  }

  vec3 col = core * cWhite
    + inner * mix(cGoldBr, cEmber, 0.3 + n1 * 0.2)
    + outer * mix(cEmber, cGold, 0.3 + n2 * 0.2)
    + bloom * cGold
    + rings * mix(cGoldBr, cGold, 0.4);

  col = clamp(col, 0.0, 1.0);
  float a = clamp(core + inner + outer * 0.7 + bloom + rings, 0.0, 1.0);
  o = vec4(col * a, a);
}`;

// ── ITERATION B: "Amoeba Membrane" ─────────────────────────────────────

export const ITER_B = /*glsl*/ `#version 300 es
${NOISE}
void main() {
  vec2 st = (v_uv - 0.5) * 2.0;
  float t = u_t, lv = u_lv;

  float n1 = fbm(vec3(st * 2.6, t * 0.16));
  float n2 = fbm(vec3(st * 3.0 + n1 * 0.5, t * 0.12 + 4.0));
  vec2 warp = vec2(n1, n2 - 0.06) * (0.07 + lv * 0.13);
  vec2 fst = st * vec2(1.0, 0.9);
  float wd = length(fst + warp) * (1.0 + sin(t * 0.5) * (0.03 + lv * 0.03));

  float core = smoothstep(0.06 + lv * 0.04, 0.005, wd);
  float inner = smoothstep(0.2 + lv * 0.06, 0.04, wd) * 0.6;
  float outer = smoothstep(0.4 + lv * 0.12, 0.03, wd) * 0.28;
  float bloom = smoothstep(0.8, 0.05, wd) * 0.08;

  float memR = 0.72 + lv * 0.08;
  float memWarp = fbm(vec3(st * 1.8 + 17.0, t * 0.22)) * 0.12;
  float memDist = length(fst + warp * 0.3) + memWarp;
  float membrane = smoothstep(0.015, 0.0, abs(memDist - memR) - 0.006);
  float memGlow = smoothstep(0.08, 0.0, abs(memDist - memR)) * 0.12;

  float rings = 0.0;
  for (int r = 0; r < 5; r++) {
    float fr = float(r);
    float radius = 0.15 + fr * 0.11;
    float breath = sin(t * 0.5 - fr * 0.7) * (0.010 + lv * 0.020);
    float edge = smoothstep(0.010, 0.0, abs(wd - (radius + breath)) - 0.003);
    float inside = smoothstep(memR + 0.02, memR - 0.05, wd);
    rings += edge * (0.45 - fr * 0.06) * (0.72 + lv * 0.5) * inside;
  }

  vec3 col = core * cWhite
    + inner * mix(cGoldBr, cEmber, 0.35 + n1 * 0.2)
    + outer * mix(cEmber, cGold, 0.30 + n2 * 0.25)
    + bloom * cGold
    + rings * cGoldBr
    + membrane * mix(cGold, vec3(0.494, 0.573, 0.722), 0.35) * 0.8
    + memGlow * cGold;

  col = clamp(col, 0.0, 1.0);
  float a = clamp(core + inner + outer * 0.7 + bloom + rings + membrane * 0.7 + memGlow, 0.0, 1.0);
  o = vec4(col * a, a);
}`;

// ── ITERATION C: "Gravitational Burst" ─────────────────────────────────

export const ITER_C = /*glsl*/ `#version 300 es
${NOISE}
void main() {
  vec2 st = (v_uv - 0.5) * 2.0;
  float t = u_t, lv = u_lv;

  float n1 = fbm(vec3(st * 2.8, t * 0.2));
  float n2 = fbm(vec3(st * 3.2 + n1 * 0.4, t * 0.15 + 3.0));
  vec2 warp = vec2(n1, n2 - 0.04) * (0.06 + lv * 0.14);
  vec2 fst = st * vec2(1.0, 0.92);
  float wd = length(fst + warp);

  float singularity = smoothstep(0.03, 0.0, wd) * 1.2;
  float core = smoothstep(0.08 + lv * 0.05, 0.01, wd);
  float inner = smoothstep(0.22 + lv * 0.06, 0.04, wd) * 0.55;
  float outer = smoothstep(0.45 + lv * 0.15, 0.05, wd) * 0.22;
  float bloom = smoothstep(0.9, 0.06, wd) * 0.06;

  float rings = 0.0;
  float speed = 0.06 + lv * 0.14;
  for (int r = 0; r < 8; r++) {
    float fr = float(r);
    float phase = fract(t * speed - fr * 0.125);
    float radius = 0.06 + phase * 0.85;
    float life = smoothstep(0.0, 0.08, phase) * smoothstep(1.0, 0.6, phase);
    float edge = smoothstep(0.009, 0.0, abs(wd - radius) - 0.003);
    rings += edge * life * (0.55 + lv * 0.35);
  }

  vec3 col = singularity * vec3(1.0)
    + core * cWhite
    + inner * mix(cGoldBr, cEmber, 0.4)
    + outer * mix(cEmber, cGold, 0.35)
    + bloom * cGold
    + rings * mix(cGoldBr, cGold, 0.3);

  col = clamp(col, 0.0, 1.0);
  float a = clamp(singularity + core + inner + outer * 0.7 + bloom + rings, 0.0, 1.0);
  o = vec4(col * a, a);
}`;

// ── ITERATION D: "Spiral Galaxy" ───────────────────────────────────────

export const ITER_D = /*glsl*/ `#version 300 es
${NOISE}
void main() {
  vec2 st = (v_uv - 0.5) * 2.0;
  float t = u_t, lv = u_lv;

  float n1 = fbm(vec3(st * 2.6, t * 0.16));
  float n2 = fbm(vec3(st * 3.0 + n1 * 0.5, t * 0.12 + 4.0));
  vec2 warp = vec2(n1, n2 - 0.06) * (0.08 + lv * 0.14);
  vec2 fst = st * vec2(1.0, 0.9);

  float wd = length(fst + warp) * (1.0 + sin(t * 0.5) * 0.03);
  float core = smoothstep(0.06 + lv * 0.04, 0.005, wd);
  float inner = smoothstep(0.2 + lv * 0.06, 0.04, wd) * 0.6;
  float outer = smoothstep(0.4 + lv * 0.12, 0.03, wd) * 0.28;
  float bloom = smoothstep(0.8, 0.05, wd) * 0.08;

  float angle = atan(fst.y + warp.y, fst.x + warp.x);
  float twist = 2.5 + lv * 1.5;
  float spiralD = wd + angle * twist / (3.14159 * 2.0) * 0.08;

  float rings = 0.0;
  for (int r = 0; r < 6; r++) {
    float fr = float(r);
    float radius = 0.14 + fr * 0.12;
    float breath = sin(t * 0.45 - fr * 0.6) * (0.008 + lv * 0.018);
    float edge = smoothstep(0.010, 0.0, abs(spiralD - (radius + breath)) - 0.004);
    rings += edge * (0.50 - fr * 0.06) * (0.75 + lv * 0.5);
  }

  vec3 col = core * cWhite
    + inner * mix(cGoldBr, cEmber, 0.35 + n1 * 0.2)
    + outer * mix(cEmber, cGold, 0.3 + n2 * 0.25)
    + bloom * cGold
    + rings * mix(cGoldBr, vec3(0.494, 0.573, 0.722), 0.15);

  col = clamp(col, 0.0, 1.0);
  float a = clamp(core + inner + outer * 0.7 + bloom + rings, 0.0, 1.0);
  o = vec4(col * a, a);
}`;

// ── ITERATION E: "Aurora Void (Shakti)" — the original ────────────────

export const ITER_E = /*glsl*/ `#version 300 es
${NOISE}

vec4 shakti(vec2 st, float r, float t, float lv, float fi) {
  float rate = 0.085 + fi * 0.016;
  float prog = t * rate + fi * 0.37;
  float ph = fract(prog);
  float cyc = floor(prog);

  float life = sin(ph * 3.14159);
  life *= life;

  float s1 = hash(fi * 13.0 + cyc * 7.3 + 1.0);
  float s2 = hash(fi * 5.7 + cyc * 3.1 + 2.0);
  float ang = s1 * 6.2831 + (ph - 0.5) * 0.8 + t * (0.05 + fi * 0.012);
  float rad = 0.40 + 0.20 * s2;
  vec2 cen = vec2(cos(ang), sin(ang)) * rad;

  vec2 q = st - cen;
  float n1 = fbm(vec3(q * 5.5, t * 0.5 + fi * 2.0));
  vec2 warp = vec2(n1, n1 * 0.6 + 0.1) * 0.15;
  float fd = length(q + warp);
  float flame = smoothstep(0.16, 0.0, fd);
  float glow = exp(-fd * 6.5) * 0.55;
  float e = (flame + glow) * life;

  vec3 aBlue = vec3(0.27, 0.50, 1.0);
  vec3 aPink = vec3(1.0, 0.50, 0.82);
  vec3 aGold = vec3(1.0, 0.82, 0.44);
  float m = fract(s1 * 0.6 + t * 0.03 + fi * 0.2);
  vec3 ec = m < 0.5 ? mix(aBlue, aPink, m * 2.0)
                    : mix(aPink, aGold, (m - 0.5) * 2.0);

  // Reduce the brightness multiplier so it doesn't blow out to pure white when thinking
  return vec4(ec * e * (0.9 + lv * 0.25), e);
}

void main() {
  vec2 st = (v_uv - 0.5) * 2.0;
  float t = u_t, lv = u_lv;
  float r = length(st);

  vec3 col = vec3(0.0);
  float alpha = 0.0;

  float neb = fbm(vec3(st * 1.7 + vec2(0.0, t * 0.05), t * 0.06));
  neb = smoothstep(0.25, 0.95, 0.5 + 0.5 * neb) * exp(-pow((r - 0.5) / 0.34, 2.0));
  vec3 nebCol = mix(vec3(0.10, 0.16, 0.42), vec3(0.34, 0.13, 0.34), 0.5 + 0.5 * sin(t * 0.1));
  col += nebCol * neb * 0.28;
  alpha += neb * 0.28;

  for (int i = 0; i < 6; i++) {
    vec4 s = shakti(st, r, t, lv, float(i));
    col += s.rgb;
    alpha += s.a;
  }

  float ringR = 0.30 + 0.006 * sin(t * 0.7);
  float ring = smoothstep(0.014, 0.0, abs(r - ringR));
  float ringGlow = exp(-pow((r - ringR) / 0.05, 2.0)) * 0.45;
  vec3 ringCol = vec3(1.0, 0.84, 0.46);
  col += ringCol * (ring + ringGlow) * (0.8 + lv * 0.4);
  alpha += ring + ringGlow;

  float core = smoothstep(0.045, 0.0, r);
  float voidGlow = exp(-r * 5.0) * 0.3;
  col += vec3(1.0, 0.96, 0.86) * core + vec3(0.27, 0.50, 1.0) * voidGlow;
  alpha += core + voidGlow;

  alpha = clamp(alpha, 0.0, 1.0);
  // Soft tonemapping prevents additive blowout from becoming a flat white blob
  col = 1.0 - exp(-col * 1.1);
  o = vec4(col * alpha, alpha);
}`;

// ═══════════════════════════════════════════════════════════════════════
//  SHAKTI VARIATIONS — sub-iterations expanding on Iteration E
// ═══════════════════════════════════════════════════════════════════════

// ── E1: "Quantum Foam" ─────────────────────────────────────────────────

export const ITER_E1 = /*glsl*/ `#version 300 es
${NOISE}

vec4 spark(vec2 st, float t, float lv, float fi) {
  float rate = 0.18 + fi * 0.032;
  float prog = t * rate + fi * 0.19;
  float ph = fract(prog);
  float cyc = floor(prog);
  float life = pow(sin(ph * 3.14159), 3.0);

  float s1 = hash(fi * 17.0 + cyc * 11.3 + 1.0);
  float s2 = hash(fi * 7.7 + cyc * 5.1 + 2.0);
  float ang = s1 * 6.2831 + ph * 1.4 + t * (0.07 + fi * 0.018);
  float rad = 0.18 + 0.38 * s2;
  vec2 cen = vec2(cos(ang), sin(ang)) * rad;

  vec2 q = st - cen;
  float n1 = fbm(vec3(q * 9.0, t * 0.8 + fi * 3.0));
  vec2 warp = vec2(n1, n1 * 0.4) * 0.06;
  float fd = length(q + warp);
  float flame = smoothstep(0.06, 0.0, fd);
  float glow = exp(-fd * 15.0) * 0.28;
  float e = (flame + glow) * life;

  vec3 aBlue = vec3(0.30, 0.55, 1.0);
  vec3 aPink = vec3(1.0, 0.42, 0.75);
  vec3 aGold = vec3(1.0, 0.85, 0.48);
  float m = fract(s1 * 0.7 + t * 0.06 + fi * 0.13);
  vec3 ec = m < 0.5 ? mix(aBlue, aPink, m * 2.0)
                    : mix(aPink, aGold, (m - 0.5) * 2.0);
  return vec4(ec * e * (0.7 + lv * 0.5), e);
}

void main() {
  vec2 st = (v_uv - 0.5) * 2.0;
  float t = u_t, lv = u_lv;
  float r = length(st);
  vec3 col = vec3(0.0);
  float alpha = 0.0;

  float vac = fbm(vec3(st * 3.5, t * 0.14)) * 0.5 + 0.5;
  vac *= exp(-r * 2.2) * 0.14;
  col += vec3(0.12, 0.18, 0.38) * vac;
  alpha += vac;

  for (int i = 0; i < 14; i++) {
    vec4 s = spark(st, t, lv, float(i));
    col += s.rgb;
    alpha += s.a;
  }

  float ringR = 0.30 + 0.005 * sin(t * 0.8);
  float ring = smoothstep(0.012, 0.0, abs(r - ringR));
  float ringGlow = exp(-pow((r - ringR) / 0.04, 2.0)) * 0.35;
  col += vec3(1.0, 0.84, 0.46) * (ring + ringGlow) * (0.7 + lv * 0.4);
  alpha += ring + ringGlow;

  float core = smoothstep(0.035, 0.0, r);
  float voidGlow = exp(-r * 5.5) * 0.22;
  col += vec3(1.0, 0.96, 0.86) * core + vec3(0.25, 0.48, 1.0) * voidGlow;
  alpha += core + voidGlow;

  alpha = clamp(alpha, 0.0, 1.0);
  col = clamp(col, 0.0, 1.0);
  o = vec4(col * alpha, alpha);
}`;

// ── E2: "Arrival" — Three minds writing a living logogram ────────────

export const ITER_E2 = /*glsl*/ `#version 300 es
${NOISE}

// ---- Living Pearls: raymarched nacreous metaball pearls ----

float smin(float a, float b, float k){
    float h = clamp(0.5 + 0.5*(b-a)/k, 0.0, 1.0);
    return mix(b, a, h) - k*h*(1.0-h);
}

// drippy displacement of a sphere surface using snoise (slow liquid undulation)
float drip(vec3 p, float seed, float amt){
    float n = snoise(p*1.7 + vec3(0.0, 0.0, seed) + u_t*0.18);
    n += 0.5*snoise(p*3.3 + vec3(seed*2.0) - u_t*0.11);
    return n * amt;
}

// the three animated pearl centers (truly 3D, organic noise-warped orbits)
vec3 pcenter(int i){
    float fi = float(i);
    float ph = fi * 2.09439510; // 120 deg apart
    // base orbit radius shrinks toward 0 as they converge
    float spread = mix(0.62, 0.045, u_lv);
    // organic wobble so the gather is "no pattern yet a pattern"
    float wob = snoise(vec3(fi*3.1, u_t*0.21, fi*1.7));
    float wob2 = snoise(vec3(fi*1.3 + 5.0, u_t*0.15, 2.0));
    float ang = u_t*0.32 + ph + wob*0.55*(1.0 - u_lv);
    float r = spread * (1.0 + 0.10*wob2);
    float x = cos(ang)*r;
    float y = sin(ang)*r * 0.86;
    float z = sin(ang*0.7 + ph)*r*0.45 + wob*0.12*(1.0-u_lv);
    // gentle breathing toward/away from camera plane
    y += 0.04*sin(u_t*0.6 + fi*2.0);
    return vec3(x, y, z);
}

float prad(int i){
    float fi = float(i);
    // size-breath, each pearl on its own slow phase
    float br = 0.5 + 0.5*sin(u_t*0.55 + fi*2.3);
    float base = mix(0.30, 0.40, u_lv);
    return base * (0.92 + 0.10*br);
}

// scene SDF: smooth union of three drippy pearls; out params carry blend weights
float mapScene(vec3 p, out vec3 hue, out float coreGlow){
    vec3 cBlue = vec3(0.30, 0.55, 1.00);
    vec3 cGold = vec3(1.00, 0.74, 0.32);
    vec3 cRose = vec3(0.97, 0.40, 0.66);

    // k grows with convergence so they fuse harder near u_lv=1
    float k = mix(0.10, 0.55, u_lv) + 0.05;

    vec3 c0 = pcenter(0); float r0 = prad(0);
    vec3 c1 = pcenter(1); float r1 = prad(1);
    vec3 c2 = pcenter(2); float r2 = prad(2);

    // drippy surfaces (less drip when fully merged -> a single calm drop)
    float dripAmt = mix(0.045, 0.018, u_lv);
    float s0 = length(p - c0) - r0 + drip(p - c0, 11.0, dripAmt);
    float s1 = length(p - c1) - r1 + drip(p - c1, 27.0, dripAmt);
    float s2 = length(p - c2) - r2 + drip(p - c2, 41.0, dripAmt);

    float d = s0;
    d = smin(d, s1, k);
    d = smin(d, s2, k);

    // hue blend by per-pearl closeness (softmax-ish via inverse distance)
    float a0 = max(s0 + r0, 0.0);
    float a1 = max(s1 + r1, 0.0);
    float a2 = max(s2 + r2, 0.0);
    float w0 = 1.0 / (0.0008 + a0*a0 + 0.02);
    float w1 = 1.0 / (0.0008 + a1*a1 + 0.02);
    float w2 = 1.0 / (0.0008 + a2*a2 + 0.02);
    float ws = w0 + w1 + w2;
    hue = (cBlue*w0 + cGold*w1 + cRose*w2) / max(ws, 1e-4);

    coreGlow = 0.0;
    return d;
}

vec3 calcNormal(vec3 p){
    vec2 e = vec2(0.0025, 0.0);
    vec3 dum; float g;
    float dx = mapScene(p + e.xyy, dum, g) - mapScene(p - e.xyy, dum, g);
    float dy = mapScene(p + e.yxy, dum, g) - mapScene(p - e.yxy, dum, g);
    float dz = mapScene(p + e.yyx, dum, g) - mapScene(p - e.yyx, dum, g);
    vec3 n = vec3(dx, dy, dz);
    float l = length(n);
    return l > 1e-5 ? n / l : vec3(0.0, 0.0, -1.0);
}

// cheap soft shadow toward the key light
float softShadow(vec3 p, vec3 ld){
    float res = 1.0;
    float t = 0.03;
    vec3 dum; float g;
    for(int i = 0; i < 14; i++){
        vec3 pos = p + ld*t;
        float h = mapScene(pos, dum, g);
        if(h < 0.001){ return 0.15; }
        res = min(res, 8.0*h/t);
        t += clamp(h, 0.02, 0.12);
        if(t > 1.6) break;
    }
    return clamp(res, 0.15, 1.0);
}

// iridescent nacre tint from view/normal angle
vec3 nacre(float f, vec3 base){
    // soft rainbow shift driven by fresnel-ish term, kept pearly (low saturation)
    vec3 a = vec3(0.5);
    vec3 b = vec3(0.5);
    vec3 cc = vec3(1.0, 0.9, 0.8);
    vec3 d = vec3(0.0, 0.18, 0.42);
    vec3 rainbow = a + b*cos(6.28318*(cc*f + d));
    return mix(base, base*0.6 + rainbow*0.7, 0.45);
}

void main(){
    vec2 st = (v_uv - 0.5) * 2.0;

    vec3 ro = vec3(0.0, 0.0, -2.2);
    vec3 rd = normalize(vec3(st*0.92, 1.7));

    // key light slightly upper-left, in front
    vec3 ld = normalize(vec3(-0.45, 0.65, -0.6));

    vec3 col = vec3(0.0);
    float alpha = 0.0;

    // raymarch
    float t = 0.0;
    bool hit = false;
    vec3 p = ro;
    vec3 hue = vec3(1.0);
    float cg = 0.0;
    for(int i = 0; i < 48; i++){
        p = ro + rd*t;
        float d = mapScene(p, hue, cg);
        if(d < 0.0015){ hit = true; break; }
        t += d;
        if(t > 5.5) break;
    }

    if(hit){
        vec3 n = calcNormal(p);
        vec3 v = -rd; // toward camera
        float ndl = max(dot(n, ld), 0.0);
        float sh = softShadow(p, ld);

        // diffuse with soft wrap (milky, no hard terminator)
        float wrap = (ndl*0.7 + 0.3);
        float diff = wrap * sh;

        // fresnel rim
        float fres = pow(1.0 - max(dot(n, v), 0.0), 3.0);

        // specular highlight
        vec3 h = normalize(ld + v);
        float spec = pow(max(dot(n, h), 0.0), 60.0) * sh;

        // milky subsurface-ish core glow: brighter where facing camera
        float core = pow(max(dot(n, v), 0.0), 1.5);

        vec3 base = hue;
        // iridescent nacre across surface
        vec3 surf = nacre(fres*0.6 + core*0.4 + 0.15*snoise(p*4.0), base);

        vec3 lit = surf * (0.35 + 0.85*diff);      // body
        lit += surf * core * 0.55;                  // milky inner glow
        lit += vec3(1.0, 0.97, 0.9) * spec * 0.9;   // specular sparkle
        lit += mix(surf, vec3(1.0), 0.6) * fres * 0.8; // pearly rim

        // intensify overall as convergence rises
        float intensity = mix(0.9, 1.7, u_lv);
        col = lit * intensity;

        alpha = 1.0;
    }

    // secondary soft aura + central bindu (does not dominate)
    float rad = length(st);
    // shared glow halo around the cluster, warm-white, grows with u_lv
    float halo = exp(-rad*rad * mix(7.0, 3.0, u_lv));
    vec3 haloCol = mix(vec3(0.4,0.55,0.9), vec3(1.0,0.85,0.55), u_lv);
    col += haloCol * halo * mix(0.10, 0.45, u_lv);
    alpha = max(alpha, halo * mix(0.10, 0.40, u_lv));

    // the bright bindu point at full convergence
    float bindu = exp(-rad*rad * 260.0);
    float binduStr = smoothstep(0.55, 1.0, u_lv);
    col += vec3(1.0, 0.96, 0.86) * bindu * binduStr * 2.2;
    alpha = max(alpha, bindu * binduStr);

    alpha = clamp(alpha, 0.0, 1.0);
    col = clamp(col, 0.0, 1.0);
    o = vec4(col*alpha, alpha);
}
`;

// ── E3: "Saṅgam (Confluence)" ──────────────────────────────────────────

export const ITER_E3 = /*glsl*/ `#version 300 es
${NOISE}

void main() {
  vec2 st = (v_uv - 0.5) * 2.0;
  float t = u_t, lv = u_lv;
  float r = length(st);
  vec3 col = vec3(0.0);
  float alpha = 0.0;

  vec2 centers[6];
  float lives[6];
  vec3 colors[6];

  for (int i = 0; i < 6; i++) {
    float fi = float(i);
    float rate = 0.072 + fi * 0.013;
    float prog = t * rate + fi * 0.35;
    float ph = fract(prog);
    float cyc = floor(prog);
    lives[i] = sin(ph * 3.14159);
    lives[i] *= lives[i];

    float s1 = hash(fi * 13.0 + cyc * 7.3 + 1.0);
    float s2 = hash(fi * 5.7 + cyc * 3.1 + 2.0);
    float ang = s1 * 6.2831 + (ph - 0.5) * 0.7 + t * (0.04 + fi * 0.01);
    float rad = 0.32 + 0.24 * s2;
    centers[i] = vec2(cos(ang), sin(ang)) * rad;

    vec3 aBlue = vec3(0.27, 0.50, 1.0);
    vec3 aPink = vec3(1.0, 0.50, 0.82);
    vec3 aGold = vec3(1.0, 0.82, 0.44);
    float m = fract(s1 * 0.6 + t * 0.03 + fi * 0.2);
    colors[i] = m < 0.5 ? mix(aBlue, aPink, m * 2.0)
                        : mix(aPink, aGold, (m - 0.5) * 2.0);
  }

  for (int i = 0; i < 6; i++) {
    float fi = float(i);
    vec2 q = st - centers[i];
    float n1 = fbm(vec3(q * 5.5, t * 0.5 + fi * 2.0));
    vec2 warp = vec2(n1, n1 * 0.6 + 0.1) * 0.14;
    float fd = length(q + warp);
    float flame = smoothstep(0.14, 0.0, fd);
    float glow = exp(-fd * 7.0) * 0.45;
    float e = (flame + glow) * lives[i];
    col += colors[i] * e * (0.85 + lv * 0.5);
    alpha += e;
  }

  for (int i = 0; i < 6; i++) {
    for (int j = i + 1; j < 6; j++) {
      float d = distance(centers[i], centers[j]);
      if (d < 0.55) {
        float proximity = smoothstep(0.55, 0.12, d);
        vec2 ab = centers[j] - centers[i];
        float tP = clamp(dot(st - centers[i], ab) / dot(ab, ab), 0.0, 1.0);
        vec2 closest = centers[i] + ab * tP;
        float lineDist = length(st - closest);
        float bridge = exp(-lineDist * 14.0) * proximity * lives[i] * lives[j];
        vec3 bridgeCol = mix(colors[i], colors[j], tP);
        float n = fbm(vec3(closest * 4.0, t * 0.6 + float(i) + float(j)));
        float flicker = 0.7 + 0.3 * n;
        col += bridgeCol * bridge * flicker * 1.6 * (1.0 + lv * 0.5);
        alpha += bridge * flicker;
      }
    }
  }

  float neb = fbm(vec3(st * 1.7 + vec2(0.0, t * 0.05), t * 0.06));
  neb = smoothstep(0.25, 0.95, 0.5 + 0.5 * neb) * exp(-pow((r - 0.5) / 0.34, 2.0));
  vec3 nebCol = mix(vec3(0.10, 0.16, 0.42), vec3(0.34, 0.13, 0.34), 0.5 + 0.5 * sin(t * 0.1));
  col += nebCol * neb * 0.18;
  alpha += neb * 0.12;

  float ringR = 0.30 + 0.006 * sin(t * 0.7);
  float ring = smoothstep(0.014, 0.0, abs(r - ringR));
  float ringGlow = exp(-pow((r - ringR) / 0.05, 2.0)) * 0.45;
  col += vec3(1.0, 0.84, 0.46) * (ring + ringGlow) * (0.8 + lv * 0.4);
  alpha += ring + ringGlow;

  float core = smoothstep(0.045, 0.0, r);
  float voidGlow = exp(-r * 5.0) * 0.3;
  col += vec3(1.0, 0.96, 0.86) * core + vec3(0.27, 0.50, 1.0) * voidGlow;
  alpha += core + voidGlow;

  alpha = clamp(alpha, 0.0, 1.0);
  col = clamp(col, 0.0, 1.0);
  o = vec4(col * alpha, alpha);
}`;

// ── E4: "Aurora Curtains (Prāṇa-Vāyu)" ────────────────────────────────

export const ITER_E4 = /*glsl*/ `#version 300 es
${NOISE}

void main() {
  vec2 st = (v_uv - 0.5) * 2.0;
  float t = u_t, lv = u_lv;
  float r = length(st);
  float ang = atan(st.y, st.x);
  vec3 col = vec3(0.0);
  float alpha = 0.0;

  // A slow global swirl rotates the whole aurora around the void; the bands
  // also migrate in and out — together the field never holds a fixed shape.
  float swirl = t * 0.09 * (1.0 + lv * 0.6);
  for (int layer = 0; layer < 5; layer++) {
    float fl = float(layer);
    float bandR = 0.28 + fl * 0.085 + 0.05 * sin(t * 0.22 + fl * 1.3);
    float bandW = 0.08 + fl * 0.028;

    float radial = exp(-pow((r - bandR) / bandW, 2.0));

    // Faster temporal churn → the curtains actively morph, not just shimmer.
    float n1 = fbm(vec3(
      ang * 1.5 + fl * 3.0 + swirl,
      r * 4.5 + t * 0.18,
      t * 0.20 + fl * 1.7
    ));
    float n2 = fbm(vec3(
      ang * 2.3 + n1 * 0.9 + fl * 5.0 - swirl * 0.6,
      r * 3.2 - t * 0.14,
      t * 0.14 + fl * 2.8
    ));

    // Dissolve & re-form: the threshold breathes over time, so whole sheets
    // fade away and new ones condense elsewhere — a transformative flow.
    float thr = 0.10 + 0.16 * (0.5 + 0.5 * sin(t * 0.3 + fl * 2.1));
    float curtain = smoothstep(thr, thr + 0.55, 0.5 + 0.5 * n1);
    curtain *= smoothstep(thr + 0.05, thr + 0.45, 0.5 + 0.5 * n2);
    float intensity = curtain * radial;

    vec3 aBlue = vec3(0.18, 0.42, 1.0);
    vec3 aPink = vec3(0.88, 0.32, 0.68);
    vec3 aGold = vec3(1.0, 0.78, 0.38);
    vec3 aTeal = vec3(0.12, 0.68, 0.82);
    float cm = fract(fl * 0.28 + t * 0.05 + n1 * 0.18);
    vec3 lc = cm < 0.33 ? mix(aBlue, aTeal, cm * 3.0)
            : cm < 0.66 ? mix(aTeal, aPink, (cm - 0.33) * 3.0)
            : mix(aPink, aGold, (cm - 0.66) * 3.0);

    col += lc * intensity * (0.5 + lv * 0.35);
    alpha += intensity * 0.45;
  }

  float innerA = fbm(vec3(st * 2.5 + t * 0.12, t * 0.22));
  innerA = smoothstep(0.28, 0.78, 0.5 + 0.5 * innerA) * exp(-r * 3.2);
  col += vec3(0.22, 0.48, 0.92) * innerA * 0.35;
  alpha += innerA * 0.25;

  float ringR = 0.30 + 0.006 * sin(t * 0.7);
  float ring = smoothstep(0.014, 0.0, abs(r - ringR));
  float ringGlow = exp(-pow((r - ringR) / 0.05, 2.0)) * 0.45;
  col += vec3(1.0, 0.84, 0.46) * (ring + ringGlow) * (0.8 + lv * 0.4);
  alpha += ring + ringGlow;

  float core = smoothstep(0.045, 0.0, r);
  float voidGlow = exp(-r * 5.0) * 0.3;
  col += vec3(1.0, 0.96, 0.86) * core + vec3(0.27, 0.50, 1.0) * voidGlow;
  alpha += core + voidGlow;

  alpha = clamp(alpha, 0.0, 1.0);
  col = clamp(col, 0.0, 1.0);
  o = vec4(col * alpha, alpha);
}`;

// ── E5: "Comet Trails (Dhūmāvalī)" ────────────────────────────────────

export const ITER_E5 = /*glsl*/ `#version 300 es
${NOISE}

vec4 comet(vec2 st, float t, float lv, float fi) {
  float rate = 0.068 + fi * 0.012;
  float prog = t * rate + fi * 0.33;
  float ph = fract(prog);
  float cyc = floor(prog);
  float life = sin(ph * 3.14159);
  life *= life;

  float s1 = hash(fi * 13.0 + cyc * 7.3 + 1.0);
  float s2 = hash(fi * 5.7 + cyc * 3.1 + 2.0);
  float ang = s1 * 6.2831 + (ph - 0.5) * 0.9 + t * (0.05 + fi * 0.012);
  float rad = 0.36 + 0.22 * s2;
  vec2 cen = vec2(cos(ang), sin(ang)) * rad;

  vec2 vel = normalize(vec2(-sin(ang), cos(ang)));

  vec2 q = st - cen;
  float along = dot(q, vel);
  float perp = dot(q, vec2(-vel.y, vel.x));

  float n1 = fbm(vec3(q * 5.5, t * 0.5 + fi * 2.0));
  vec2 warp = vec2(n1, n1 * 0.5) * 0.10;
  float fd = length(q + warp);
  float head = smoothstep(0.11, 0.0, fd);
  float headGlow = exp(-fd * 9.0) * 0.45;

  float tailLen = 0.30 + lv * 0.12;
  float tailR = smoothstep(0.0, -tailLen, along);
  float tailW = exp(-perp * perp * 28.0);
  float tailN = fbm(vec3(along * 5.0 + t * 0.9, perp * 7.0, t * 0.35 + fi * 2.0));
  float tail = tailR * tailW * (0.45 + 0.45 * tailN) * 0.55;

  float e = (head + headGlow + tail) * life;

  vec3 aBlue = vec3(0.27, 0.50, 1.0);
  vec3 aPink = vec3(1.0, 0.50, 0.82);
  vec3 aGold = vec3(1.0, 0.82, 0.44);
  float m = fract(s1 * 0.6 + t * 0.03 + fi * 0.2);
  vec3 headCol = m < 0.5 ? mix(aBlue, aPink, m * 2.0)
                         : mix(aPink, aGold, (m - 0.5) * 2.0);
  vec3 tailCol = mix(headCol, vec3(0.12, 0.22, 0.50), 0.45);
  float hf = (head + headGlow) / max(e, 0.001);
  vec3 ec = mix(tailCol, headCol, hf);

  return vec4(ec * e * (0.85 + lv * 0.5), e);
}

void main() {
  vec2 st = (v_uv - 0.5) * 2.0;
  float t = u_t, lv = u_lv;
  float r = length(st);
  vec3 col = vec3(0.0);
  float alpha = 0.0;

  float neb = fbm(vec3(st * 1.5, t * 0.05));
  neb = smoothstep(0.3, 0.9, 0.5 + 0.5 * neb) * exp(-pow((r - 0.42) / 0.30, 2.0));
  col += mix(vec3(0.07, 0.12, 0.35), vec3(0.24, 0.08, 0.26), 0.5 + 0.5 * sin(t * 0.08)) * neb * 0.2;
  alpha += neb * 0.15;

  for (int i = 0; i < 6; i++) {
    vec4 s = comet(st, t, lv, float(i));
    col += s.rgb;
    alpha += s.a;
  }

  float ringR = 0.30 + 0.006 * sin(t * 0.7);
  float ring = smoothstep(0.014, 0.0, abs(r - ringR));
  float ringGlow = exp(-pow((r - ringR) / 0.05, 2.0)) * 0.45;
  col += vec3(1.0, 0.84, 0.46) * (ring + ringGlow) * (0.8 + lv * 0.4);
  alpha += ring + ringGlow;

  float core = smoothstep(0.045, 0.0, r);
  float voidGlow = exp(-r * 5.0) * 0.3;
  col += vec3(1.0, 0.96, 0.86) * core + vec3(0.27, 0.50, 1.0) * voidGlow;
  alpha += core + voidGlow;

  alpha = clamp(alpha, 0.0, 1.0);
  col = clamp(col, 0.0, 1.0);
  o = vec4(col * alpha, alpha);
}`;

// ── 4D: "Hyperdimensional Bindu" ───────────────────────────────────────
// A raymarched volumetric orb whose interior fire is sampled from a field
// ROTATING THROUGH THE 4TH DIMENSION (xw/yw/zw plane rotations) — so it churns
// and turns inside-out in that uncanny hyperdimensional way. Gold Fresnel rim +
// glassy specular give it real 3D depth: a point that contains all dimensions.

export const ITER_4D = /*glsl*/ `#version 300 es
${NOISE}

uniform sampler2D u_latent;

vec4 rotXW(vec4 p, float a){ float c=cos(a), s=sin(a); return vec4(c*p.x - s*p.w, p.y, p.z, s*p.x + c*p.w); }
vec4 rotYW(vec4 p, float a){ float c=cos(a), s=sin(a); return vec4(p.x, c*p.y - s*p.w, p.z, s*p.y + c*p.w); }
vec4 rotZW(vec4 p, float a){ float c=cos(a), s=sin(a); return vec4(p.x, p.y, c*p.z - s*p.w, s*p.z + c*p.w); }
vec4 rotXY(vec4 p, float a){ float c=cos(a), s=sin(a); return vec4(c*p.x - s*p.y, s*p.x + c*p.y, p.z, p.w); }

// Interior fire density, sampled from a 4D-rotating noise field.
float dens4(vec3 p, float t) {
  vec4 q = vec4(p, 0.0);
  
  // Sample the AI latent space. The texture is 24x16 (384 dims).
  // We sweep through it using the 3D position and time to find a semantic perturbation.
  vec2 latentUV = fract(p.xy * 0.5 + 0.5 + t * 0.05);
  float latentSample = texture(u_latent, latentUV).r;
  
  // Apply a subtle gravity-like distortion to the 4D coordinate space based on thought-vector density
  q.xyz += (latentSample - 0.5) * 0.4;
  q.w += (latentSample - 0.5) * 0.6;
  
  q = rotXW(q, t * 0.30);
  q = rotYW(q, t * 0.23 + 1.3);
  q = rotZW(q, t * 0.17 + 2.1);
  q = rotXY(q, t * 0.11);
  float n = fbm(q.xyz * 1.7 + vec3(q.w * 0.9));
  return n * 0.5 + 0.5;
}

// A handful of aura particles orbiting the void on tilted 3D rings — they sweep
// in front of and behind it (real depth), drifting blue→pink→gold like the
// Shakti energy in the flat Bindu.
vec3 particles(vec3 p, float t, float lv, out float pe) {
  pe = 0.0;
  vec3 acc = vec3(0.0);
  for (int k = 0; k < 7; k++) {
    float fk = float(k);
    float ang = t * (0.5 + fk * 0.11) + fk * 1.7;
    float tilt = fk * 0.8;
    float rho = 0.6 + 0.16 * sin(t * 0.4 + fk * 2.0);
    vec3 c = vec3(cos(ang) * rho, sin(ang) * cos(tilt) * rho, sin(ang) * sin(tilt) * rho);
    float dd = length(p - c);
    float g = exp(-dd * dd * 150.0) * (0.7 + lv * 0.6);
    pe += g;
    float m = fract(fk * 0.21 + t * 0.05);
    vec3 cc = m < 0.5 ? mix(vec3(0.30, 0.55, 1.0), vec3(1.0, 0.50, 0.85), m * 2.0)
                      : mix(vec3(1.0, 0.50, 0.85), vec3(1.0, 0.82, 0.44), (m - 0.5) * 2.0);
    acc += cc * g;
  }
  return acc;
}

void main() {
  vec2 st = (v_uv - 0.5) * 2.0;
  float t = u_t, lv = u_lv;

  // Camera looking at a unit sphere (the Bindu).
  vec3 ro = vec3(0.0, 0.0, -2.2);
  vec3 rd = normalize(vec3(st * 0.92, 1.7));
  float R = 0.92;

  vec3 col = vec3(0.0);
  float alpha = 0.0;

  float b = dot(ro, rd);
  float cc = dot(ro, ro) - R * R;
  float disc = b * b - cc;

  // Analytic edge antialiasing — a smooth, resolution-independent round limb
  // (kills the jagged silhouette of a hard ray-sphere cutoff).
  float aa = clamp(0.5 + 0.5 * disc / max(fwidth(disc), 1e-5), 0.0, 1.0);

  // The VOID: a deep dark heart (black-hole-like shadow) the fire haloes around.
  // Deeper + a touch wider now. 0 at the heart → 1 past the void.
  float voidShadow = smoothstep(0.05, 0.46, length(st));
  // A slow gravity pulse — the whole field breathes/disturbs like a wave train.
  float pulse = 0.82 + 0.18 * sin(t * 0.85);

  if (disc > 0.0) {
    float sq = sqrt(disc);
    float t0 = max(-b - sq, 0.0);
    float t1 = -b + sq;

    vec3 cWhite = vec3(1.0, 0.95, 0.82);
    vec3 cGold  = vec3(1.0, 0.78, 0.42);
    vec3 cBlue  = vec3(0.32, 0.55, 1.0);
    vec3 cPink  = vec3(1.0, 0.50, 0.85);

    const int STEPS = 28;
    float dt = (t1 - t0) / float(STEPS);
    for (int i = 0; i < STEPS; i++) {
      float tt = t0 + dt * (float(i) + 0.5);
      vec3 p = ro + rd * tt;
      float rr = clamp(length(p) / R, 0.0, 1.0);

      // DARK VOID at the centre; the hyperdimensional fire lives in a SHELL
      // wrapping the sphere — the ray crosses its near + far sides, so it reads
      // as a 3D hollow orb (not a flat disc), with a dark void in the middle.
      float shell = smoothstep(0.40, 0.72, rr) * smoothstep(1.0, 0.80, rr);
      // Gravity-wave disturbance — concentric ripples travelling through the halo.
      float grav = 0.6 + 0.4 * sin(rr * 16.0 - t * 2.2) + 0.18 * sin(rr * 27.0 - t * 3.1 + 1.7);
      grav = clamp(grav, 0.0, 1.4);
      float d = dens4(p * (1.5 + lv * 0.4), t);
      d = pow(d, 2.4);
      float emit = d * shell * voidShadow * grav * pulse;

      float mA = fract(d * 1.7 + atan(p.y, p.x) * 0.16 + t * 0.04);
      vec3 aura = mA < 0.5 ? mix(cBlue, cPink, mA * 2.0) : mix(cPink, cGold, (mA - 0.5) * 2.0);
      vec3 shade = mix(cGold, aura, smoothstep(0.55, 0.95, rr));
      shade = mix(cWhite, shade, smoothstep(0.40, 0.56, rr)); // hot inner lip of the shell

      col += shade * emit * dt * (5.2 + lv * 2.0);
      alpha += emit * dt * 4.2;

      // Orbiting aura particles (3D), kept out of the void heart.
      float pe;
      vec3 pcol = particles(p, t, lv, pe);
      col += pcol * dt * 9.0 * voidShadow;
      alpha += pe * dt * 5.5 * voidShadow;
    }

    // A faint deep-blue breath in the void + a tiny luminous Bindu seed-point.
    float voidGlow = smoothstep(0.34, 0.0, length(st)) * 0.12;
    col += cBlue * voidGlow;
    alpha += voidGlow;
    float seed = smoothstep(0.045, 0.0, length(st));
    col += cWhite * seed * 0.7;
    alpha += seed * 0.8;

    // Sphere surface → Fresnel gold rim (lit edge) + glassy specular = 3D depth.
    vec3 pent = ro + rd * t0;
    vec3 nrm = normalize(pent);
    float fres = pow(1.0 - max(dot(-rd, nrm), 0.0), 3.0);
    col += cGold * fres * (0.55 + lv * 0.4);
    alpha += fres * 0.6;

    vec3 L = normalize(vec3(0.55, 0.7, -0.7));
    float spec = pow(max(dot(reflect(rd, nrm), L), 0.0), 30.0);
    col += vec3(1.0, 0.96, 0.86) * spec * 0.7;
    alpha += spec * 0.4;
  }

  // Apply the antialiased coverage for a clean round edge.
  col *= aa;
  alpha *= aa;

  alpha = clamp(alpha, 0.0, 1.0);
  col = clamp(col, 0.0, 1.0);
  o = vec4(col, alpha); // emission already premultiplied by coverage
}`;

// ── ITER_GURUJI_LATENT: "Guruji Flame" with Latent Vector warping ──────────

export const ITER_GURUJI_LATENT = /*glsl*/ `#version 300 es
${NOISE}

uniform sampler2D u_latent;

void main() {
  vec2 st = (v_uv - 0.5) * 2.0;
  float t = u_t, lv = u_lv;
  
  // Sample the AI latent space. The texture is 24x16 (384 dims).
  vec2 latentUV = fract(st * 0.5 + 0.5 + t * 0.05);
  float latentSample = texture(u_latent, latentUV).r;
  
  // Apply semantic perturbation to coordinates
  st += (latentSample - 0.5) * 0.08;

  vec3 cWhite  = vec3(1.0, 0.97, 0.88);
  vec3 cGoldBr = vec3(1.0, 0.914, 0.659);
  vec3 cGold   = vec3(0.796, 0.643, 0.333);
  vec3 cEmber  = vec3(1.0, 0.541, 0.239);
  vec3 cViolet = vec3(0.545, 0.361, 0.965);

  float n1 = fbm(vec3(st * 2.6, t * 0.16));
  float n2 = fbm(vec3(st * 3.0 + n1 * 0.5, t * 0.12 + 4.0));
  float n3 = fbm(vec3(st * 6.8 + n2 * 0.7, t * 0.38 + 9.0));
  vec2 warp = vec2(n1, n2 - 0.06) * (0.07 + lv * 0.13)
            + vec2(n3 * 0.5, n3) * (0.022 + lv * 0.03);
  vec2 fst = st * vec2(1.0, 0.9);
  float wd = length(fst + warp) * (1.0 + sin(t * 0.5) * (0.03 + lv * 0.03));

  float flicker = 0.9 + 0.1 * sin(t * 7.3 + n3 * 6.28) * (0.5 + 0.5 * sin(t * 2.1));
  float tide = 0.5 + 0.5 * sin(t * 0.11) * (0.7 + 0.3 * sin(t * 0.043));

  float coreR = 0.038 + lv * 0.028;
  float core = smoothstep(coreR, coreR * 0.06, wd) * flicker;

  float corona = smoothstep(coreR * 2.4, coreR * 0.5, wd) * 0.42 * flicker;
  float inR = 0.13 + lv * 0.045;
  float inner = smoothstep(inR + 0.085, inR * 0.22, wd) * 0.50 * (0.9 + 0.22 * n3);
  float outR = 0.30 + lv * 0.09;
  float outer = smoothstep(outR + 0.22, outR * 0.12, wd) * 0.28 * (0.85 + 0.3 * n3);
  float bloom = smoothstep(0.85, 0.05, wd) * 0.10 * (0.6 + 0.5 * tide);
  float aura = smoothstep(1.0, 0.06, wd) * (0.22 + lv * 0.18) * (0.82 + 0.4 * n2) * (0.55 + 0.6 * tide);

  float ang = atan(st.y, st.x);
  float rings = 0.0;
  for (int r = 0; r < 3; r++) {
    float fr = float(r);
    float radius = 0.18 + fr * 0.14;
    float breath = sin(t * 0.5 - fr * 0.7) * (0.008 + lv * 0.016);
    float line = smoothstep(0.014, 0.0, abs(wd - (radius + breath)));
    float dir = mod(fr, 2.0) < 0.5 ? 1.0 : -1.0;
    float spin = t * (0.16 + fr * 0.05) * dir;
    float aa = ang + spin;
    float wisp = fbm(vec3(cos(aa) * 1.8, sin(aa) * 1.8, fr * 2.7 + t * 0.05));
    wisp = smoothstep(0.0, 0.6, wisp);
    rings += line * wisp * (0.30 - fr * 0.05) * (0.7 + lv * 0.55);
  }

  float rr = length(st);
  float wspeed = 0.9 + 0.5 * sin(t * 0.19) + 0.2 * sin(t * 0.07);
  float spiralPhase = ang * 3.0 - log(max(rr, 0.02)) * 5.5 - t * wspeed;
  float sturb = fbm(vec3(st * 3.0, t * 0.14));
  float arms = pow(0.5 + 0.5 * sin(spiralPhase), 6.0);
  float spiral = arms * smoothstep(0.30, 0.0, rr) * (0.7 + 0.5 * lv) * (0.7 + 0.4 * flicker) * (0.7 + 0.5 * sturb);
  vec3 spiralHue = mix(cViolet, cGoldBr, 0.5 + 0.5 * sin(spiralPhase * 0.5 + t * 0.3));
  spiralHue = mix(spiralHue, cEmber, 0.28 * sturb);

  float gwave = sin(wd * 16.0 - t * (1.0 + 0.4 * wspeed));
  float gwenv = exp(-wd * 1.15) * smoothstep(0.05, 0.20, wd);
  float gcrest = max(gwave, 0.0) * gwenv * (0.7 + 0.5 * lv);

  float hueT = 0.5 + 0.5 * sin(t * 0.18 + n2 * 2.5);
  vec3 surroundHue = mix(cViolet, vec3(0.13, 0.36, 0.62), hueT);
  surroundHue = mix(surroundHue, cEmber, 0.32 * (0.5 + 0.5 * sin(t * 0.11 + n1 * 2.0)));
  float fineTex = fbm(vec3(st * 4.2 + 7.0, t * 0.10));
  float surroundField = smoothstep(1.18, 0.16, wd) * (0.08 + 0.12 * fineTex);

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
