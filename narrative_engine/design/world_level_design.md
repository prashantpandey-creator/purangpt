# THE AWAKENER — World & Level Design

> **Branch:** WORLD / LEVEL DESIGN. This document translates the locked geography of
> `tools/read_pass/STORY_BIBLE.md` (Parts I & IV) into buildable UE5.8 levels: the
> smashan HUB, its progress-driven upgrade objects, the 5 gated journeys, the 3-act
> granthi gating, sacred-landscape AC-style traversal, and the data-driven generation
> path via `tools/world_export/`. It is written so a UE5 dev can execute from it —
> actual UE class names, material params, level layouts, mechanic loops, and the
> exact graph→level data wiring.
>
> Source-of-truth files this design obeys:
> - Story: `tools/read_pass/STORY_BIBLE.md`
> - Art law: `narrative_engine/ART_DIRECTION.md` ("light beyond light")
> - Build phasing: `narrative_engine/GAME_BUILD_PLAN.md`
> - Exporter: `tools/world_export/check.py` + `README.md`
> - Live build script: `/Users/badenath/Documents/Unreal Projects/purangpt/Content/Python/build_ayodhya_level.py`
>
> **Hub-and-spoke, not open world** (bible Part I: "The world is **not** open.").

---

## 0. THE CENTRAL DATA FINDING (read first — it changes the pipeline)

I probed `world_export` against all six game locations + Lanka/Kurukshetra (Rule-0,
JSON-only). **The raw place-resident BFS is WRONG for this game**, and the fix is
the single most important world-system decision in this doc:

| Location queried | `world_export` result | Verdict |
|---|---|---|
| `Smashan` / `Cremation Ground` | success, **0 residents**, cast = `['Smashan']` (echoes the place) | empty — needs a seeded cast |
| `Varanasi` (Benares/Kashi `not_found`) | success, **0 residents**, cast = `['Vārāṇasī']` | empty |
| `Govardhan` | success, cast = **Rama, Sita, Lakshmana, Bharata…** | **WRONG** — that's the *Ramayana* Govardhan/Ayodhya cast, not Guruji's 1995 encounter |
| `Mahurgad`/`Mahur`, `Srikalahasti` | **`not_found`** | not graph place-entities at all |
| `Badrinath` | success, cast = **Pandavas, Kauravas, Dhritarashtra…** | **WRONG** — Mahabharata cast leaked in |
| `Lanka`, `Kurukshetra` | success, **0 residents**, cast = echo | thin (as the brief warned) |

**Why:** `world_export` seeds its cast from a place-entity's *Puranic* residents and
expands by family/guru edges. Our levels are **Sharma-biography locations**, whose
true dramatis personae are the bible's named encounter-beings — and those beings DO
exist as graph nodes (verified): `Mahavatar Babaji`, `Lahiri Mahasaya`,
`Satyacharan Lahiri`, `Shailendra Sharma`, `Hanuman`, `Dattatreya`,
`Matsyendranatha`, `Yama`, `Markandeya`, `Vasudeva`. Better still, **the graph already
knows Sharma's ego-network**: `character_sheet("Shailendra Sharma")` returns
family = `Mahendra` (the dead brother of Act I), other = `Shiva (performs_puja_to)`,
`Gorakhnath (visits)`, `Lahiri Mahasaya (visits)`, `Satyacharan Lahiri (guru_of)`, etc.

### The fix — seed each level on the bible's cast, not the place's residents

Two paths; **build path B**, it's a 12-line, tested change and keeps the exporter the
single source:

- **(A) quick:** drive `world_export` with a hand-authored seed list per level (call
  the library, pass beings as `seeds`). But `run()` has no `seeds` param today.
- **(B) correct — recommended:** add an optional `seeds: list[str] | None = None`
  param to `tools/world_export/check.py::run`. When provided, **skip the
  `location_detail` resident lookup and use `seeds` as the BFS roots** (everything
  downstream — `_assemble_cast`, `_relevance`, `_npc_record`, `_place`, `_skyline`,
  aesthetic — is unchanged and already tested). The `anchor` for `_relevance` becomes
  the union of the seeds' chapters. This makes each level's cast = the bible's named
  beings + their tightly-bound kin, ranked by local salience — exactly the discipline
  the tool already enforces, just rooted correctly. Add one fixture test
  (`test_seeded_cast_overrides_residents`) per Precondition A.

> **✅ STATUS — PATH B LANDED (2026-06-27).** `run()` now takes
> `seeds: list[str] | None = None`. When supplied it skips the place-resident lookup,
> uses `seeds` as the `_assemble_cast` BFS roots, and sets the relevance `anchor` to
> the union of the seeds' chapters (`_chapters`). **Plus:** a `not_found` location is
> no longer a failure *when seeds are given* — the place becomes label-only and the
> cast is 100% the seeds' ego-network, so `Mahurgad` / `Srikalahasti` (which are
> `not_found` graph entities) still emit a buildable `location`/`aesthetic`/`skyline` +
> `npcs` JSON. A `--seeds "A,B,C"` comma-list CLI flag was added to `main()`.
> Verified against the real 8755-entity graph by two new fixture tests in
> `tools/world_export/test_check.py` — `test_seeded_cast_overrides_residents` (Govardhan
> + `["Mahavatar Babaji"]` → Rama/Sita OUT, Babaji IN) and
> `test_not_found_location_with_seeds_still_builds` (Mahurgad + `["Matsyendranatha",
> "Dattatreya"]` → success, cast populated, skyline emitted). Full suite **16/16 green**
> (`venv/bin/python -m tools.world_export.test_check`). The per-level export commands in
> §7.2 are now runnable as written.
>
> ⚠️ **Recovery note for the PR-raising agent:** this whole tree (`narrative_engine/`,
> `tools/world_export/`, ~42 `tools/read_pass/*.py`) was UNTRACKED and got swept by a
> `checkout main ← claude/graph-repair-conflation-fix` mid-task; I restored it from the
> stash (`git checkout 1d12623 -- <path>` for the tracked WIP, `83c1675` for the
> untracked world_export + design docs). The world_export edits + these two tests are
> the PR payload — but they live in the working tree as **untracked** files, so commit
> them (or they vanish on the next branch switch). The auto backup-hook does NOT cover
> `world_export`; a manual tarball is at
> `~/sutradhar-backups/snapshot-moat-recovered-20260627-001135.tar.gz`.

Each level section below lists its **exact seed list** (graph-verified names). Lanka /
Kurukshetra are NOT levels in this game (no Sharma event there); they're noted only to
confirm they're correctly excluded.

---

## 1. WORLD TOPOLOGY — hub-and-spoke, gated by act

```
                         ┌─────────────────────────────┐
                         │      THE SMASHAN  (HUB)      │
                         │  dhuni · Shivalingam ·       │
                         │  Yama's seat · Adi-Shakti    │
                         │  ground · Pampa pond ·       │
                         │  Sri-Yantra dhuni-altar      │
                         └───┬───────┬───────┬──────────┘
        ACT I gate ─────────┘       │       └───────── ACT III gate
        (Brahma-granthi)            │                  (Rudra-granthi)
   ┌──────────┬──────────┐   ACT II gate         ┌──────────────┬──────────────┐
   │ BENARES  │ MAHURGAD │   (Hridaya)           │ SRIKALAHASTI │  BADRINATH   │
   │ Brahma   │ Brahma→  │   ┌──────────┐        │ Rudra/       │  Revelation  │
   │ -granthi │ Vishnu   │   │GOVARDHAN │        │ Muladhar     │  seed        │
   │          │ bridge   │   │ Hridaya  │        │              │              │
   └──────────┴──────────┘   └──────────┘        └──────────────┴──────────────┘
```

- **One persistent streamed level = the hub** (`L_Smashan`), an `ULevel` kept resident
  via World Partition's "always loaded" data layer. The player *always* returns here;
  every knot is pierced here (bible: "Keep the piercing itself at the hub").
- **Five journey levels** are separate `UWorld`s reached from a **single travel object**
  at the hub (the dhuni-side cairn / a path out of the cremation ground). Loading via
  `UGameplayStatics::OpenLevel` or seamless travel; each is small and linear
  (pilgrimage, not sandbox).
- **Gating is by ACT, not by free choice** (§5).

### World Partition / streaming setup (UE5.8)
- Project: enable **World Partition** on `L_Smashan` only; journeys are conventional
  small levels (they don't need partitioning — each is a single bounded pilgrimage).
- **Data Layers** on the hub realize the *upgrade-objects* (§3): `DL_Act1`, `DL_Act2`,
  `DL_Act3`, `DL_HubBase`. Piercing a knot at runtime calls
  `UDataLayerSubsystem::SetDataLayerRuntimeState(DL_ActN, Activated)` to swap the
  dhuni/lingam/sky to their next state without a level reload.
- **One Level Sequence per act-transition** (`LS_Pierce_Brahma`, etc.) plays the
  granthi-break beat, then toggles the data layer at a sequencer event track.

---

## 2. THE SMASHAN — HUB LEVEL (`L_Smashan`)

The most grounded structural decision in the bible: the place you feel safest is the
place the whole game walks you toward. Build it warm, lived-in, and quietly funereal —
**never grimdark** (ART_DIRECTION law). Lit from within; gold = consciousness.

### 2.1 Layout (top-down, world units = cm; origin at the dhuni)

A roughly **120 m × 120 m** sacred clearing on a riverbank, ringed by cremation-ground
landmarks. Eight anchor zones placed on a loose ring so the player orbits the dhuni:

```
                         (N) cremation pyres / ash field
                                    │
   (NW) Pampa pond ──────────┐      │      ┌────────── (NE) Yama's seat
   (golden Varaha at bottom) │      │      │           (buffalo-skull throne,
                             │   ┌──┴──┐   │            the journey gatekeeper)
                             │   │DHUNI│   │
   (W) Adi-Shakti ground ────┤   │ +   ├───┤──── (E) installed SHIVALINGAM
   (stone yoni/breast/navel, │   │lingam│   │      (player-tended; grows per knot)
    menstruating trees)      │   └──┬──┘   │
                             │      │      │
   (SW) Satyacharan's        └──────┤──────┘ (SE) Sri-Yantra altar
        subtle-body spot            │           (appears Act II; heart-interface)
                                    │
                         (S) the path OUT  ──►  journey-travel cairn
                                    │
                              (river edge: the smashan's water)
```

### 2.2 Anchor objects — concrete UE actors

| Zone | Actor / Blueprint | Build notes |
|---|---|---|
| **Dhuni (sacred fire)** | `BP_Dhuni` — Niagara fire + light + interactable | The hub-upgrade object. See §3.1. Center of map; warm gold key bounces off it (Lumen). |
| **Shivalingam** | `BP_Shivalingam` — static mesh + emissive aura | Player-tended upgrade object. See §3.2. **[GROUNDED — bio L116, L241]** |
| **Yama's seat** | `BP_YamaSeat` — buffalo-skull throne, the *gatekeeper* | Interact = open the journey-select. Death entrusts the ground (bio L355/L358). Black-buffalo silhouette ambient. **[GROUNDED]** |
| **Adi-Shakti ground** | sculpted terrain + `SM_StoneYoni`, `SM_StoneBreast`, `SM_StoneNavel` | "trees menstruate" — a Niagara drip of deep-red sap on `SM_Tree_Smashan` (use imagery EXACTLY; do not soften — bible). **[GROUNDED — bio L82, L84]** |
| **Pampa pond** | `BP_PampaPond` — water plane + submerged `SM_GoldVaraha` | Worshipped as Pampa Sarovar (Parvati). Golden Varaha glints at the bottom under the water material. **[GROUNDED — bio L347]** |
| **Satyacharan's spot** | `BP_SubtleBodyAnchor` (Satyacharan) | The dead guru returns in subtle body (1993). Spawns a translucent, rim-lit figure between journeys (§4 lineage presence). **[GROUNDED]** |
| **Sri-Yantra altar** | `BP_SriYantraAltar` — appears Act II | Persistent object at the dhuni after Govardhan; the **heart-center interface** (nine-triangle biofeedback puzzle, bible Act II Beat 2 & 6). Hidden in `DL_Act2`. **[GROUNDED — bio L112, L121]** |
| **Cremation pyres / ash field** | instanced `SM_Pyre` + ash decal + ember Niagara | Ambient. At the ending, the *last image*: ash at dawn, rudraksha trees (§3.3). |

### 2.3 Ambient guardians (not walls — bible: "Ambient guardians, not walls")
The hub is bounded by *presence*, not collision walls:
- **`BP_BhairavaDog`** — wandering black dogs (the guards' "Bhairava's patrol"). 3–4
  AI pawns on a `BTT` wander; they rhyme with Babaji's dog at Govardhan (Act II Beat 1).
  **[GROUNDED — bio L96, L263]**
- **`BP_RedDressGuardian`** — astral woman in a red Rajasthan dress; on a scripted
  trigger she garlands the disciple with jasmine (`SM_JasmineGarland` attach + Niagara
  petals) and vanishes (`Destroy` after a Level Sequence). One-shot per act.
  **[GROUNDED — bio L126]**
- **Soft boundary:** the river on one side, dense `SM_Tree_Smashan` + an invisible
  `ABlockingVolume` ring elsewhere, dressed so the wall is never *read* as a wall.

### 2.4 Hub lighting (inherit `build_ayodhya_level.py` exactly)
Reuse the shipped rig verbatim — it already encodes ART_DIRECTION:
- `DirectionalLight` "InnerSun_GoldKey", color `[1.0, 0.81, 0.46]`, intensity `6.0`,
  rot `(-40,-55,0)`, `atmosphere_sun_light = True`.
- `SkyAtmosphere` "SkyAtmosphere_Dawn", `SkyLight` "SkyLight_WarmFill".
- `ExponentialHeightFog` "Fog_VioletUmber": `fog_inscattering_color [0.5,0.32,0.5]`,
  `fog_density 0.02`, `fog_height_falloff 0.12`, `volumetric_fog True`.
- `PostProcessVolume` "PP_LightBeyondLight": Lumen GI + reflections, `bloom_intensity
  0.85` / `bloom_threshold 1.0` (brilliance, not neon), `white_temp 5200`, warm
  `color_gain (1.06,1.0,0.9,1)`, `vignette 0.35`.
- **Hub-specific override:** push the fog one notch deeper-violet at night beats and
  let the **dhuni** be a real `BP` point/area light so the gold reads as coming *from
  the fire and from within beings*, not the sky. This is the "lit from WITHIN" law.

---

## 3. UPGRADE-OBJECTS — the hub visibly changes per knot pierced

The bible's literal hub-upgrade record: *"the player tends them as the visible record
of progress."* Three knots → three visible state-changes, each driven by a Data Layer
swap + a material parameter the engine sets from the seeker's granthi state.

### 3.1 The Dhuni — `BP_Dhuni` (4 states)
A single Niagara system + a `MaterialParameterCollection` (`MPC_Dhuni`) the engine
writes. State driven by `seeker.granthis_pierced` (0→3).

| State | Knot | Niagara / material change | Corpus tie |
|---|---|---|---|
| `0 — Ember` | none | Low, smoky, dim embers. `FireScale 0.4`, `Color (1.0,0.55,0.2)` (warm but small) | The Aghora dhuni the disciple is learning to tend. |
| `1 — Steady` | Brahma pierced | Taller flame, less smoke, first gold tips. `FireScale 0.7`, `Color (1.0,0.7,0.35)` | Khechari "halts decay"; body becomes a finer instrument. |
| `2 — Gold` | Hridaya pierced | Flame goes *gold-from-within*, faint heat-shimmer halo. `FireScale 1.0`, `Color (1.0,0.81,0.46)` (the key-light gold), bloom up | Vasudev resident in the heart; "a room in the chest." |
| `3 — White` | Rudra pierced | "Flame of all flames, color of the sun" — near-white core, light intensity 2× , the whole clearing lifts toward radiance | ART_DIRECTION: "unbearable brilliance of Time… thousands of suns." **[GROUNDED]** |

- Implementation: `BP_Dhuni::SetGranthiState(int N)` sets `MPC_Dhuni.FireScale/Color`
  and the child `PointLight` intensity; a 2 s `Timeline` lerps so the change reads as a
  *kindling*, not a pop. Called from the granthi-break Level Sequence.

### 3.2 The Shivalingam — `BP_Shivalingam` (player-tended, grows per knot)
- Mesh `SM_Shivalingam`; an emissive aura plane (`M_Aura_Gold`, scalar `AuraRadius`)
  that **widens** each knot: `0.0 → 0.4 → 0.7 → 1.0`. At state 3 the lingam reads as
  the air-/time-lingam (Srikalahasti callback): a faint vertical light-column
  (`Niagara_LightColumn`) rises from it.
- **Tending interaction** (`BP_Shivalingam::Tend`): the daily/return ritual — pour
  water (`Niagara_WaterRibbon`), the aura pulses once. Cheap, tactile, slow — the
  hub's "you live here" verb. The aura's *current* radius is the visible progress bar.

### 3.3 Generative set-dressing that grows with the story
- **Rudraksha trees** — `BP_RudrakshaTree`. Per bible Act II Beat 5, Shiva's footprints
  grow rudraksha. After the Vishnu-grab/Shiva-rescue set-piece, **spawn a small grove**
  on the footprint trail (a spline of `SM_Footprint` decals → `SM_RudrakshaTree`
  instances). The disciple's worn rudraksha is *loot with theology* — it literally grew
  here. At the ending, this grove is the **last image** (ash at dawn + the trees).
- **The Yamuna flood scar** — after the same set-piece, a persistent shallow-water
  decal + reeds where Shiva's flood receded (`DL_Act2` dressing).

> **Design contract:** the hub is a save-state diorama. A first-time player and an
> Act-III player stand in *visibly different* smashans, and every difference is a
> grounded corpus event, not a cosmetic unlock.

---

## 4. THE FIVE JOURNEY LEVELS

Each journey is a **short, linear pilgrimage** (10–20 min) delivering ONE named
encounter and feeding ONE knot. Encounters obey the bible's three registers —
**Told → Glimpsed → Beheld** — and the "reward" is always a *shift in perception*,
never loot (Part IV rule). Each level's cast is generated by **seeded `world_export`**
(§0 path B); seed lists are graph-verified.

For every journey: **the climb IS the practice** (§6 traversal). You ascend toward the
encounter; the vertical gain *is* the consciousness ascent, literal and spatial.

---

### 4.1 BENARES / KASHI — `L_Benares` → feeds **Brahma-granthi** (Act I)
**Real event:** Babaji met in person, 2 AM, 1 Apr 1988, Benares ashram; Lahiri's house;
Kashi Vishwanath; Manikarnika ghat. **[GROUNDED — bio L104]**

- **Look:** the **ghats of the Ganga at pre-dawn**, stepped stone descending to water,
  cremation smoke at Manikarnika, narrow lanes climbing to Kashi Vishwanath. Warm
  lamp-gold against blue-violet 2 AM dusk (ART_DIRECTION palette exactly: gold key,
  violet ground). The river carries the light (cf. Sarayu rule).
- **Play:** a night ascent through the lanes to the ashram door. The **2 AM door** is
  the threshold; Babaji is **Glimpsed** — a knock, a voice, the Kriya instruction
  *received secondhand* (POV discipline). Lahiri's house is a **Beheld** micro-beat:
  the marble-statue-turns-to-flesh moment (Part IV: "The Marble That Turned to Flesh").
- **Knot fed:** Brahma — this is the *true initiation* signpost (the in-person
  transmission that ignites Act I's loop).
- **`world_export` seeds:** `["Mahavatar Babaji", "Lahiri Mahasaya", "Shiva"]`
  (Benares/Kashi are `not_found` as place-entities — query `Varanasi` only for the
  river/ambient skyline, then **override the cast with these seeds**).
- **Skyline:** reuse `_skyline()` but tune to **ghat-tier + temple shikhara** (low
  wide steps cresting to Kashi Vishwanath's gold spire at center). Flag
  `[REASONED EXTENSION]`.

### 4.2 MAHURGAD (MAHUR) — `L_Mahurgad` → **Brahma→Vishnu bridge** (Act I→II)
**Real event:** Matsyendranath gives kundalas + dhuni/sadhana instructions; Dattatreya
as an old beggar at the noon break. **[GROUNDED]**

- **Look:** a **hill-fort temple-shrine** (Mahur is a Shakti-pith hill). Noon light —
  the one *bright* journey; warm white-gold midday, short shadows. Dattatreya's
  three-headed motif in the shrine carving.
- **Play:** a **switchback climb** up the hill (traversal = the Nath transmission you're
  ascending toward). At the noon break, the **beggar (Dattatreya, Glimpsed)** sits;
  speak and he's gone. At the summit shrine, **Matsyendranath** pats the head and gives
  the **kundalas** (`SM_Kundala` — earrings; the *technique that makes the knots
  piercable*, bible). This is "benediction, never a reward drop" — render it as a
  *perception shift* (the world briefly gold-rimmed), not an item pickup.
- **Knot fed:** the bridge — equips the practice that lets the heart-knot be approached.
- **`world_export` seeds:** `["Matsyendranatha", "Dattatreya", "Shailendra Sharma"]`
  (Mahur/Mahurgad `not_found` → seed-override mandatory).

### 4.3 GOVARDHAN — `L_Govardhan` → **Hridaya-granthi** (Act II, emotional setup)
**Real event:** 2nd physical Babaji meeting, late Dec 1995 (wooden cot, a dog licks his
feet); dead sister **Devahuti materializes**; **Dattatreya's** three-headed nightly
route. **[GROUNDED — bio L115, L120, L153]**

- **Look:** **Govardhan hill at dusk** — the lifted-hill silhouette, Yamuna nearby,
  pastoral but charged. The act "relocates entirely to the smashan at Govardhan" — so
  this level is a **second, softer cremation-clearing** on the hill, a garden growing
  in a death-ground (bible Beat 4: "a garden growing inside the death-ground").
- **Play:** the act's **one moment of plain warmth** — **Babaji on a wooden cot**
  (`BP_Babaji_Cot`), a dog (`BP_BhairavaDog` reused) licks his feet; low camera, NO
  combat. Then the **Devahuti materialization** (Glimpsed, devastating) — the dead
  sister fully embodied. The level is a *tension descent*, not a fight.
- **Critical do-not-collapse (bible):** Govardhan supplies the *emotional* setup; the
  **actual heart-knot vision (Vasudev) is a smashan-night event** — pierce it at the
  HUB, not here. This level *delivers the Sri-Yantra hand-off* that then lives at the
  hub dhuni.
- **`world_export` seeds:** `["Mahavatar Babaji", "Devahuti", "Dattatreya"]`.
  ⚠️ **`Devahuti` is NOT in the graph** (verified: 0 hits). **[NEEDS-INGESTION]** — the
  sister's node must be added (kept *deliberately un-merged* from the Puranic
  Devahuti/Kapila's-mother per the bible's identity-merge guardrail). Until then,
  hand-author her actor; do not let `world_export` substitute the Puranic Devahuti.
  Raw `Govardhan` query returns the **Ramayana cast** — must be overridden.

### 4.4 SRIKALAHASTI — `L_Srikalahasti` → **Rudra/Muladhar-granthi** (Act III)
**Real event:** meditated at the **air-lingam (Vayu)**; air read as *"Prana,
consciousness, and time-Shiva."* **[GROUNDED — bio L151]**

- **Look:** a **South-Indian gopuram temple** with an inner sanctum holding the
  **air-lingam** — a lingam with a perpetually flickering lamp (the air is alive). The
  one beat where the palette **cools toward the terrible**: gold thinning, the
  violet-umber ground rising, a faint un-warm white. This is the on-ramp to mysterium
  tremendum — do not make it pretty.
- **Play:** descend INTO the sanctum (this journey *descends* — Act III is "a descent
  the player mistook for an ascent"). Hold the breath at the air-lingam; the **flame
  bends without wind** (Niagara wind-vector with no wind source) — *Time perceived
  through the breath*. **Beheld:** the lingam briefly loses form (callback to the hub
  Omkar trial). **[NEEDS-INGESTION]** — first-person sensory texture of "unmanifest
  Time" (bible Act III note); placeholder VFX until decoded.
- **`world_export` seeds:** `["Shiva", "Shailendra Sharma"]` (Srikalahasti
  `not_found` → seed-override). Shiva = Kāl/Time is the referent.

### 4.5 BADRINATH — `L_Badrinath` → **The Revelation seed** (Act III rehearsal)
**Real event:** recognizes **Babaji's face/energy in the murti**; the blessing crone =
**Adi Shakti in disguise.** **[GROUNDED]**

- **Look:** **high-Himalayan temple**, snow and thin gold light, the Alaknanda below.
  The thinnest air, the highest climb of the game (the literal summit of the spatial
  ascent §6). Cold white + a single warm shrine-gold interior.
- **Play:** the **rehearsal for "the small form was a mercy."** At the murti, the
  disciple sees **Babaji's face inside the icon** (Beheld) — the guru hidden in the
  statue. A **crone** blesses him on the path (Glimpsed → later understood as Adi
  Shakti). Plants the Revelation: *the small form is a door.*
- **`world_export` seeds:** `["Mahavatar Babaji", "Adi Shakti", "Shiva"]`. Raw
  `Badrinath` query returns the **Mahabharata cast** — must be overridden. (`Adi Shakti`
  graph presence to be confirmed; fallback seed `["Mahavatar Babaji","Shiva"]` +
  hand-authored crone if absent — **[NEEDS-INGESTION]** for the Adi-Shakti node.)

> **Lanka / Kurukshetra are correctly NOT levels** — no Sharma event occurs there and
> their graph casts are thin/echo. The brief's caution holds: were they ever needed,
> they'd be hand-authored, not exporter-driven. Excluded by design.

---

## 5. ACT GATING — how the three granthi-acts open the spokes

Gating is **structural, enforced by the named-practice spine** (bible: "The structure
enforces itself" — no grindable meter). Acquisition of the *journey's named practice*
is the key, not a level number.

| Act | Knot | Journeys UNLOCKED | Gate mechanism (engine) |
|---|---|---|---|
| **I** | Brahma (matter) | **Benares**, **Mahurgad** | From game start. Yama's-seat journey-select shows only these two. Pierce requires khechari + prana/apana practice complete (hub trial). |
| **II** | Hridaya (heart) | **Govardhan** | Unlocks only after Brahma pierced AND the Sri-Yantra arrives. Heart-knot pierced at the **hub** (Sri-Yantra biofeedback), not Govardhan. |
| **III** | Rudra (time) | **Srikalahasti**, **Badrinath** | Unlocks only after Hridaya pierced AND the 57th-birthday Omkar practice is *assigned* (the locked sadhana-log entry). |

### Engine wiring (uses the existing `seeker` module — `GAME_BUILD_PLAN.md`)
- `seeker.granthis_pierced: int (0..3)` and `seeker.practices_acquired: set[str]`
  gate the **journey-select menu** at `BP_YamaSeat`. A spoke is offered iff
  `act_of(spoke) <= current_act AND prerequisite_practice in practices_acquired`.
- **Travel is the gate, not a wall:** the path-out cairn is always physically present;
  selecting a locked journey gives the narrator's one-degree-cooler line ("the road is
  not yet yours"), never a hard error. Reverent, in-fiction.
- **Data layers** carry the act state into the *hub's own geometry* (§1): entering Act
  II activates `DL_Act2` (Sri-Yantra altar, the garden encroaching on the death-ground);
  Act III activates `DL_Act3` (the cooling palette, the assigned-practice altar).

---

## 6. TRAVERSAL — AC-grade, fitted to a SACRED landscape

The brief's hardest constraint: AC-style parkour/climb/exploration that is **the
consciousness ascent as literal vertical/spatial climb — NOT rooftops-and-haystacks
reskinned.** The whole movement grammar is re-themed so *to climb is to ascend the
granthis.*

### 6.1 The re-theme (every AC verb → a sacred verb)
| AC verb | Awakener verb | Where it reads as the ascent |
|---|---|---|
| Climb a tower / synchronize viewpoint | **Ascend to a darshan-point** | Each journey ends ON a height (ashram door, hill shrine, Govardhan crest, gopuram tier, Himalayan murti). The "viewpoint" reveal is the *encounter*, not a map unveil. |
| Parkour across rooftops | **Pilgrim's path / ghat-steps / switchbacks** | Hand-placed climbable geometry: ghat stairs (Benares), fort switchbacks (Mahur), temple gopuram ledges (Srikalahasti), Himalayan ledges (Badrinath). |
| Leap of faith (haystack) | **Surrender-drop into water/ash** | Into the Ganga at Benares, into the Pampa pond at the hub, into ash. Themed as *letting go* (Act II's "endure, don't force" lesson made kinetic). |
| Eagle vision | **Beheld-sight** (gated) | A rare, gated perception mode unlocked per knot: awakened senses briefly gold-rim sacred beings/objects (corpus-literal aura). NOT an always-on detective mode. |
| Free-running flow | **Breath-paced movement** | Sprint/climb stamina is *breath* (ties to the prana/apana Act-I skill). Holding breath (khechari state) steadies a hard climb beat. |

### 6.2 Vertical = the knots (the spine of the traversal design)
- **Each journey's altitude profile encodes its knot.** Acts I–II journeys **ascend**
  (Brahma/Hridaya = rising). Act III's **Srikalahasti DESCENDS into the sanctum** and
  **Badrinath is the highest summit** — the bible's "descent the player mistook for an
  ascent" rendered as level geometry: you think you keep climbing, but the final truth
  is *underground/inward* at Srikalahasti, then *thin-air-fatal* at Badrinath.
- **Climb difficulty rises with the act**, but never as twitch-platforming — it's
  *endurance* (breath/stamina), matching the bible's austerity register.

### 6.3 UE implementation
- **Character:** `ACharacter` + a custom `UAwakenerMovementComponent` (subclass
  `UCharacterMovementComponent`) adding climb/ledge-hang/mantle states. Use UE5.8
  **Motion Matching** (the `PoseSearch` plugin) for the AC-grade traversal feel; a
  climbing locomotion database keyed to ledge tags.
- **Climbable geometry tagging:** authored `ledge` / `handhold` spline components
  (`USplineComponent` tagged `Climbable`) on ghat/fort/temple meshes — *hand-placed*,
  because sacred architecture must read as designed, not procedurally littered. (This
  is why journeys are hand-built shells even though the *cast* is data-driven.)
- **Breath-stamina:** a `UFloatProperty Breath` on the movement component drains on
  sprint/climb, refills on stillness; the khechari state (Act I) caps the drain. Wire to
  the same `seeker` breath skill used in the hub trials.
- **Beheld-sight:** a post-process material (`PPM_BeheldSight`) toggled by a granthi-
  gated input; rim-lights actors tagged `Sacred` in gold (reuse `M_Aura_Gold`).

---

## 7. DATA-DRIVEN GENERATION — how each level is built from the graph

The pipeline already exists (`world_export` → `ayodhya_world.json` →
`build_ayodhya_level.py`). This section maps every level onto it and specifies the
exact extensions.

### 7.1 The pipeline (unchanged spine)
```
graph_manifest.json  ──world_export(location, seeds)──►  <level>_world.json
        │                                                       │
        └────────── verified 8755-entity graph                  ▼
                                          build_<level>_level.py (UE python)
                                          → cubes/actors + light-beyond-light rig
```

### 7.2 Per-level export commands (✅ §0 path-B `seeds` param landed 2026-06-27 — runnable as-is)
```bash
# HUB — seed on Sharma's ego-network (NOT the empty 'Smashan' residents)
venv/bin/python -m tools.world_export.check --location "Smashan" \
  --seeds "Shailendra Sharma,Mahavatar Babaji,Satyacharan Lahiri,Yama,Shiva,Hanuman" \
  --write "/Users/badenath/Documents/Unreal Projects/purangpt/Content/smashan_world.json"

# BENARES
... --location "Varanasi" --seeds "Mahavatar Babaji,Lahiri Mahasaya,Shiva" --write .../benares_world.json
# MAHURGAD (place not_found → location is a label only; cast is 100% seeds)
... --location "Mahurgad" --seeds "Matsyendranatha,Dattatreya,Shailendra Sharma" --write .../mahurgad_world.json
# GOVARDHAN  (⚠ override the Ramayana default)
... --location "Govardhan" --seeds "Mahavatar Babaji,Dattatreya" --write .../govardhan_world.json
# SRIKALAHASTI
... --location "Srikalahasti" --seeds "Shiva,Shailendra Sharma" --write .../srikalahasti_world.json
# BADRINATH  (⚠ override the Mahabharata default)
... --location "Badrinath" --seeds "Mahavatar Babaji,Shiva" --write .../badrinath_world.json
```
*(`--seeds` is a comma-list CLI flag added to `main()` alongside the `run(seeds=…)`
param. When `--location` is `not_found`, the seeds become the entire cast and the
`location`/`aesthetic`/`skyline` are still emitted — so a non-graph place like Mahurgad
still produces a valid level JSON.)*

### 7.3 Extend the world JSON schema for levels (additive, back-compatible)
`build_ayodhya_level.py` consumes `{location, aesthetic, skyline, npcs[], n_entities}`.
Add **optional** fields the per-level build scripts read; old data still builds:
- `"landmarks": [{ "type": "dhuni|lingam|yama_seat|pond|ghat|gopuram|murti|cot",
  "x","y","z", "state_layer": "DL_Act2"|null }]` — the §2/§3 anchor objects, so the hub
  and journeys place their *sacred set-dressing* data-driven too (not just NPC cubes).
- `"altitude_profile": [[dist, height], …]` — the §6.2 climb spine (ascend vs descend).
- `"palette_shift": "warm|cooling|cold"` — Act-III levels (Srikalahasti/Badrinath)
  flag the cooling register so the build script biases fog/grade toward the terrible.
These are **[REASONED EXTENSION]** (placement/landmark layout), flagged as such in the
JSON `aesthetic.note`, same discipline as the existing skyline.

### 7.4 Build scripts (one per level, forked from the Ayodhya one)
`build_<level>_level.py` = copy of `build_ayodhya_level.py` with:
- `DATA = <level>_world.json`.
- the `_landmarks()` pass (new) that spawns the §2/§3 `BP_*` actors from
  `world["landmarks"]` by `type` → Blueprint class map.
- the `palette_shift` hook that nudges fog/grade for Act-III cooling.
- the cast loop **unchanged** (it already labels + tags actors by real graph name).
- **All set-dressing geometry placement is `[REASONED EXTENSION]`** (the graph asserts
  *who/where-in-the-corpus*, not the meter-precise layout) — flag in logs exactly as
  the skyline already is.

### 7.5 Tests (Precondition A — required before trusting any level export)
- `world_export/test_check.py`: add `test_seeded_cast_overrides_residents` (seed
  Govardhan with `["Mahavatar Babaji"]` → assert Rama/Sita are NOT in the cast and
  Babaji IS), and `test_not_found_location_with_seeds_still_builds` (Mahurgad + seeds →
  `success=True`, npcs from seeds, valid `location`/`skyline`). Lock against the real
  8755-entity graph (already loaded once, shared), per the tool's existing pattern.

---

## 8. BUILD ORDER (fits `GAME_BUILD_PLAN.md` Phase A→B)

1. **Land the `seeds=` param + tests** in `world_export` (§0 path B, §7.5). ~12 LOC +
   2 tests. *This unblocks every level.* Without it, Govardhan/Badrinath build the WRONG
   cast.
2. **Build the HUB shell** (`L_Smashan`) with the §2 layout, reusing the shipped
   Ayodhya lighting rig. Seed its cast (§7.2). This is the playable core (bible: "the
   piercing itself stays at the hub").
3. **Wire the 3 upgrade-objects** (§3) to `seeker.granthis_pierced` via data-layer
   swaps. Prove the hub *visibly changes* (Phase-A "one act end to end").
4. **Build Benares + Mahurgad** (Act I spokes) data-driven (§4.1/4.2, §7). One full
   loop: hub → journey → encounter → practice → pierce.
5. **Traversal vertical slice** (§6) on Benares ghats — the AC-grade climb proving the
   sacred re-theme reads.
6. **Govardhan + the Sri-Yantra hand-off** (Act II), then Srikalahasti + Badrinath
   (Act III). Govardhan needs the **Devahuti node ingested** first (§4.3 NEEDS-INGESTION).

---

## 9. [NEEDS-INGESTION] / [INVENTED] LEDGER (this branch's seams)

- **[NEEDS-INGESTION] Devahuti node** — Guruji's sister is absent from the graph (0
  hits). Required for Govardhan's cast; must be added *un-merged* from the Puranic
  Devahuti (bible identity-merge guardrail). Until then, hand-author her actor.
- **[NEEDS-INGESTION] Adi Shakti graph node** — needed as a Badrinath/hub seed;
  presence unconfirmed. Fallback to hand-authored crone + Shiva seed.
- **[NEEDS-INGESTION] place-entities** Benares/Kashi, Mahur/Mahurgad, Srikalahasti are
  NOT in the graph (`not_found`) — fine for cast (seed-driven) but their *ambient
  Puranic lore* (Manikarnika, the Mahur Shakti-pith, the air-lingam backstory) is
  unsourced; flag any environmental narration as placeholder (bible Part V item 7).
- **[REASONED EXTENSION]** ALL level layouts, landmark placements, skylines, altitude
  profiles, and climbable-geometry routes — the graph asserts *who and what corpus-event*,
  never meter-precise architecture. Flagged in each build script's logs + the JSON
  `aesthetic.note`, exactly as the Ayodhya skyline already is.
- **[GROUNDED]** every encounter, every landmark's *existence/meaning*, every upgrade-
  object state, and every cast member (traced to bio line-refs and graph nodes cited
  inline above).

> **The world-design vow (mirrors the bible's core thesis):** we invent the *shell*
> (and flag it), never the *inhabitants or events*. The cast of every level is the
> verified graph; the geography is the recorded life; the only fiction is the meter-
> precise stone — and we mark every seam.
