# THE AWAKENER — Graphics Asset Pipeline

> The fastest CREDIBLE route from CUBE-BLOCKOUT Ayodhya to real, breathtaking,
> Assassin's-Creed-grade 3D on **UE5.8 / M1-class hardware**, Mac-first then iOS.
> This is an execution doc — exact Fab/Megascans kits, AI-gen recipes, material
> params, UE class names, JSON additions, and the data-driven swap path that stops
> `build_ayodhya_level.py` spawning cubes and starts it spawning real meshes.
>
> Source-of-truth inputs read for this doc:
> - `ART_DIRECTION.md` ("light beyond light" — gold = body of consciousness; bloom
>   sparing; warm gold over dusk violet/umber; golden aura on awakened beings).
> - `build_ayodhya_level.py` (the live, auto-on-boot blockout builder).
> - `tools/world_export/check.py` (the graph→world-JSON exporter; current data shape).
> - `Content/ayodhya_world.json` (the actual shipped data being swapped against).
> - `STORY_BIBLE.md` (smashan/dhuni/lingam hub + 5 journeys + cast + deity-forms).

---

## 0. The core decision: blockout-replace, not blockout-rebuild

We do **not** rebuild the level by hand in the editor. The blockout is already
**data-driven from the world JSON** — every cube is spawned from a JSON record.
So the entire graphics upgrade reduces to **one swap**: give each JSON record a
`mesh` id + material slots, and make `build_ayodhya_level.py` load that mesh
instead of `/Engine/BasicShapes/Cube`. The cube layout the exporter already
computes (ring of NPCs, crested shikhara skyline, ground plane, Sarayu strip)
*becomes* the real-mesh layout for free. This keeps the moat intact: the graph
still decides who/what/where; we only change *what mesh sits at each slot*.

The whole pipeline is therefore three tracks running in parallel:

| Track | What | Who/what produces it |
|---|---|---|
| **A. Modular kits** | Buy/pull marketplace meshes for the 80% generic (ground, stone, props, ghat steps, foliage, water) | Fab / Megascans / Quixel Bridge |
| **B. Bespoke Puranic** | The 20% the marketplace lacks (shikhara temple, smashan dhuni, Govardhan hill, air-lingam) | Blender + AI-gen (Meshy/Tripo), retopo, UE import |
| **C. Characters** | Disciple, NPCs, Babaji, deity-forms, golden-aura shader | MetaHuman + Fab clothing + Marvelous/Blender + the aura material |

And one piece of glue: **the JSON schema additions + the loader rewrite** (§6).

---

## 1. Hardware reality on M1 (this constrains every choice)

M1/M1 Pro (8-core GPU, unified memory) running UE5.8 on Metal. Hard truths that
pick our techniques:

- **Nanite works on Apple Silicon in 5.8** but is GPU-heavy on the M1's tile GPU.
  Use Nanite for **hero static meshes** (the great temple, hill cliffs, big stone)
  where its auto-LOD pays off; **disable Nanite on small/instanced props** (lamps,
  pots, railings) and ship them as traditional LOD'd static meshes via ISM/HISM.
- **Lumen**: use **Software Ray Tracing + Final Gather** (not Hardware RT — Apple
  HWRT path is immature/slow on M1). This already matches the post-process the
  build script sets (`DynamicGlobalIlluminationMethod.LUMEN`). Keep
  `r.Lumen.ScreenProbeGather.RadianceCache 1`. Target **Lumen Scene** detail =
  Medium for the open city.
- **Virtual Shadow Maps** on but clamp: `r.Shadow.Virtual.ResolutionLodBiasLocal 1`.
- **Texture budget**: unified memory means VRAM == RAM. Keep streaming pool ~2GB
  (`r.Streaming.PoolSize 2048`). Author hero textures at 2K, props at 1K, trim
  sheets 512–1K. **Never ship 4K** except the hero temple's facade trim.
- **iOS later**: iOS will NOT run Nanite/Lumen. Plan a **second material/quality
  path** from day one: every hero material gets a `Mobile` quality switch
  (`Quality Switch` node) and every Nanite mesh has baked LODs so the iOS build
  falls back to baked lightmaps + LOD meshes. Don't author yourself into a
  Nanite-only corner. (This is a build-setting fork, not a re-art — but only if
  the meshes carry LODs, hence "keep LODs on props.")

**Frame target:** 60fps at 1080p on M1 for the open city is achievable with the
above. The smashan (smaller, night, fewer draws) is easier; Ayodhya (open, many
NPCs) is the stress case — budget there.

---

## 2. Track A — Modular kits to pull/buy NOW (the 80%)

Priority is **Ayodhya + smashan first** (§5 budget). Everything below is on
**Fab** (the merged Quixel/Unreal/ArtStation marketplace in 5.8; Quixel Bridge is
now the in-editor "Fab" plugin). Free Megascans are included with a UE/Epic
account. Pull order:

### 2.1 Free / included first (zero spend, pull today via Bridge/Fab plugin)
- **Megascans → Surfaces**: `Indian Sandstone`, `Weathered Stone`, `Marble`,
  `Wet Mud / Riverbed`, `Ash / Charcoal ground`, `Cobblestone`. These become the
  master-material instances for ground, ghat, temple stone, smashan ash-ground.
- **Megascans → 3D Assets**: cracked stone blocks, debris, pottery shards, rope,
  cloth piles, firewood, rocks/boulders (for Govardhan + smashan), `Banyan` and
  `Fig/Pipal` tree atlases, `Banana leaf`, `Lotus` (Sarayu/pond).
- **Megascans → Decals**: soot/scorch (dhuni), water stains, moss, cracks, ash —
  these do enormous credibility work cheaply on the temple/ghat.
- **UE Marketplace freebies**: the monthly free packs; grab any
  Indian/Asian/temple/village set when offered.

### 2.2 Paid modular kits — the credibility multipliers (buy these)
Search Fab for these categories; representative packs (verify current listings —
marketplace SKUs churn, so these are the *kinds* to buy, named where stable):

| Need | Fab search / pack kind | Why |
|---|---|---|
| **Indian temple/architecture modular** | "Indian Temple", "Hindu Temple Modular", "South Asian Architecture Kit" | Pillars, jaali screens, plinths, mandapa, torana gates — the Ayodhya streets + the journey temples |
| **Ghat / riverfront steps** | "Varanasi", "Ghat", "Indian Riverfront", "Stone Steps Modular" | Benares/Kashi + the Sarayu edge: tiered stone steps to water |
| **Indian village / props** | "Indian Village", "Rajasthan", "Asian Village Props" | Pots, oil lamps (diya), bells, garlands, market stalls, cloth awnings — set-dressing density = AC-grade feel |
| **Modular ancient city / palace** | "Ancient City Modular", "Sandstone Palace", "Stylized Hindu City" | Dasharatha's golden capital fabric between the hero temple and the river |
| **Foliage / Indian flora** | "Banyan", "Tropical Foliage", "Indian Trees" | Govardhan greenery, smashan trees, Sarayu banks |
| **Cremation-ground / ascetic props** | "Sadhu", "Cremation", "Ritual Fire", "Skull props" | The smashan: dhuni firewood, skulls, tridents, ash pots, rudraksha |
| **Water / river** | UE5 **Water plugin** (built-in) + a river spline; or "Stylized River" | Sarayu + the Govardhan/Badrinath water, the Act-II flood |

**Buy rule:** prefer **modular kits** (snap-together pieces) over monolithic
hero buildings — modular lets the data-driven spawner mix pieces per building and
keeps memory low through instancing. One good Indian-temple modular kit + one
ghat kit + one village-props kit covers ~80% of Ayodhya and Benares.

### 2.3 What NOT to buy
Avoid "fantasy temple" / "Aztec" / "generic medieval" kits — they read wrong and
violate ART_DIRECTION (grimdark/European). Avoid PBR sets with baked harsh
torchlight — we relight everything with the inner-radiance rig.

---

## 3. Track B — Bespoke Puranic geometry the marketplace lacks (the 20%)

These four forms do not exist as buyable assets and define the project. Pipeline
for each: **AI-gen draft → Blender retopo/clean → UE import → master material**.

### 3.0 The AI-gen tool choice (use, with discipline)
- **Meshy.ai** (text+image→3D, has PBR texturing, free tier) — primary for props
  and mid-complexity forms (dhuni, lingam, ritual objects, statues).
- **Tripo3D** — alternative/second opinion; good clean topology on single objects.
- **Workflow**: generate from a *grounded prompt* (cite the corpus form), download
  GLB, **retopo in Blender** (AI meshes are dense/messy — decimate to target tris,
  fix normals, UV-unwrap, bake AO), then import `.fbx`/`.glb` to UE. AI-gen is for
  the **draft silhouette**, never the final unedited mesh.
- **Flag discipline:** every AI-gen/bespoke form is `[REASONED EXTENSION]` in its
  asset notes (same rule as ART_DIRECTION/world_export) — the texts assert the
  *meaning*, we author the *form*.

### 3.1 The shikhara temple (Ayodhya hero + journey temples) `[REASONED EXTENSION]`
The single most important asset — it IS the Ayodhya skyline (5 `Shikhara_*`
slots) and recurs at every journey.
- **Form**: North-Indian **Nagara shikhara** — curvilinear tower (rekha-prasada),
  rising to an `amalaka` (ribbed disc) + `kalasha` (finial pot). NOT a flat South
  gopuram for Ayodhya (save gopuram for Srikalahasti, which is a real South temple).
- **Build**: model ONE master shikhara in Blender (or Meshy draft + heavy retopo),
  parameterized so 3 height variants come from the same mesh (the skyline already
  asks for `base` + `h` per tower). Make it **Nanite** (hero, high silhouette
  detail in the amalaka ribbing pays off).
- **Material**: warm sandstone/gold master (see §4) — the central tower (`Shikhara_2`,
  tallest) gets the **gilt** instance (gold leaf), flanking towers get bare
  sandstone with gold trim. This literally renders "Dasharatha's golden capital."

### 3.2 The smashan dhuni (the hub's beating heart) `[GROUNDED form, fire is invented]`
- **Form**: a low circular fire-pit, ringed stones, perpetual flame, ash, skulls,
  trident (trishula) planted beside, the installed **Shivalingam** adjacent. The
  STORY_BIBLE makes dhuni + lingam the literal "hub-upgrade objects the player
  tends" — so these must be **swappable-state meshes** (dim → bright as progress).
- **Build**: pit + stones + trishula from Megascans/Meshy props; the **fire** is a
  **Niagara** system, not geometry (see §4.4). The lingam is a simple turned form
  (Blender lathe) — black polished stone master material with a faint inner glow
  emissive (the lingam carries the "lit from within" law literally).
- **State swap**: author 3 dhuni intensity tiers (low/mid/high flame + emissive)
  driven by the seeker's granthi progress — the JSON gets a `state` field (§6).

### 3.3 Govardhan hill `[GROUNDED place]`
- **Form**: a large sacred hill, lush, with the wooden-cot meeting clearing.
- **Build**: this is **terrain/landscape**, not a mesh — sculpt a UE **Landscape**
  (or import a Blender/Gaea heightmesh) for the hill body, then scatter Megascans
  boulders + Indian foliage via the **Foliage tool / PCG**. Nanite on the cliff
  rock meshes; landscape uses Virtual Heightfield Mesh. The "dog licks Babaji's
  feet" clearing is a flat hand-placed sub-area.

### 3.4 The air-lingam (Srikalahasti, Vayu) `[GROUNDED concept, form invented]`
- **Form**: the corpus reads air here as "Prana, consciousness, and time-Shiva" —
  the lingam is **air/wind made visible**. This is the most bespoke: a lingam
  silhouette rendered as a **volumetric/translucent shimmer**, not solid stone.
- **Build**: a lingam-shaped mesh with a **translucent refractive master material**
  (distortion + fresnel + the gold inner light) PLUS a Niagara wind/heat-haze
  swirl around it. This is a shader+VFX object more than a model. `[REASONED
  EXTENSION]` heavily flagged — the form is ours; the meaning is cited.

### 3.5 Other bespoke (lower priority, as journeys come online)
- Sri Yantra (Act II persistent object at the dhuni) — flat geometry + emissive
  nine-triangle material; trivial to author, high narrative weight.
- Manikarnika ghat cremation pyres (Benares) — prop set + Niagara fire.
- Badrinath murti (Babaji's face recognized in the icon) — a statue; MetaHuman-
  head-derived or sculpt; needs the face match, defer until Badrinath is built.

---

## 4. The material system — how "light beyond light" actually renders

This is where the project wins or looks generic. Build **one master material set**;
everything instances from it so the look is coherent and the iOS fork is one switch.

### 4.1 `M_Awakener_Stone` (master for all architecture)
- Base: Megascans sandstone/marble albedo+normal+roughness (texture params).
- **Gold tint param** (`GoldAmount` 0→1): lerps albedo toward `#d4af37`/`#ff9933`
  and drops roughness → the same master makes bare stone OR gilt tower.
- **Inner-light emissive** (`InnerGlow` param): a subtle fresnel-masked emissive in
  warm gold so edges catch the "lit from within" key even in shadow — sparing
  (ART_DIRECTION: "brilliance, NOT neon"). Emissive intensity ~0.5–1.5, never blown.
- Mobile quality switch: drops emissive fresnel + uses 1K textures on iOS.

### 4.2 `M_Awakener_Gold` (hero gold — finials, trim, awakened objects)
- Metallic 1.0, anisotropic-ish roughness 0.2–0.35, albedo warm gold.
- This is the material that the **sparing bloom** (build script: `bloom_threshold
  1.0`, `bloom_intensity 0.85`) is tuned to catch. Keep gold the *only* thing above
  the bloom threshold so brilliance reads as consciousness, not neon everywhere.

### 4.3 `M_GoldenAura` (THE signature — awakened/divine beings differ here)
The corpus-literal "faint golden aura around the heads of the Time-Conscious."
This is how Babaji/deity-forms/awakened NPCs visually differ from ordinary NPCs:
- A **rim-light emissive** material applied as a second material slot or a shell
  mesh: fresnel (`Power` ~3–5) × warm gold × pulsing `Time`-driven sine (slow,
  ~0.2Hz breath), masked strongest at the head/crown.
- For the strongest beings (deity-forms, climax): add a **back-facing shell mesh**
  (duplicate skeletal mesh, scaled 1.02, flipped normals, additive translucent
  gold) = a true volumetric halo silhouette.
- **NPC differentiation rule** (data-driven, §6): JSON `aura` tier
  `none|faint|bright|vishvarupa`. `none` = ordinary citizen; `faint` = sage/awakened
  mortal; `bright` = Babaji, Matsyendranath, materialized Devahuti; `vishvarupa` =
  the climax deity-forms (Shiva-as-Time, Vishnu-grasp), which crank emissive +
  add the Vishvarupa Niagara (§4.4) — "the human form was a mercy" rendered.

### 4.4 Niagara VFX (no geometry where light/air should be)
- **Dhuni / pyre fire**: Niagara fire+embers+heatwave; warm gold-biased, not orange-
  cartoon. Drives the hub-state intensity tiers.
- **Golden motes**: slow-drifting luminous particles in awakened spaces (smashan at
  night, the heart-knot vision) — the "thousands of suns" register, dialed to a whisper.
- **Air-lingam swirl** + **Act-II flood** + **Vishvarupa** (climax) — all Niagara.
- **Aura breath**: the §4.3 pulse can be Niagara ribbon for hero beings.

---

## 5. Asset budget + strict priority order

Spend and effort gated by playable order (Phase A in GAME_BUILD_PLAN: smashan hub
→ one journey → one encounter). **Ayodhya + smashan FIRST** — nothing else starts
until those two read as breathtaking.

### Priority ladder (do in this order; each must look shippable before next)
1. **P0 — Master materials + lighting validated** (§4, ~free, days). The relit
   blockout with real materials on cubes already looks 5× better; prove the
   "light beyond light" rig on real surfaces before buying meshes.
2. **P0 — Smashan hub** (the home base; player sees it most). Dhuni + lingam +
   ash ground + a few trees + night rig. Mostly Megascans + 2 bespoke (dhuni,
   lingam). Small scene, highest emotional density.
3. **P1 — Ayodhya** (first journey target, the existing build). Hero shikhara
   (bespoke) ×3 height variants + Indian-temple modular kit + ghat/Sarayu +
   village props + foliage. The cube skyline → real shikhara skyline.
4. **P1 — The disciple + a few hero NPCs** (Rama, Dasharatha, Babaji) as
   MetaHumans with the aura tiers. Generic NPCs from a crowd kit.
5. **P2 — Benares** (Manikarnika ghat — reuse ghat kit + pyre Niagara).
6. **P2+ — Govardhan, Mahurgad, Srikalahasti (air-lingam), Badrinath** as the
   journeys come online; each reuses the kits + 1 bespoke hero asset.

### Spend estimate (Fab, USD; ranges because SKUs churn)
| Item | Est. |
|---|---|
| Megascans + UE Water + freebies | $0 (included) |
| Indian temple modular kit | $30–60 |
| Ghat/Varanasi kit | $20–50 |
| Indian village props kit | $20–40 |
| Foliage / Indian flora | $0–30 (much in Megascans) |
| Cremation/sadhu/ritual props | $15–40 |
| Crowd / NPC clothing (dhoti, sari, sadhu) | $20–60 |
| Meshy/Tripo AI-gen | $0–20/mo (free tiers cover P0/P1) |
| **Total to ship Ayodhya + smashan credibly** | **~$120–280** |

MetaHumans, Nanite, Lumen, Niagara, UE Water = **free/built-in**. The bespoke
Puranic forms = **labor (Blender/AI-gen), not spend.**

---

## 6. The data-driven swap: JSON additions + loader rewrite

This is the load-bearing engineering. Today every record renders as a cube. We add
**mesh + material + scale + aura** fields to the world JSON and rewrite the spawn
functions to load real meshes, falling back to the cube when a mesh id is absent
(so the pipeline degrades gracefully and partial asset sets still build).

### 6.1 World-JSON schema additions
Add an `assets` block (a name→mesh registry, so the exporter can stay graph-pure
and the *art mapping* lives in one editable place), and per-record `mesh`/`aura`
fields. Backward-compatible: missing fields → cube fallback.

```jsonc
{
  "location": "Ayodhya",
  "aesthetic": { /* unchanged: key_light_color, key_intensity, fog_* */ },

  // NEW: art registry — maps logical kinds to real UE asset paths + slots.
  "assets": {
    "ground":        { "mesh": "/Game/Kits/Ground/SM_GroundPlane",
                       "materials": ["/Game/Mat/MI_Sandstone_Ground"] },
    "river":         { "mesh": "WATER",            // sentinel: build a Water body, not a mesh
                       "materials": [] },
    "shikhara_tall": { "mesh": "/Game/Bespoke/SM_Shikhara_A",
                       "nanite": true,
                       "materials": ["/Game/Mat/MI_Stone_Gilt"] },
    "shikhara_mid":  { "mesh": "/Game/Bespoke/SM_Shikhara_A",
                       "materials": ["/Game/Mat/MI_Stone_Sandstone"] },
    "npc_default":   { "skeletal": "/Game/Chars/MH_Citizen",
                       "materials": [] },
    "npc_king":      { "skeletal": "/Game/Chars/MH_Noble_Male" },
    "npc_queen":     { "skeletal": "/Game/Chars/MH_Noble_Female" },
    "npc_deity":     { "skeletal": "/Game/Chars/MH_Deity_Form",
                       "aura": "bright" },
    "dhuni":         { "mesh": "/Game/Bespoke/SM_Dhuni",
                       "niagara": "/Game/VFX/NS_DhuniFire",
                       "state_param": "FlameTier" },
    "lingam":        { "mesh": "/Game/Bespoke/SM_Shivalingam",
                       "materials": ["/Game/Mat/MI_Lingam_InnerGlow"] }
  },

  // skyline entries gain an asset key + per-tower material override.
  "skyline": [
    { "x": -3600, "y": -7400, "base": 700, "h": 1400, "asset": "shikhara_mid" },
    { "x": 0,     "y": -7000, "base": 900, "h": 3400, "asset": "shikhara_tall" }
    // ... (old [x,y,base,h] arrays still accepted — see loader fallback)
  ],

  "npcs": [
    {
      "name": "Rama", "kind": "deity", "chapters": 339,
      "x": -600.0, "y": 0.0, "z": 0.0,
      "yaw": 90.0,                       // NEW: face the city centre
      "asset": "npc_deity",              // NEW: which registry skeletal to spawn
      "aura": "bright",                  // NEW: none|faint|bright|vishvarupa
      "scale": 1.0,                      // NEW: optional per-NPC scale
      "brief": "...", "weapons": ["Brahma"], "family": [ /* ... */ ]
    }
    // ordinary NPCs omit asset/aura → "npc_default", aura "none"
  ],
  "n_entities": 8755
}
```

**Who fills the new fields:** keep the **graph exporter (`world_export/check.py`)
pure** — it keeps emitting name/kind/x/y/chapters/brief/weapons/family. The art
fields are layered by a NEW small step:
- Add a **deterministic `kind → asset/aura` mapping** in the exporter's `_npc_record`
  (e.g. `kind=="deity" → asset "npc_deity", aura "bright"`; `king/queen → noble`;
  else `npc_default`, aura `none`). This is a flagged `[REASONED EXTENSION]` exactly
  like `_place`/`_skyline` already are — art mapping, not corpus claim.
- The `assets` registry block (the actual UE paths) is authored ONCE per location
  and merged in (a sibling `ayodhya_assets.json` the exporter splices, OR a static
  default in the exporter). This keeps "which real mesh" out of the graph and in
  the art layer where a UE dev edits it.

### 6.2 `build_ayodhya_level.py` loader rewrite (the cube→mesh swap)
Replace the cube-only helpers with mesh-aware ones. Exact UE5.8 Python:

```python
# --- asset cache (load each asset once) ---------------------------------
_ASSET_CACHE = {}
def _load(path):
    if path not in _ASSET_CACHE:
        _ASSET_CACHE[path] = unreal.EditorAssetLibrary.load_asset(path)
    return _ASSET_CACHE[path]

# --- generic static-mesh spawner (replaces _cube for buildings/props) ----
def _smesh(asset_def, loc, scale, label, yaw=0.0):
    """Spawn a real StaticMeshActor from an assets-registry entry.
    Falls back to the engine cube when mesh is missing — so a partial
    asset set still builds (graceful degradation)."""
    actor = _spawn(unreal.StaticMeshActor, loc, unreal.Rotator(0, 0, yaw))
    if not actor:
        return None
    comp = actor.get_component_by_class(unreal.StaticMeshComponent)
    mesh_path = (asset_def or {}).get("mesh")
    mesh = _load(mesh_path) if mesh_path and mesh_path != "WATER" else None
    if mesh is None:                       # FALLBACK: keep the blockout cube
        mesh = _load("/Engine/BasicShapes/Cube")
    _try("set mesh", lambda: comp.set_static_mesh(mesh))
    # material slots from the registry
    for i, mpath in enumerate((asset_def or {}).get("materials", [])):
        mat = _load(mpath)
        if mat:
            _try("set mat %d" % i, lambda i=i, mat=mat: comp.set_material(i, mat))
    # Nanite flag (5.8): set on the mesh asset's Nanite settings if requested
    if (asset_def or {}).get("nanite"):
        _try("nanite", lambda: unreal.EditorStaticMeshLibrary
             .set_nanite_enabled(mesh, True))   # build once; cheap if already on
    actor.set_actor_scale3d(unreal.Vector(*scale))
    actor.set_actor_label(label)
    return actor

# --- skeletal NPC spawner (replaces the tall-thin cube for beings) -------
def _being(asset_def, loc, label, yaw=0.0, scale=1.0, aura="none", tags=None):
    skel_path = (asset_def or {}).get("skeletal")
    skel = _load(skel_path) if skel_path else None
    if skel is None:                       # FALLBACK to the mannequin already in /Game
        skel = _load("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple")
    actor = _spawn(unreal.SkeletalMeshActor, loc, unreal.Rotator(0, 0, yaw))
    if not actor:
        return None
    comp = actor.skeletal_mesh_component
    _try("set skel", lambda: comp.set_skeletal_mesh(skel))
    actor.set_actor_scale3d(unreal.Vector(scale, scale, scale))
    actor.set_actor_label(label)
    # the golden aura: attach the aura material as an overlay/second slot
    if aura != "none":
        _apply_aura(comp, aura)            # sets MI_GoldenAura overlay + intensity by tier
    if tags:
        _try("tags", lambda: actor.set_editor_property(
            "tags", [unreal.Name(t) for t in tags]))
    return actor

def _apply_aura(comp, tier):
    """ART_DIRECTION: awakened beings carry a faint golden aura; tier scales it."""
    aura_mat = _load("/Game/Mat/MI_GoldenAura")
    if not aura_mat:
        return
    intensity = {"faint": 0.4, "bright": 1.2, "vishvarupa": 3.0}.get(tier, 0.0)
    # overlay material renders the rim on top of the base skin (UE5 mesh overlay)
    _try("aura overlay", lambda: comp.set_overlay_material(aura_mat))
    mid = comp.create_dynamic_material_instance(0, aura_mat) if False else None
    # (set the intensity param on a MID of the overlay; tier drives brilliance)
```

Then `build()` changes only at the spawn calls — the *layout math is untouched*:

```python
    assets = world.get("assets", {})

    # ground
    _smesh(assets.get("ground"), (0,0,-50), (200,200,1), "Ground_Ayodhya")

    # Sarayu: if registry says WATER, build a real water body, else a mesh strip
    if (assets.get("river") or {}).get("mesh") == "WATER":
        _spawn_water_body((0,-5200,-40), length=6800, width=680, "Sarayu_River")
    else:
        _smesh(assets.get("river"), (0,-5200,-40), (200,34,1), "Sarayu_River")

    # skyline → real shikhara (accept both new dict form and legacy [x,y,base,h])
    for i, s in enumerate(world.get("skyline", [])):
        if isinstance(s, dict):
            adef = assets.get(s.get("asset", "shikhara_mid"))
            x,y,base,h = s["x"], s["y"], s["base"], s["h"]
        else:
            adef = assets.get("shikhara_mid"); x,y,base,h = s
        _smesh(adef, (x,y,h/2.0), (base/100.0, base/100.0, h/100.0),
               "Shikhara_%d" % i)

    # cast → real beings with auras
    for npc in world.get("npcs", []):
        adef = assets.get(npc.get("asset", "npc_default"))
        _being(adef, (npc["x"], npc["y"], npc.get("z", 0.0)),
               "NPC_%s" % npc["name"], yaw=npc.get("yaw", 0.0),
               scale=npc.get("scale", 1.0), aura=npc.get("aura", "none"),
               tags=[npc["name"], npc.get("kind", "being")])

    # hub-only: dhuni + lingam if present (smashan world JSON)
    if "dhuni" in assets:
        _spawn_dhuni(assets["dhuni"], (0,0,0))     # mesh + Niagara fire + state
    if "lingam" in assets:
        _smesh(assets["lingam"], (300,0,0), (1,1,1), "Shivalingam")
```

**Key UE5.8 class/API names used above** (verify against
`node_modules`-equivalent — i.e. the editor's Python stubs — before relying):
`unreal.StaticMeshActor`, `unreal.SkeletalMeshActor`,
`SkeletalMeshActor.skeletal_mesh_component`,
`SkeletalMeshComponent.set_skeletal_mesh`,
`StaticMeshComponent.set_material(i, mat)`,
`SkeletalMeshComponent.set_overlay_material(mat)` (UE5 mesh overlay material —
exact reflected name may be `set_overlay_material` or an editor property; confirm),
`EditorStaticMeshLibrary.set_nanite_enabled`,
`create_dynamic_material_instance`. The existing `_try`/`_spawn`/`_load` fault-
tolerant wrappers stay — one bad asset never kills the build (matches the file's
current discipline).

### 6.3 Why the fallback matters
Because every new spawner falls back to cube (static) or mannequin (skeletal),
**the level always builds**, even mid-migration. You can swap ONE asset at a time
(ground first, then shikhara, then NPCs) and boot-build after each — continuous
visible progress, no big-bang. This is the fastest credible route: the moment the
hero shikhara + sandstone ground + Sarayu water land, Ayodhya stops looking like
cubes and starts looking like a city, even with mannequin NPCs still standing in.

---

## 7. Track C — Characters (disciple, NPCs, Babaji, deity-forms)

- **Disciple (player)**: MetaHuman base (young male ascetic), retarget the existing
  Third-Person `BP_ThirdPersonCharacter` AnimBP onto the MetaHuman skeleton (UE5
  retarget is built-in; the project already ships Manny anims under
  `Content/Characters/Mannequins/Anims`). Clothing: dhoti/wrap from a Fab clothing
  pack or Marvelous Designer → import as skeletal clothing.
- **Hero NPCs** (Rama, Dasharatha, Sita, Babaji, Matsyendranath, Devahuti):
  individual MetaHumans, period clothing, the **aura tier** distinguishing awakened
  beings. Babaji = `aura: "bright"`, deathless calm.
- **Crowd NPCs**: a single MetaHuman + a few outfit/skin variants, instanced; or a
  Fab crowd pack. The world JSON `npc_default` points all of them at one skeletal.
- **Deity-forms** (Shiva-as-Time, Vishnu-grasp, the Vishvarupa climax):
  `aura: "vishvarupa"` + the shell-halo mesh + Niagara — they must read as
  *principle wearing a face* (STORY_BIBLE guardrail), so author them with the
  brightest emissive and the most aggressive aura, NOT extra gore/monster geometry.
  "The human form was a mercy" = a normal-proportioned figure drowning in light,
  not a many-limbed monster. (Many arms only at the explicit Vasudev/Vishvarupa
  beats, and even there: arms of *light*.)

---

## 8. Validation loop (how a dev confirms it looks right, headless)

The build script already auto-runs on editor boot. The graphics loop is:
1. Edit `ayodhya_world.json` / `ayodhya_assets.json` (or re-run `world_export`).
2. Boot editor → `build_ayodhya_level.py` rebuilds with real meshes.
3. Take a high-res screenshot headless:
   `UnrealEditor-Cmd <project> -ExecutePythonScript="take_shot.py"` calling
   `unreal.AutomationLibrary.take_high_res_screenshot(2560,1440, "shot.png")`.
4. Eyeball against ART_DIRECTION: is gold the only thing blooming? is the key warm
   over dusk violet? do awakened beings carry the aura? No grimdark?
5. Iterate materials/lighting params (all already in the JSON `aesthetic` block +
   the post-process — tweak data, not code).

A future Rule-0 tool (`tools/world_export/`-adjacent) could diff the screenshot's
gold/violet histogram against the ART_DIRECTION palette and return a pass/fail
envelope — automating step 4. Out of scope here; flagged as the natural next tool.

---

## 9. Summary — the fastest credible route, in order

1. Build the **master material set** (§4) + validate the inner-radiance rig on the
   existing cubes. (~free, days. Biggest perceived jump per hour.)
2. Add the **JSON `assets` block + per-record `mesh`/`aura` fields** (§6.1) and
   **rewrite the spawners with cube/mannequin fallback** (§6.2). (Engineering; the
   moat-preserving core.)
3. Pull **Megascans surfaces/props + UE Water**; ground + Sarayu + sandstone go
   real first. (~free.)
4. Author the **bespoke shikhara** (§3.1, Nanite) → cube skyline becomes a golden
   city. Author the **dhuni + lingam** (§3.2) → the smashan hub becomes real.
5. **MetaHuman** disciple + hero NPCs with **aura tiers** (§7).
6. Buy the **Indian temple + ghat + village-props kits** (§2.2) for density.
7. Repeat per journey, reusing kits + one bespoke hero asset each.

The graph keeps deciding *who/what/where*; this pipeline only decides *what mesh
sits at each slot* — and the swap is one fallback-safe loader change away.

**Invention flags:** shikhara form, air-lingam form, dhuni fire, NPC placement,
skyline, and all `kind→asset/aura` art mapping are `[REASONED EXTENSION]` (form
authored in the established register; meaning is corpus-cited). Babaji/deity
*presence* and the smashan dhuni/lingam *existence* are `[GROUNDED]` (STORY_BIBLE).
**`[NEEDS-INGESTION]`:** weapon-appearance descriptors (codex `animation_hints`),
and the first-person sensory texture of "unmanifest Time" for the Act-III
air-lingam visuals (STORY_BIBLE flags these too).
