#include <metal_stdlib>
using namespace metal;

// ============================================================================
//  Bindu/Shaders.metal — native Metal orb for the chat backdrop.
//
//  The "Living Void" bindu: a turbulent, formless, ever-regenerating plasma that
//  tears open a deep BLACK void in its middle, rings it with an iridescent rim
//  and concentric GRAVITY RINGS, and lets a crisp bindu surface IN and OUT at the
//  void's heart only seldom. The interior is near-pure black threaded with rare
//  EVER-TRANSFORMING neon that drifts slowly through the whole rainbow. Owner-
//  approved look (2026-06-28). Rendered at native fps in an MTKView.
//
//  ── SWAP POINT ───────────────────────────────────────────────────────────
//  ALL the orb art lives in ONE function, `composeOrb(uv, t, lv)`, between the
//  matching `BEGIN ORB ART` / `END ORB ART` banners (+ its `rainbow`/`fbm4`
//  helpers). To restyle, replace ONLY that block. The noise substrate and the
//  vertex/fragment plumbing below the banner are stable and must not change.
//
//  Uniform contract (BinduUniforms, mirrored in BinduMetalView.swift):
//      uTime   — seconds since first frame        (GLSL u_t)
//      uLevel  — 0..1 energy/activity              (GLSL u_lv): chat activity.
//                Drives `openness` — the void tears open + the bindu surfaces as
//                the conversation lives (idle low = void mostly closed, plasma).
//      uRes    — drawable size in pixels (aspect correction; no GLSL analogue)
//
//  NOTE: symbols here are namespaced under `bindu` so the orb is self-contained
//  and never collides with other Metal sources added to the App target.
// ============================================================================

namespace bindu {

struct Uniforms {
    float  uTime;
    float  uLevel;
    float2 uRes;
};

// ----------------------------------------------------------------------------
//  NOISE SUBSTRATE (verbatim port of the shared GLSL NOISE block).
//  Do NOT edit to change the look — this is the shared noise substrate.
//  GLSL overloads mod289(vec3)/mod289(vec4) become distinct MSL names.
// ----------------------------------------------------------------------------

static inline float3 mod289_3(float3 x) { return x - floor(x / 289.0) * 289.0; }
static inline float4 mod289_4(float4 x) { return x - floor(x / 289.0) * 289.0; }
static inline float4 permute(float4 x)  { return mod289_4((x * 34.0 + 1.0) * x); }
static inline float4 taylorInvSqrt(float4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

// 3D simplex noise (Ashima / "webgl-noise" lineage). Use full-precision float;
// half would visibly drift the noise.
static float snoise(float3 v) {
    const float2 C = float2(1.0 / 6.0, 1.0 / 3.0);
    float3 i  = floor(v + dot(v, C.yyy));
    float3 x0 = v - i + dot(i, C.xxx);
    float3 g  = step(x0.yzx, x0.xyz);
    float3 l  = 1.0 - g;
    float3 i1 = min(g.xyz, l.zxy);
    float3 i2 = max(g.xyz, l.zxy);
    float3 x1 = x0 - i1 + C.xxx;
    float3 x2 = x0 - i2 + C.yyy;
    float3 x3 = x0 - 0.5;
    i = mod289_3(i);
    float4 p = permute(permute(permute(
        i.z + float4(0.0, i1.z, i2.z, 1.0))
        + i.y + float4(0.0, i1.y, i2.y, 1.0))
        + i.x + float4(0.0, i1.x, i2.x, 1.0));
    float4 j  = p - 49.0 * floor(p / 49.0);
    float4 x_ = floor(j / 7.0);
    float4 y_ = j - 7.0 * x_;
    float4 x  = x_ / 7.0 + 0.5 / 7.0 - 0.5;
    float4 y  = y_ / 7.0 + 0.5 / 7.0 - 0.5;
    float4 h  = 1.0 - abs(x) - abs(y);
    float4 b0 = float4(x.xy, y.xy);
    float4 b1 = float4(x.zw, y.zw);
    float4 s0 = floor(b0) * 2.0 + 1.0;
    float4 s1 = floor(b1) * 2.0 + 1.0;
    float4 sh = -step(h, float4(0.0));
    float4 a0 = b0.xzyw + s0.xzyw * sh.xxyy;
    float4 a1 = b1.xzyw + s1.xzyw * sh.zzww;
    float3 p0 = float3(a0.xy, h.x);
    float3 p1 = float3(a0.zw, h.y);
    float3 p2 = float3(a1.xy, h.z);
    float3 p3 = float3(a1.zw, h.w);
    float4 norm = taylorInvSqrt(float4(dot(p0, p0), dot(p1, p1), dot(p2, p2), dot(p3, p3)));
    p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
    float4 m = max(0.6 - float4(dot(x0, x0), dot(x1, x1), dot(x2, x2), dot(x3, x3)), 0.0);
    m = m * m;
    return 42.0 * dot(m * m, float4(dot(p0, x0), dot(p1, x1), dot(p2, x2), dot(p3, x3)));
}

static inline float fbm(float3 p) {
    return 0.5 * snoise(p) + 0.25 * snoise(p * 2.03) + 0.125 * snoise(p * 4.01);
}

// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  BEGIN ORB ART — the "Living Void" composition. Swap everything between    ║
// ║  this banner and END ORB ART to restyle the orb; leave noise + plumbing.   ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
//  A formless turbulent plasma (domain-warped fbm, advecting in time so it never
//  repeats) that tears open a deep BLACK void in the middle whose interior is a
//  recessed realm, threaded with rare EVER-TRANSFORMING neon (drifts through the
//  whole rainbow). An iridescent rim + concentric GRAVITY RINGS ring the void; a
//  crisp bindu surfaces IN and OUT at its heart. `lv` (chat activity) tears the
//  void open and brings the bindu; at idle the void opens only seldom on a slow
//  irregular cycle.
//
//  GLSL→MSL translation notes: vecN→floatN; atan(y,x)→atan2(y,x); fract/mix/
//  smoothstep/pow/exp/clamp identical. `pow(float3,float3)` is valid in MSL.

// IQ cosine palette — full rainbow as h sweeps 0..1.
static inline float3 rainbow(float h) {
    return 0.5 + 0.5 * cos(6.28318 * (h + float3(0.0, 0.33, 0.67)));
}

// 4-octave fbm (the plasma substrate; one octave finer than the shared `fbm`).
static inline float fbm4(float3 p) {
    return fbm(p) + 0.0625 * snoise(p * 8.05);
}

// THE swap point. Returns straight (un-premultiplied) RGB + alpha for uv in
// [0,1]; the fragment entry below does the premultiply.
//   uv : normalized 0..1 (GLSL v_uv), aspect-corrected by the caller.
//   t  : seconds (u_t)
//   lv : 0..1 chat activity (u_lv) — tears the void open + surfaces the bindu.
static float4 composeOrb(float2 uv, float t, float lv) {
    float2 st = (uv - 0.5) * 2.0;
    lv = clamp(lv, 0.0, 1.0);
    float r = length(st) + 1e-4;
    float fl = 0.7;   // flow / turbulence

    // void "openness": a slow irregular auto-cycle (opens SELDOM at idle), pushed
    // open by chat activity (lv) so the void tears + the bindu surfaces on answers.
    float cyc = sin(t * 0.30) + 0.55 * snoise(float3(t * 0.08, 3.0, 0.0));
    float openness = clamp(smoothstep(0.30, 0.95, cyc) + lv * 0.7, 0.0, 1.0);

    // plasma drawn inward as the void opens (accretion)
    float2 pull = -(st / r) * openness * 0.16 * smoothstep(0.7, 0.1, r);

    // GRAVITY PULSE — a FINE radial ripple that DISPLACES the plasma rather than
    // painting a coloured band. You see the plasma itself shiver outward in many
    // fine rings; the pulse has NO colour of its own ("invisible gravity pulse").
    // Replaces the old gold "sonar" swells. Owner 2026-06-28.
    float gwave  = sin(r * 24.0 - t * 1.15);                  // fine, many rings
    float gwenv  = exp(-r * 1.3) * smoothstep(0.05, 0.20, r);
    float2 gdisp = (st / r) * gwave * gwenv * 0.032;
    float2 sp = st + pull + gdisp;

    // formless turbulence — fbm folded through itself twice, advecting in time
    float3 P  = float3(sp * 1.5, t * 0.09 * fl);
    float a1  = fbm4(P);
    float3 P2 = P + (1.1 + 0.7 * fl) * float3(a1, fbm4(P + float3(3.1, 1.2, 4.0)), 0.0)
                  + float3(0.0, 0.0, t * 0.04 * fl);
    float a2  = fbm4(P2 * 1.25);
    float3 P3 = P2 + (0.9 + 0.5 * fl) * float3(a2, fbm4(P2 + float3(8.3, 2.8, 0.0)), 0.0);
    float f   = fbm4(P3);
    float fil = clamp(1.0 - abs(f * 1.5), 0.0, 1.0); fil = pow(fil, 1.5);  // thicker -> visible
    float dens = smoothstep(0.04, 0.72, a2);                              // wider -> more lit area
    float energy = fil * dens;

    // full-rainbow plasma hue, drifting slowly so it eventually visits every colour
    float3 plasmaHue = pow(rainbow(fract(t * 0.013 + a1 * 0.5)), float3(0.8));
    float3 col = plasmaHue * energy * 1.85;                               // brighter -> patterns read
    float alpha = energy;

    // the gravity pulse catches a hair of the plasma's OWN light on its crest,
    // tinted by the local hue (NEVER gold) — keeps the ripple invisible yet alive.
    float crest = max(gwave, 0.0) * gwenv;
    col   += plasmaHue * crest * (0.25 + energy) * 0.6;
    alpha  = max(alpha, crest * 0.5);

    // the void forming in the middle (formless boundary, opens with the cycle)
    float voidR = mix(0.05, 0.42, openness);
    float wdist = r + 0.22 * f;
    float voidMask = smoothstep(voidR - 0.04, voidR + 0.14, wdist);
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
        float3 deepCol = float3(0.002, 0.003, 0.008);
        float3 neon = pow(rainbow(fract(t * 0.016 + dneb2 * 0.6 + zdepth * 0.08)), float3(0.8));
        float tinge = smoothstep(0.60, 0.95, 0.5 + 0.5 * dneb);
        deepCol += neon * tinge * 0.20 * smoothstep(1.15, 0.1, ir);
        deepCol *= smoothstep(1.2, 0.05, ir);
        float glint = smoothstep(0.74, 0.90, fbm4(float3(iv * 6.0, zdepth * 0.3 - t * 0.2)));
        deepCol += neon * glint * 0.5 * smoothstep(1.0, 0.3, ir);
        col = mix(col, deepCol, inside);
        alpha = max(alpha, inside * 0.55);
    }

    // (Gravity is now the INVISIBLE displacement pulse applied to the plasma up by
    //  the accretion block — no coloured band here. The old gold "sonar" swells are
    //  gone: owner wanted the pulse felt, not seen as yellow rings.)

    // SMALL SHARP BINDU — a quiet, fine needle in a tight dark pocket. No deliberate
    // sparkle: the rest of the orb stays vague and dreaming, only THIS is sharp.
    float bp = (0.55 + 0.30 * sin(t * 0.6)) * (0.7 + 0.3 * openness);
    float bd = r;
    float pocket = 1.0 - 0.58 * exp(-pow(bd / 0.035, 2.0));      // small dark pocket -> it pierces
    col *= pocket;
    float bcore = exp(-bd * bd * 11000.0);                       // tight pinpoint
    float bhalo = exp(-bd * 72.0);                               // tighter sharp glow
    float bang = atan2(st.y, st.x);
    float bwavy = 1.0 + 0.45 * sin(bang * 8.0 - t * 2.0) * exp(-bd * 60.0);
    float bindu = (bcore * 4.0 + bhalo * 0.13) * bwavy * bp;
    float3 binduCol = mix(float3(1.0, 0.99, 0.95), float3(1.0, 0.82, 0.46), smoothstep(0.0, 0.04, bd));
    col += binduCol * bindu;
    alpha = max(alpha, bcore * bp);

    // generous edge fade so the whole composite (incl. rings) falls to nothing by
    // the view edge — this soft circle is what makes it read as a round orb.
    float edge = 1.0 - smoothstep(1.25, 1.9, r);
    col *= edge; alpha *= edge;

    // tonemap — brighter midtones so the plasma patterns read; void stays deep.
    col = col / (col + float3(0.5));

    alpha = clamp(alpha, 0.0, 1.0);
    col   = clamp(col, 0.0, 1.0);
    return float4(col, alpha);
}

// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  END ORB ART                                                              ║
// ╚══════════════════════════════════════════════════════════════════════════╝

struct VSOut {
    float4 position [[position]];
    float2 uv;
};

} // namespace bindu

// ----------------------------------------------------------------------------
//  PLUMBING (fullscreen triangle + fragment entry — stable, art-agnostic).
//
//  CRITICAL: the `vertex` / `fragment` entry points live OUTSIDE `namespace
//  bindu` on purpose. A Metal entry point declared inside a C++ namespace is
//  symbol-mangled into the library as `bindu::bindu_orb_vertex`, so the host's
//  `library.makeFunction(name: "bindu_orb_vertex")` returns nil, the pipeline
//  never builds, draw(in:) early-returns every frame, and the transparent
//  MTKView shows the page background through it (the "blank orb" bug). Keeping
//  the entries at global scope makes their library names plain
//  `bindu_orb_vertex` / `bindu_orb_fragment`, matching the Swift lookup. The
//  helpers + art stay namespaced under `bindu::` and are referenced as such.
// ----------------------------------------------------------------------------

// Fullscreen triangle: 3 verts cover clip space, no vertex buffer needed.
vertex bindu::VSOut bindu_orb_vertex(uint vid [[vertex_id]]) {
    float2 pos[3] = { float2(-1.0, -3.0), float2(-1.0, 1.0), float2(3.0, 1.0) };
    bindu::VSOut out;
    float2 p = pos[vid];
    out.position = float4(p, 0.0, 1.0);
    // uv 0..1, y flipped so the GLSL v_uv (origin bottom-left) orientation
    // matches Metal's top-left clip/texture space.
    out.uv = float2(p.x * 0.5 + 0.5, 1.0 - (p.y * 0.5 + 0.5));
    return out;
}

fragment float4 bindu_orb_fragment(bindu::VSOut in [[stage_in]],
                                   constant bindu::Uniforms &u [[buffer(0)]]) {
    // Aspect-correct so the orb stays circular on any drawable shape (the GLSL
    // assumed a square canvas).
    float2 uv = in.uv;
    float aspect = u.uRes.x / max(u.uRes.y, 1.0);
    if (aspect >= 1.0) {
        uv.x = (uv.x - 0.5) * aspect + 0.5;
    } else {
        uv.y = (uv.y - 0.5) / aspect + 0.5;
    }
    float4 c = bindu::composeOrb(uv, u.uTime, u.uLevel);
    // Premultiplied output (matches GLSL `o = vec4(col*alpha, alpha)`); the
    // pipeline MUST use premultiplied-alpha blending (one, oneMinusSrcAlpha).
    return float4(c.rgb * c.a, c.a);
}
