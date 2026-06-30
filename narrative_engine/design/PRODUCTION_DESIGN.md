# THE AWAKENER — PRODUCTION DESIGN

> The unifier of the four execution branches (`graphics_pipeline.md`,
> `shaders_rendering.md`, `world_level_design.md`, `combat_system.md`). This is the
> single buildable spine: what we build, in what order, and how the four systems
> interlock on top of the one fact that already ships — `build_ayodhya_level.py`
> boots, auto-runs, and builds a level from graph data via `tools/world_export/`.
>
> Sources of truth (obey, do not re-derive): `tools/read_pass/STORY_BIBLE.md`,
> `narrative_engine/ART_DIRECTION.md`, `narrative_engine/GAME_BUILD_PLAN.md`,
> `narrative_engine/combat.py`, `tools/world_export/`,
> `"/Users/badenath/Documents/Unreal Projects/purangpt/Content/Python/build_ayodhya_level.py"`.

---

## 1. The unified build vision (3 sentences)

THE AWAKENER is a hub-and-spoke, AC-grade pilgrimage in the Puranic world — a
disciple walking back toward his guru — where a verified 8,755-entity knowledge
graph keeps deciding *who, what, and where* at every slot, and the only thing the
art pipeline changes is *what mesh, material, and aura sits at that slot*. Every
level is generated from graph data into a world JSON and built by an auto-running
UE5.8 Python script, so the entire game is a **data-driven swap, not a hand-rebuild**:
cubes become real meshes, the flat key becomes "light beyond light," and the empty
place-residents become the bible's true cast — each a small, fallback-safe change
that leaves the level always buildable. Combat is two verbs (the rare AC **Duel**
and the endure-don't-kill **Vigil**) resolved by `combat.py`'s rulebook through a
JSON-contract tool, so the moat — every weapon, being, and beat traces to decoded
corpus or is flagged invented — holds from the graph all the way to the screen.

---

## 2. How the four branches interlock (the dependency order)

The four branches are not parallel tracks — they are **one stack with a strict
bottom-up dependency**. Each layer is useless or wrong until the one below it lands.

```
        ┌─────────────────────────────────────────────────────────────┐
        │  COMBAT (combat_system)                                       │
        │  Duel + Vigil + astra rulebook → needs BEINGS to fight/endure │
        └───────────────▲─────────────────────────────────────────────┘
                        │ needs cast + aura'd beings + a place to stand
        ┌───────────────┴─────────────────────────────────────────────┐
        │  WORLD (world_level_design)                                   │
        │  seeded cast + hub/journey layout + act gating + traversal    │
        │  → decides WHO/WHAT/WHERE per level                           │
        └───────────────▲─────────────────────────────────────────────┘
                        │ needs each slot to render as a real mesh/being
        ┌───────────────┴─────────────────────────────────────────────┐
        │  GRAPHICS (graphics_pipeline)                                 │
        │  JSON assets-block + mesh/aura fields + spawner rewrite        │
        │  → swaps cube→mesh, mannequin→being, with cube/mannequin       │
        │     FALLBACK so the level always builds                        │
        └───────────────▲─────────────────────────────────────────────┘
                        │ needs surfaces that embody "light beyond light"
        ┌───────────────┴─────────────────────────────────────────────┐
        │  SHADERS (shaders_rendering)                                  │
        │  master materials + lighting rig + golden-aura + Terror PP     │
        │  → makes the inner-radiance LAW physically true at 60fps/M1    │
        └───────────────────────────────────────────────────────────────┘
                  ↑ all four sit on the ONE shipped fact:
            build_ayodhya_level.py boots, auto-builds from world JSON,
            world_export turns any graph LOCATION into that JSON.
```

The four hand-offs, concretely:

- **SHADERS → GRAPHICS.** Graphics' spawner rewrite is pointless if the materials it
  assigns are generic. The `M_FX_GoldenAuraRim`/`Shell` (shaders §2.5) is the exact
  material the graphics `_apply_aura()` helper (graphics §6.2) loads; the
  `M_Awakener_Stone`/`Gold`/`Water` (graphics §4 = shaders §2.1/2.2/2.6, same
  materials named twice) are what the rewritten `_smesh()` assigns per registry slot.
  **Build shaders' aura + lighting rig FIRST** — it's near-free, needs no new geometry,
  and proves the whole art direction on the existing cubes (both branches independently
  ranked it P0).
- **GRAPHICS → WORLD.** World's per-level JSON needs the schema graphics defines: the
  `assets` registry block + per-record `mesh`/`aura`/`yaw`/`scale` (graphics §6.1) is
  the SAME additive, back-compatible schema world extends with `landmarks`/
  `altitude_profile`/`palette_shift` (world §7.3). One schema, two contributors —
  graphics owns *what mesh*, world owns *what sacred landmark / climb / palette*. The
  cube/mannequin fallback (graphics §6.3) is what lets world stand up a journey before
  its bespoke hero asset exists.
- **WORLD → COMBAT.** Combat's Duel needs an asuric foe to strike and its Vigil needs
  a divine being to endure — both are **graph cast members the seeded exporter places**
  (world §0 path B). A Vishvarupa/aura'd Babaji (graphics aura tier + shaders shell) is
  the being the climax Trial (combat §8) is staged against. Combat cannot be authored
  for a level until that level's *cast* is correct — which is world's load-bearing
  `seeds=` fix (without it Govardhan fights the Ramayana cast).
- **COMBAT ↔ SHADERS (the climax loop closes the stack).** Combat's climax Trial
  (combat §8, "do not flinch") IS shaders' single-knob `Terror`/`M_PP_Vishvarupa`
  stack (shaders §3.3) — the arms dissolving into light, the bleach to white, Babaji
  stencil-masked out. The combat rulebook decides the *outcome string*; the shader
  decides the *look of that outcome*. Neither invents; both read the same beat.

**The one cross-cutting engineering contract** all four obey (workspace Rule 0): the
two new `tools/` scripts — `world_export` gains `seeds=` (world §0/§7.5) and a new
`tools/combat_resolve/` wraps `resolve_attack`/`encounter` (combat §9) — are built
tests-first, JSON-envelope-out, and are the ONLY bridge between the Python authority
(graph + rulebook) and UE5 (presentation). UE never re-implements cast selection or
combat outcomes; it renders the `data` field.

---

## 3. Phased roadmap (each phase showable, each riding the auto-build)

The spine of the phasing is the shipped fact: **`build_ayodhya_level.py` already
boots on editor start and builds a level from a world JSON that `world_export`
emits.** So every phase is "edit data / add one fallback-safe spawner / re-boot →
see it," never a hand-rebuild. Phases map onto `GAME_BUILD_PLAN.md` Phase A→B.

### Phase 0 — The Radiant Blockout (days, ~free, NO new geometry)
*Goal: the existing Ayodhya cube-blockout stops looking like cubes and starts looking
like the art direction — purely via materials + lighting, before any mesh swap.*

- Build the **master material set** on the existing cubes: `M_Awakener_Gold` (→ shikhara
  cubes), `M_Awakener_Stone` (→ ground), `M_Awakener_Water`/`M_Master_Water` (→ Sarayu),
  and the signature `M_FX_GoldenAuraRim` + `M_FX_GoldenAuraShell` on the NPC cubes
  (shaders §2, graphics §4).
- Extend the lighting rig **inside `build_ayodhya_level.py`** (shaders §1.2/§3.1, §5
  exact edits): warm real-time-capture SkyLight with violet lower hemisphere,
  forward-scatter glowing horizon (`mie_anisotropy 0.85`), a shadowless warm
  under-sun, and the post refinements (`film_toe ≥ 0.15` anti-grimdark, split-tone
  gold-highlights/cool-violet-shadows). All additive, `_try()`-wrapped.
- Prototype the single **`Terror` knob** on `MPC_Climax` early (shaders §3.3) so Acts
  I–II can foreshadow with the same material at low values.
- **Showable:** a headless high-res screenshot (graphics §8) of a *radiant* Ayodhya
  blockout — gold the only thing blooming, warm key over dusk violet, aura'd beings.
  This is the biggest perceived jump per hour and validates the entire art law before
  a dollar is spent on assets.

### Phase 1 — One Beautiful Smashan-Hub Moment (the vertical slice)
*Goal: a single, complete, breathtaking interactive moment in the hub — the showable
proof that the swap path works end to end.*

1. **Land `tools/world_export` `seeds=` param + 2 grounding tests** (world §0 path B,
   §7.5) — ~12 LOC. Without it the hub seeds on empty `Smashan` residents. Build it
   tests-first (asserts Govardhan-with-Babaji-seed excludes Rama; Mahurgad-not_found
   + seeds still builds). Seed the hub on Sharma's ego-network
   (`Shailendra Sharma, Mahavatar Babaji, Satyacharan Lahiri, Yama, Shiva, Hanuman`).
2. **Add the `assets` block + per-record `mesh`/`aura`/`yaw`/`scale` to the world JSON
   schema** (graphics §6.1) and **rewrite `build_ayodhya_level.py`'s `_cube` into
   mesh-aware `_smesh` + skeletal `_being` + `_apply_aura`** (graphics §6.2), each
   **falling back to `/Engine/BasicShapes/Cube` and `SKM_Manny_Simple`** so the level
   always builds mid-migration. Fork it to `build_smashan_level.py` (world §7.4) with
   the new `_landmarks()` pass.
3. **Build the HUB shell `L_Smashan`** (world §2) with the 8-zone layout (dhuni,
   Shivalingam, Yama's-seat gatekeeper, Adi-Shakti ground, Pampa pond, Satyacharan
   anchor, Sri-Yantra altar, ash field), reusing the Phase-0 light-beyond-light rig.
   Pull free **Megascans** ash-ground/sandstone + the **UE Water** plugin so the
   ground, Sarayu/pond, and stone are real first (graphics §2.1). Author the two
   bespoke hub heroes: the **dhuni** (mesh + Niagara fire + the 4 state tiers) and the
   **Shivalingam** (inner-glow material) — graphics §3.2.
4. **The one moment:** the player tends the dhuni (`BP_Dhuni::Tend` / `Shivalingam::Tend`,
   world §3) — pour water, the aura pulses, the flame kindles. A MetaHuman disciple
   (retarget the existing Third-Person Manny AnimBP, graphics §7) stands in a *real*,
   warm, lit-from-within cremation ground at dusk, an aura'd Babaji present on the
   wooden cot. **The smashan-hub moment is the entire game in miniature**: the place
   you feel safest, lit from within, that you tend as the record of your progress.
- **Showable:** a 30-second walk-tend-look loop. Proves graphics-swap + world-seed +
  shaders-aura all interlock on the shipped auto-build.

### Phase 2 — Act I Playable (one full loop: hub → journey → encounter → pierce)
*Goal: the core loop end to end, the data-driven journey pipeline proven on a real spoke.*

- **Wire the 3 hub upgrade-objects** to `seeker.granthis_pierced` via World Partition
  Data Layer swaps `DL_Act1/2/3` (world §3) — prove the hub *visibly changes* per knot.
- **Build Benares + Mahurgad** (Act I spokes) data-driven (world §4.1/4.2): seeded
  `world_export` → `*_world.json` → forked `build_*_level.py`. Pull the **ghat/Varanasi
  Fab kit** (graphics §2.2) for Benares; author one bespoke hero asset per journey,
  reuse the kits.
- **Sacred-traversal vertical slice on the Benares ghats** (world §6):
  `UAwakenerMovementComponent` + Motion Matching, breath-stamina climb, vertical
  altitude = the knots. The climb IS the practice.
- **Combat foundation:** build `tools/combat_resolve/` tests-first (combat §9) with the
  3 fixtures (Brahmastra-mirror, Narayanastra-vs-surrender, strike-kin). Implement the
  two UE5 boss base-classes `AVigilEncounter` + `ADuelEncounter` and the **Surrender
  input**, teaching surrender early at low stakes (combat §4). Act I's asuric road-foes
  are the rare Duels; the Glimpsed Babaji at Benares is the first Vigil.
- **Showable:** a full Act-I loop — receive the practice at the hub, climb the Benares
  ghats, Glimpse Babaji at the 2 AM door, return, pierce the Brahma-granthi at the hub,
  watch the dhuni kindle one tier brighter.

### Phase 3 — Full Game (Acts II–III, the climax pays off the whole stack)
*Goal: every spoke, the Vigil-heavy Acts II–III, the Vishvarupa Trial.*

- **Govardhan + the Sri-Yantra hand-off** (Act II) — needs the **Devahuti node
  ingested** first (world §4.3 `[NEEDS-INGESTION]`). Build the named Vigils off the
  combat §5.2 table: the **Hemorrhage Vigil** (Hanuman), **Vishnu's Grasp** (inert
  controls by design), **Still the Heartbeats** (the Sri-Yantra breath biofeedback
  Vigil on the 60fps RAF rig, combat §5.3).
- **Srikalahasti (air-lingam) + Badrinath** (Act III) — the cooling `palette_shift`
  (world §7.3), the descent-mistaken-for-ascent geometry (world §6.2). Author the
  bespoke air-lingam (graphics §3.4: translucent refractive + Niagara swirl).
- **The climax Trial** (combat §8) staged through the full **`M_PP_Vishvarupa`
  `Terror` stack** built last (shaders §3.3, §6 step 6): bleach to white, chromatic
  fracture, the form's arms dissolving into light using only corpus imagery, Babaji
  stencil-masked out as the one thing Time does not consume. Resolves to voluntary
  samadhi — no trophy, the grade returns cooler and stiller than Act I.
- **iOS fork** (graphics §1, shaders §0): the mobile quality switch on every master
  material + baked LODs, planned from day one so this is a build-setting fork, not a
  re-art.
- **Showable:** the complete pilgrimage, hub visibly transformed across three acts,
  ending on ash-at-dawn and the rudraksha grove.

> **Why this order is forced, not chosen:** Phase 0 needs nothing new (materials on
> cubes). Phase 1's hub is the smallest, highest-emotional-density, fewest-draw scene
> (easiest to make breathtaking) and exercises every interlock once. Phase 2 proves the
> journey *pipeline* on the cheapest spoke (ghat kit + breath-climb). Phase 3 is the
> payoff that can only be built once cast, materials, and the Terror knob all exist.
> Each phase re-uses the auto-build, so "showable" is always one editor-boot away.

---

## 4. Locked guardrails (carried verbatim into every phase)

These are non-negotiable and gate every asset, beat, and mechanic. They appear in all
four branches; restated here as the production contract.

1. **Truth-to-texts (the moat).** Every weapon, being, place, and beat traces to
   decoded corpus (graph node / bio line-ref) or is flagged `[INVENTED]` /
   `[REASONED EXTENSION]` (form authored in-register, meaning corpus-cited) /
   `[NEEDS-INGESTION]` (gap awaiting decode). The graph decides *who/what/where*; we
   only author the *shell* and mark every seam. Combat outcomes come from `combat.py`'s
   rulebook via `tools/combat_resolve` — the renderer **never invents an outcome**.
   Cast comes from seeded `world_export` — the renderer **never substitutes** a Puranic
   namesake for a biography being (e.g. Guruji's sister Devahuti stays un-merged).
2. **POV: reverent distance.** The player is the **disciple, looking back, walking
   toward the guru** — never Guruji, never Babaji, never a deity. In the Vigils the guru
   is the one seized across a gap; the player's inputs to reach him **fail by design**.
3. **No-reincarnation / lineage spine.** No Puranic character reincarnates into Sharma;
   the spine is deathless Babaji + the inheritable Lahiri-family seat. Aura tiers
   (`none|faint|bright|vishvarupa`) mark awakened beings; Babaji = `bright`, deathless
   calm, and is stencil-masked OUT of the climax bleach (the one constant Time does not
   consume).
4. **Light from within.** ART_DIRECTION's one law: lit from within, gold = the body of
   consciousness, golden aura on awakened beings, **bloom sparing (brilliance NOT
   neon)**, warm gold over dusk violet/umber, `film_toe ≥ 0.15` so shadows never crush —
   **NEVER grimdark.** Gold is the only thing above the bloom threshold.
5. **No god-trophy.** There is no boss-rush ending, no "YOU UNLOCKED: GOD." The climax
   is mysterium tremendum (Gita-11/Vishvarupa) resolving to voluntary samadhi; "the
   human form was a mercy." The reward and the ending are the same event. Siddhis/astras
   are a **temptation** that re-locks itself (`_moral_weight` corrodes sattva for forced
   violence) — a player who never fires an astra can reach the ending and is rewarded for
   restraint.

---

## 5. Top 5 open questions for the user (pulled from the branches)

1. **Substrate vs. non-Substrate materials on M1?** Shaders defaults to non-Substrate
   for M1 safety unless the project already enabled Substrate (shaders §2). This decides
   the entire master-material graph authoring path and the iOS fork — confirm before any
   material is built.

2. **Ingest Guruji's biography cast now, or hand-author the gaps?** The graph is missing
   **Devahuti** (Guruji's sister, 0 hits) and possibly **Adi Shakti** — both are
   required level seeds (world §4.3, §4.5, §9). Govardhan (Act II) is blocked on Devahuti.
   Do we run the Guruji-corpus ingestion now, or hand-author these actors un-merged and
   defer ingestion?

3. **How literal is the climax "arms dissolve / extra arms appear then dissolve"
   staging?** Shaders flags the *choreography* as `[INVENTED]` dramatization (the corpus
   asserts the universal form and its terror, not the exact limb sequence), pending
   verse-level Vishvarupa decode beyond `bhp_05.07.001`/`mbh_02.009.014` (shaders §3.3
   Phase 3, combat §8 `[NEEDS-INGESTION]`). How much invented staging is acceptable
   before the verses land?

4. **Asset spend approval for Act I (~$120–280 on Fab).** Indian-temple modular + ghat/
   Varanasi + village-props + crowd-clothing kits (graphics §2.2, §5). Megascans/Water/
   MetaHumans/Nanite/Lumen are free; this is the only cash cost to ship Ayodhya + smashan
   + Benares credibly. Approve the budget and the buy-order?

5. **The "Vishnu's Grasp" deliberately-inert-controls Vigil — ship it as designed?**
   It is the boldest beat: a boss where the player's inputs to reach the guru *return
   "you cannot reach him"* by design (combat §5.2). It risks reading as a bug if the
   telegraphing (via the earlier Hemorrhage Vigil + Narayanastra-surrender lesson) isn't
   trusted. Confirm we commit to inert-by-design rather than softening it to a
   conventional survival fight.
