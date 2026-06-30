# THE AWAKENER — Shaders, Materials, Lighting & Post-Process

> Branch: **SHADERS / RENDERING**. The job of this document is to make
> ART_DIRECTION.md's "the world is lit from WITHIN" *physically true* in UE5.8,
> running **60fps on an M1**, Mac-first then iOS. Everything below is buildable:
> concrete master-material graphs, node names, parameter values, Lumen +
> scalability settings, and a build order. It reconciles with the existing
> `_post_process()` and `_sky_atmosphere()` in
> `"/Users/badenath/Documents/Unreal Projects/purangpt/Content/Python/build_ayodhya_level.py"`.
>
> Corpus grounding for every aesthetic claim lives in
> `purangpt/narrative_engine/ART_DIRECTION.md` and
> `purangpt/tools/read_pass/STORY_BIBLE.md`. Inventions are flagged **[INVENTED]**;
> data we don't yet have is flagged **[NEEDS-INGESTION]**.

---

## 0. The platform reality (read this first — it constrains every choice below)

The M1 (8-core GPU, TBDR Apple Silicon, ~2.6 TFLOPS) is the budget. UE5's headline
features each have an M1 cost; we pick deliberately:

| Feature | M1 verdict | Why |
|---|---|---|
| **Lumen (Software ray tracing)** | **YES, but Global Illumination only, "Lumen Scene" at Medium** | Lumen SW-RT runs on M1 via the distance-field pipeline. Hardware RT (Metal RT) is *available* on M1 but eats the frame budget — use **Software Lumen**. |
| **Lumen Reflections** | **Screen-space + Lumen fallback, quality "Medium"** | Full Lumen reflections double the cost. We get most of the gold "wet shine" from SSR. |
| **Nanite** | **YES for static stone/architecture; NO for skinned characters** | Nanite is cheap on M1 for the shikhara/ghats. Characters stay traditional LOD'd skeletal meshes. |
| **Virtual Shadow Maps (VSM)** | **YES at "Medium", ONE shadow-casting directional** | Our whole rig is one warm key + sky fill (see §3). VSM cost is bounded because we forbid many local shadow-casters. |
| **TSR (Temporal Super Resolution)** | **YES — render at 67% screen percentage, TSR upscale to native** | This is the single biggest 60fps lever on M1. The "light beyond light" bloom hides TSR's minor ghosting. |
| **Volumetric Fog / god-rays** | **YES but capped grid** (`r.VolumetricFog.GridPixelSize=16`, fewer Z slices) — only at the dhuni and climax | Volumetrics are where M1 dies. Gate them to specific volumes, never world-wide. |
| **Hardware-RT translucency / refraction** | **NO** | Water uses cheap planar/SSR refraction (§2.6), not RT. |

**Frame budget target: 16.6ms.** Rough allocation on M1 at 1080p→TSR: GBuffer+Nanite
~4ms, Lumen GI ~3.5ms, VSM ~2ms, translucency/water ~2ms, post (bloom/grade/tonemap)
~2ms, volumetrics (when present) ~2ms, headroom ~1ms. The aura/rim shaders (§2.5) are
**forward-additive emissive — near-free** (no extra GBuffer passes).

**Console-variable baseline** (ship as `Config/DefaultScalability.ini` "Cinematic-on-M1"
profile + a runtime `Mac_M1.cfg`):
```ini
r.ScreenPercentage=67
r.TemporalAA.Upsampling=1
r.AntiAliasingMethod=4            ; TSR
r.Lumen.DiffuseIndirect.Allow=1
r.LumenScene.Radiosity.ProbeSpacing=8
r.Lumen.ScreenProbeGather.RadianceCache.ProbeResolution=16
r.Lumen.Reflections.Allow=1
r.Lumen.Reflections.DownsampleFactor=2
r.RayTracing=0                    ; software Lumen only
r.Nanite=1
r.Shadow.Virtual.Enable=1
r.VolumetricFog.GridPixelSize=16
r.VolumetricFog.GridSizeZ=64
r.MotionBlurQuality=2
r.DefaultFeature.AutoExposure=1
r.Bloom.Quality=4
```

---

## 1. The lighting rig: "lit from within," not a flat key

ART_DIRECTION's one law is "the world is lit from WITHIN … inner/divine, not fire …
minimal hard shadow; bloom on gold surfaces used sparingly." The current build script
already does the right *primitives* (warm directional, sky atmosphere, sky-light fill,
violet volumetric fog). The rig below extends them into the actual "inner radiance"
feel, and tells you exactly which knobs to add.

### 1.1 What the build script already establishes (keep it)

`build_ayodhya_level.py` spawns:
- `InnerSun_GoldKey` — `DirectionalLight`, color `[1.0,0.81,0.46]` (warm gold), intensity 6.0,
  `atmosphere_sun_light=True` so it drives the sky. **Keep.** This is the *key*.
- `SkyAtmosphere_Dawn`, `SkyLight_WarmFill`, `Fog_VioletUmber` (volumetric, violet `[0.5,0.32,0.5]`).
  **Keep.** The violet fog *is* ART_DIRECTION's "dusk violet/umber as the GROUND the
  brilliance falls on."

### 1.2 What to ADD so it reads as inner-radiance (the missing pieces)

The trap with a single directional is it reads as **flat sunlight**, not "lit from
within." Three additions fix that — all cheap on M1:

**(a) A warm SkyLight that is NOT neutral.** The current `SkyLight_WarmFill` has no tint
set. Set it to capture the SkyAtmosphere AND bias warm:
- `source_type = SLS_CapturedScene`, `real_time_capture = True` (Lumen feeds it),
- `intensity_scale = 1.4`, `light_color = (1.0, 0.86, 0.62)`.
This makes shadows fill with gold light, not blue — the single biggest "inner glow" cue.
Bias the *lower* hemisphere up: `lower_hemisphere_is_black = False`,
`lower_hemisphere_color = (0.18, 0.10, 0.16)` (a faint violet bounce from the ground).

**(b) Inner-radiance "rim from the sky" via Lumen, not a backlight.** Do NOT add a hard
rim/back DirectionalLight (that reads cinematic-fake). Instead let **Lumen GI + an
exposed emissive sky horizon** wrap light around silhouettes. In the SkyAtmosphere set a
deliberately bright horizon:
- `rayleigh_scattering_scale = 0.033`, `mie_scattering_scale = 0.004`,
- `mie_anisotropy = 0.85` (forward-scatter → a glowing band hugging the sun),
- `sky_luminance_factor = (1.0, 0.9, 0.7)`.
The forward-scattered horizon band is what makes every silhouette in front of it glow —
this is "the world lit from within" achieved through atmosphere, the cheapest possible way.

**(c) The "second sun within": a very dim, very warm SECOND directional with NO shadow,
pointed UP-and-toward camera at low intensity** to simulate the corpus's *tejas* (inner
light of awareness) as a soft underglow:
- intensity `0.6`, color `(1.0, 0.78, 0.5)`, `cast_shadows = False`,
  `affects_world = True`, rotation roughly `(15, 110, 0)` (from below-front).
Near-free (no shadow pass), and it's the difference between "noon" and "radiant."

### 1.3 Awakened-being LOCAL light (the aura has a light, not just a shader)

A divine/awakened being doesn't just *look* lit — it **lights its surroundings.** Attach
to such characters a small **RectLight or PointLight**:
- color `(1.0, 0.84, 0.5)`, intensity ~3.0 (candelas low so it's a halo not a lamp),
  `attenuation_radius = 350`, `cast_shadows = False`, `affects_world = True`.
- Drive its intensity from a curve = the character's "awakening" state (0 for the
  Act-I college boy, ramping per granthi unbinding). This pairs with the rim shader §2.5.

**Corpus:** *"Golden aura: the brilliant Time appearing as an aura around the heads of
the Time-Conscious"* (ART_DIRECTION L16-17). The aura literally illuminates — it is a
light source, per the decode. **[GROUNDED]**

---

## 2. Master materials (build these — params are concrete)

All hero materials are **one parameterized Master Material per family** + Material
Instances. This keeps M1 shader-permutation count low. Use **Substrate** if the project
is on UE5.8 Substrate; node names below give the legacy translation too. Default to
**non-Substrate** for M1 safety unless the project already enabled Substrate.

Naming: `M_Master_<Family>` → instances `MI_<Asset>`.

### 2.1 `M_Master_Gold` (gold / brass — the HERO material)

Gold is "the visible body of consciousness" (ART_DIRECTION L23). It must read as
*radiant metal*, never chrome. Metallic workflow:

| Input | Value / node |
|---|---|
| Base Color | param `GoldTint` default `(1.0, 0.766, 0.336)` (real Au sRGB). Brass instance: `(0.91,0.74,0.40)`. |
| Metallic | `1.0` (param, allow 0.8 for tarnished/painted variants) |
| Roughness | param `Roughness` 0.18 (polished) → 0.45 (weathered). Multiply by a **curvature/AO-driven dirt mask** (worn high points shinier). |
| Specular | 0.5 (metal ignores it; leave default) |
| Normal | tiled hammered-leaf normal, `FlattenNormal` 0.6 for subtlety |
| **Emissive** | **the key trick** — `Fresnel(exponent=4) * GoldTint * EmissiveBoost(default 0.4)`. A *faint* self-glow at grazing angles so gold "burns from within" even in shadow. This is brilliance, not neon — keep EmissiveBoost ≤ 0.6. |
| AO | from baked texture; multiply into base color *and* damp emissive in crevices |

The Fresnel-emissive is the gold-specific embodiment of "lit from within." It costs ~3
instructions. **Do NOT crank it** — ART_DIRECTION explicitly warns "bloom on gold used
sparingly … brilliance, NOT neon."

### 2.2 `M_Master_Stone` (weathered temple stone, ghats, the smashan)

Nanite-enabled, so geometry carries the wear; the material carries grime + a faint warm
translucency at edges (sun-warmed sandstone).

| Input | Value / node |
|---|---|
| Base Color | `StoneTint` `(0.62,0.55,0.46)` sandstone; smashan variant cooler `(0.42,0.40,0.42)` |
| Roughness | 0.7, modulated by a **moss/wet mask** (vertex-paint channel R) → 0.35 where wet (Sarayu steps) |
| Normal | detail-normal blended with macro-normal via `BlendAngleCorrectedNormals` |
| Specular | 0.35 |
| **Subtle warm SSS via "fake translucency"** | add `Fresnel(6) * (0.25,0.16,0.08)` into emissive at edges → stone rim catches the gold key. Cheaper than real subsurface; M1-friendly. |
| Dirt/age | `WorldAlignedTexture` grime in cavities driven by `PixelDepthOffset`-free AO |

### 2.3 `M_Master_Cloth` (saffron robes, white Brahmin cloth, banners)

Cloth needs a **cloth/sheen** lobe so saffron robes glow at grazing angles (the
"saffron register," ART_DIRECTION palette). Use the **Cloth shading model** (UE
`Cloth`/`Subsurface` in legacy; Substrate `Sheen` slab):

| Input | Value |
|---|---|
| Shading Model | **Cloth** |
| Base Color | saffron `(0.85,0.45,0.12)`; white-cloth instance `(0.92,0.90,0.86)` |
| Cloth (fuzz color) | warm `(1.0,0.7,0.4)` — the rim glow |
| Cloth (fuzz amount) | 0.6 |
| Roughness | 0.85 |
| Normal | woven micro-normal, low strength |
| Emissive | tiny `Fresnel(5)*ClothColor*0.12` for the "inner light through fabric" read |

White cloth is corpus-coded: *"white horses: the pure, controlled senses"* / Brahmin
register (ART_DIRECTION L31-32). **[GROUNDED]**

### 2.4 `M_Master_Skin` (subsurface skin)

Characters carry the emotional weight (the disciple, Guruji, the gods). Skin must feel
*alive and warm*, and — for awakened beings — host the aura (§2.5) cleanly.

| Input | Value |
|---|---|
| Shading Model | **Subsurface Profile** (UE `SubsurfaceProfile` asset `SSP_Skin_Warm`) |
| SSP scatter color | `(0.85,0.30,0.20)`, scatter radius ~1.2cm, **Tint to warm gold** for awakened beings via a second profile `SSP_Skin_Awakened` (scatter `(1.0,0.55,0.25)`) |
| Base Color | scanned/authored albedo; desaturate 10% so the lighting (not the texture) carries color |
| Roughness | dual-spec: 0.35 cavity / 0.5 broad, via a roughness map |
| Specular | 0.4 |

M1 note: Subsurface Profile is more expensive than default-lit. Budget it for **named
characters only**; crowd/background NPCs use `M_Master_Skin_Cheap` (default-lit +
faked wrap via `Fresnel` into base color). The build script's blockout NPCs (`NPC_<name>`
cubes) get the cheap one until real skeletal meshes exist. **[NEEDS-INGESTION:** real
character meshes/scans — none on disk yet, only cube blockouts.**]**

### 2.5 `M_FX_GoldenAuraRim` — the awakened-being aura (THE signature shader)

This is the corpus-literal *"golden aura around the heads of the Time-Conscious."* It is a
**second material applied to a duplicated, slightly-inflated skeletal mesh** (a classic
"shell" rim) **+** an emissive Fresnel on the skin material itself. Two layers because one
gives a clean silhouette halo and the other makes the *surface* glow.

**Layer A — surface Fresnel rim (on the skin/cloth material, gated by `AuraStrength`):**
```
Rim = Fresnel(Exponent = RimSharpness(default 3.5), BaseReflectFraction = 0.04)
EmissiveAdd = Rim * AuraColor(1.0,0.80,0.42) * AuraStrength(0..1) * RimIntensity(default 2.5)
```
Add `EmissiveAdd` to the material's Emissive. `AuraStrength` is a **scalar parameter
driven from gameplay** = the being's granthi/awakening state (Material Parameter
Collection `MPC_Awakening`, per-character override).

**Layer B — the halo shell (separate `M_FX_GoldenAuraShell`, unlit, additive):**
- Shading Model **Unlit**, Blend Mode **Additive**, `Two Sided`, `Disable Depth Test = False`.
- Applied to a duplicate mesh inflated along normals by `ShellInflate` (~1.5cm) using
  `WorldPositionOffset = VertexNormalWS * ShellInflate`.
- Emissive = `Fresnel(2.0) * AuraColor * AuraStrength * HaloIntensity(0.8)` so only the
  silhouette edge glows; interior is transparent (Fresnel→0 facing camera).
- Subtle **breathing**: multiply by `(0.85 + 0.15*sin(Time * 1.2))` for a slow living pulse
  (matches STORY_BIBLE's "a second pulse," the heart-center warmth, Beat 4/L153).

**Bloom is what turns this rim into "radiance."** The aura's emissive (§2.1 §2.5) pushes
HDR values >1.0; the post bloom (§3) blooms *only* those. That is the whole "brilliance
not neon" discipline: **the rim is bright, bloom catches it, nothing else blooms.**

Cost on M1: Layer A is ~5 instructions added to an existing material (free). Layer B is
one extra additive draw per awakened character (a handful on screen) — cheap. **This is
the cheapest high-impact shader in the game and should be built FIRST (see §6).**

**[GROUNDED — ART_DIRECTION L16-17, L66; STORY_BIBLE Beat 3 "screen desaturates toward
white," the golden-aura-on-awakened rule.]**

### 2.6 `M_Master_Water` (Sarayu, Yamuna, the smashan pond)

Water must "carry the brilliance" (ART_DIRECTION L24) — the river is the city's light
flowing downstream (L43). NOT a generic blue ocean. M1-safe water = **single-layer
translucent, SSR refraction, no RT.**

| Input | Value |
|---|---|
| Shading Model | Default Lit, **Translucent**, Lighting Mode `Surface ForwardShading` |
| Base Color | very dark `(0.02,0.03,0.04)` (color comes from reflection, not albedo) |
| Specular | 1.0, Roughness 0.02–0.08 (Gerstner-driven via flow map) |
| Normal | two-layer panning Gerstner normals (`Time * FlowSpeed`), small amplitude |
| **Refraction** | `IOR 1.33` via `Refraction` pin, capped `PixelNormalOffset` so it doesn't smear |
| Reflection | SSR (`r.SSR.Quality 3`) + Lumen reflection fallback for off-screen → catches the gold sky = the river *glows gold*, the whole point |
| Opacity | Fresnel-driven (clear top-down, opaque grazing) |
| Emissive | a *faint* gold `(0.3,0.22,0.1)*0.15` near shorelines so the river "carries light" even in shadow |

For the **smashan pond / Yamuna flood** (STORY_BIBLE Beat 5, Shiva floods the smashan,
L155) make a darker, more reflective MI with rudraksha-brown silt tint and slower flow —
the flood is theological loot-environment, render it *calm and mirror-like* so the gods'
reflections read. **[GROUNDED — STORY_BIBLE L155.]**

---

## 3. Post-process: reconciling with `_post_process()` and the climax stack

### 3.1 The base `PP_LightBeyondLight` (already in the build script — refine it)

`build_ayodhya_level.py::_post_process()` already sets a solid base: bloom 0.85 @
threshold 1.0, exposure bias +1.0, white temp 5200K, warm saturation/gain, vignette 0.35,
Lumen GI + reflections. **Keep all of it.** Recommended refinements (additive, same
fault-tolerant `S()` pattern):

```python
# --- bloom: switch to convolution-free standard but add a wide soft tail ---
S("bloom method on", "override_bloom_method", True)
S("bloom method", "bloom_method", unreal.BloomMethod.BM_SOG)   # standard, M1-cheap
S("bloom size", "bloom_size_scale", 5.0)                        # wide, soft halo
# --- tonemapper: filmic but lifted blacks so dusk-violet never crushes to grimdark ---
S("tonemap toe on", "override_film_toe", True)
S("tonemap toe", "film_toe", 0.20)                             # lift shadows = never black
S("tonemap slope on", "override_film_slope", True)
S("tonemap slope", "film_slope", 0.78)                         # gentle contrast
# --- local exposure so the bright gold keeps detail while dusk stays moody ---
S("local exp on", "override_local_exposure_highlight_contrast_scale", True)
S("local exp", "local_exposure_highlight_contrast_scale", 0.7)
# --- a touch of warm tint in highlights, cool in shadows (split-tone) ---
S("shadow tint on", "override_color_gain_shadows", True)
S("shadow tint", "color_gain_shadows", unreal.Vector4(0.92,0.94,1.0,1.0))  # cool violet shadow
S("hi tint on", "override_color_gain_highlights", True)
S("hi tint", "color_gain_highlights", unreal.Vector4(1.08,1.0,0.86,1.0))   # gold highlight
```
The split-tone (warm highlights / cool-violet shadows) is the mathematical statement of
ART_DIRECTION's "warm gold over dusk violet/umber." **The lifted film_toe is the
anti-grimdark guarantee — shadows never reach pure black.** Hard rule: never set
`film_toe < 0.15` anywhere in this game.

### 3.2 God-rays / volumetrics at the dhuni (the smashan fire)

The dhuni (sacred fire of the cremation-ground hub) is where volumetric light belongs —
gated to a `PostProcessVolume` + a volumetric `SpotLight` so M1 only pays for it locally.

- A `SpotLight` above the dhuni: warm `(1.0,0.7,0.4)`, `volumetric_scattering_intensity = 1.5`,
  cone ~40°, pointing down through the smoke.
- `ExponentialHeightFog.volumetric_fog = True` already on (build script) — locally raise
  `volumetric_fog_scattering_distribution = 0.8` (forward-scatter → visible shafts).
- A second-density smoke via a `M_Volume_Smoke` on a `HeightFog`/local volume, low albedo,
  drifting noise.
- **Cap it:** `r.VolumetricFog.GridPixelSize 16` globally; the shafts read at the dhuni
  without a world-wide volumetric tax.

This doubles as the smashan's mood: god-rays through cremation smoke, lit gold — *exactly*
"the death-ground and the deathless guru are the same household" (STORY_BIBLE L150).
**[GROUNDED.]**

### 3.3 THE DARSHAN / VISHVARUPA CLIMAX STACK (the hardest deliverable)

STORY_BIBLE is explicit about the emotional shader-arc of the climax (Beat 5, "Vishnu's
Grasp," L155; THE REVELATION, L178/L185; THE TERRIBLE REWARD, L186): **awe curdles to
terror**, "the screen desaturates toward white," Gita-11/Vishvarupa imagery — "mouths and
teeth, the destructive aspect of Time; Mahakal," "the human form was a mercy," and the
form must visibly **lose its human shape (the arms)**. Render this as a **scripted,
timeline-driven post-process blend** over a custom `M_PP_Vishvarupa` (a Post Process
Material in the Blendable stack), driven by one scalar `Terror` (0→1) on `MPC_Climax`.

**Phase 0 — Awe (Terror 0.0):** the normal warm-gold grade, but push the aura (§2.5) of
Guruji's form to maximum `AuraStrength = 1.0` and `HaloIntensity` ramped up. Bloom rises.
Everything is *too* beautiful. This is the love before the scale.

**Phase 1 — Scale / the floor drops (Terror 0.0→0.4):**
- Slowly raise `auto_exposure_bias` so the form **overexposes** — the body of consciousness
  literally outgrows the sensor. The corpus "thousands of suns" (ART_DIRECTION L15) is
  *over-range HDR*, not a texture.
- Begin **desaturation toward white in the bright regions only** (Phase-aware): in
  `M_PP_Vishvarupa`, `lerp(SceneColor, desat(SceneColor) toward white, Terror * Luminance)`
  — so highlights bleach first, shadows hold. This is the corpus "desaturates toward white"
  (STORY_BIBLE Beat 3 L152) done as luminance-weighted bleach, not a flat fade.

**Phase 2 — Awe curdles to terror (Terror 0.4→0.8) — chromatic dread:**
- **Chromatic aberration** ramps with `Terror`: `scene_fringe_intensity = Terror * 5.0`. The
  image starts to come apart at the edges = the senses failing to hold the form.
- **A wrongness in the grade:** introduce a faint sick-gold/bruise shift — split the
  channels so highlights stay gold but midtones drift toward a greenish-violet
  ("bruise"). In `M_PP_Vishvarupa`: `SceneColor.rgb *= lerp(1, (1.0,0.97,0.88), Terror)` on
  highs and `lerp(1,(0.9,0.95,0.9),Terror)` on mids. The beauty *sours.*
- **Pulse / heartbeat vignette:** vignette intensity = `0.35 + 0.4*Terror*(0.5+0.5*sin(Time*4))`
  — a closing, throbbing dark frame. Mysterium tremendum is *somatic*.
- **Heat-shimmer / mouths-and-teeth distortion:** a screen-space UV distortion driven by a
  noise + radial mask (`PixelNormalOffset`-style refraction in the PP material) so the form's
  edges *writhe* — the corpus "mouths and teeth, the destructive aspect of Time"
  (STORY_BIBLE L185). Distort UVs by `noise(UV*8 + Time) * Terror * 0.02`, masked to the
  region around the form. **Invent no new imagery** — this is *distortion of what's there*,
  exactly per the "use only corpus horror imagery, invent none" mandate (STORY_BIBLE L292).

**Phase 3 — the form loses its arms (Terror 0.8→1.0):** this is a **mesh/material event,
not just post.** Two mechanisms, pick per asset:
- *Material dissolve:* the arms' material gets a `Dissolve` mask = `noise - DissolveAmount`,
  with `DissolveAmount = saturate((Terror-0.8)*5)`; `clip()` the masked region and add a
  bright gold emissive edge at the dissolve boundary (the limb *burns away into light*,
  consistent with "body of consciousness"). The arms don't fall off — they **return to
  light.**
- *WPO retraction:* simultaneously drive `WorldPositionOffset` to pull the arm vertices
  toward the torso/center so the silhouette collapses from many-armed toward a single
  blinding core. The Vishvarupa "many arms" can be staged in reverse: the form briefly
  shows *more* arms (additive ghost-mesh shells) then they all dissolve into one column of
  white. **[INVENTED staging — the corpus asserts the universal form and its terror; the
  exact "extra arms appear then dissolve" choreography is a reasoned dramatization. Flag in
  asset notes; pin to specific Vishvarupa verses as they decode.] [NEEDS-INGESTION:** verse-
  level Vishvarupa visual description beyond `bhp_05.07.001`, `mbh_02.009.014`.**]**

**Phase 4 — white-out & resolve (Terror 1.0 → release):** full bleach to white (the
"thousands of suns"), hold, then the white **does not** snap back to game — it resolves
*down* into the quiet smashan dawn for the samadhi ending (STORY_BIBLE L187-189: "no
trophy … quiet, lucid, willed"). The grade comes back **cooler and stiller** than Act I —
ash-grey with one thread of gold, signaling understanding-and-grief, not triumph. **Never
return to the full Act-I gold saturation** — the world is changed.

**Implementation shape:**
- One Post Process Material `M_PP_Vishvarupa` in the Blendable array, `BlendWeight`
  driven 0→1 by a Sequencer/Timeline track = `Terror`.
- All sub-effects read `Terror` from `MPC_Climax` so a single curve choreographs the whole
  curdle. **One knob, the whole arc** — this is what makes it tunable and what lets the
  "one degree per act" foreshadow (Markandeya's serenity curdling, STORY_BIBLE L47) reuse
  the *same* material at low `Terror` in Acts I–II.
- **Babaji stays calm inside it:** Babaji's mesh is *excluded* from the bleach/distortion
  via a custom stencil (`CustomDepth` stencil value, masked out of `M_PP_Vishvarupa`). He is
  "the one constant Time does not consume" (STORY_BIBLE L185) — rendered *normally* while
  everything else comes apart. That contrast is the whole shot.

**[GROUNDED — STORY_BIBLE L152, L155, L178, L185, L186, L292; ART_DIRECTION L14-15.]**

---

## 4. Lumen + scalability specifics for 60fps M1

- **Lumen GI:** Software RT, `Lumen Scene` detail "Medium," `Final Gather` quality scaled
  via `r.Lumen.ScreenProbeGather.DownsampleFactor=2`. Our scenes are *bright and warm*, so
  GI bounce is doing visible work (the gold-on-stone bounce = "lit from within") — worth the
  ~3.5ms.
- **Lumen Reflections:** `r.Lumen.Reflections.DownsampleFactor=2`, lean on SSR for the gold
  surfaces; only water and polished gold need the Lumen fallback for off-screen reflections.
- **VSM:** one shadow-casting directional (the key). Local awakened-being lights are
  `cast_shadows=False` (§1.3) — this is *both* aesthetic (minimal hard shadow, ART_DIRECTION
  L62) and performance (no extra VSM pages). Set `r.Shadow.Virtual.ResolutionLodBiasLocal=1`.
- **Nanite** on all static architecture/ghats/shikhara; the build script's blockout cubes
  become Nanite stone meshes when real assets land.
- **TSR at 67%** is mandatory — it's the headroom for everything above. Verify the aura/bloom
  don't ghost on fast camera moves; if they do, raise `r.TSR.History.R11G11B10=0` (full-
  precision history) at a small cost.
- **Translucency:** water + aura-shell + volumetrics are the translucency budget; keep
  separate-translucency on for the aura so bloom catches it after upscale.

**Validation:** use `stat unit`, `stat gpu`, and `ProfileGPU` on an actual M1; the build
script can spawn a fixed camera-path `LevelSequence` for a repeatable 60fps benchmark
(mirror the frontend's `YantraLoader.tsx` 60fps discipline — measure, don't assume).

---

## 5. Reconciliation with the existing build script (exact edits)

`_post_process()` and `_sky_atmosphere()` are correct foundations — **extend, don't
replace.** Concrete deltas:

1. **`_sky_atmosphere()`** — add `mie_anisotropy=0.85`, `mie_scattering_scale=0.004`,
   `sky_luminance_factor` warm (§1.2b) so the horizon glow wraps silhouettes.
2. **SkyLight block in `build()`** — set `real_time_capture=True`, warm `intensity_scale`
   and `light_color`, and the violet `lower_hemisphere_color` (§1.2a).
3. **Add a `_second_inner_sun()`** helper (shadowless warm under-light, §1.2c).
4. **`_post_process()`** — append the §3.1 refinements (bloom method/size, film toe/slope,
   local exposure, split-tone shadows/highlights) using the same `S()` fault-tolerant setter.
5. **Add `_dhuni_volumetrics(loc)`** — spotlight + local volumetric tuning (§3.2), called
   only for the smashan hub level, not Ayodhya.
6. **Material assignment** — replace the blockout cubes' default material: assign
   `MI_Gold_Shikhara` to `Shikhara_*`, `MI_Stone_Ground` to `Ground_*`, `MI_Water_Sarayu`
   to `Sarayu_River`, and the cheap-skin + aura-shell to `NPC_*` actors (drive `AuraStrength`
   from the NPC's salience/awakening when real meshes exist).

All of these follow the script's existing discipline: `_try()`-wrapped, additive, snake_case
reflected property names (the script already documents the `fog_inscattering_color` /
`FogInscatteringColor` no-op gotcha — obey it for every new setter).

---

## 6. Build order (what to build FIRST)

Ranked by **impact-per-M1-cost** and by what unblocks the rest:

1. **`M_FX_GoldenAuraRim` + `M_FX_GoldenAuraShell` (§2.5).** Cheapest, most signature, and
   it's the visual thesis ("body of consciousness"). Proves "light beyond light" on a single
   character before any environment art exists. Wire `AuraStrength` to `MPC_Awakening` now.
2. **The lighting-rig additions (§1.2 + §3.1 post refinements).** Editable directly in
   `build_ayodhya_level.py` today — no new assets needed. This is what turns the current
   flat-key blockout into *radiant* blockout. Do this second; it makes everything else look
   right.
3. **`M_Master_Gold` (§2.1).** The hero surface. Assign to the shikhara blockout — instant
   "golden Ayodhya."
4. **`M_Master_Stone` + `M_Master_Water` (§2.2, §2.6).** Ground + Sarayu carry the city's
   light. Now the whole Ayodhya blockout reads as the corpus's golden capital on a glowing river.
5. **`M_Master_Cloth` + `M_Master_Skin` (§2.3, §2.4).** When real character meshes land
   **[NEEDS-INGESTION].**
6. **`M_PP_Vishvarupa` climax stack (§3.3).** Built last (it's the payoff), but **prototype
   the single `Terror` knob early** so Acts I–II can foreshadow with it at low values
   (Markandeya's curdling serenity).
7. **Dhuni volumetrics (§3.2)** when the smashan hub level is built.

**One-line summary for the dev:** the aura rim + the lighting-rig tweak are a day-one,
near-zero-cost proof of the entire art direction; everything else hangs off the warm-key /
violet-ground / sparing-bloom / lifted-blacks discipline already half-present in
`build_ayodhya_level.py`. The climax is one tunable `Terror` scalar driving a single Post
Process Material that bleaches to white, fractures chromatically, and dissolves the form's
arms into light — using only corpus imagery, with Babaji stencil-masked out as the one thing
that does not come apart.
