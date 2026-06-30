# THE AWAKENER — Combat System Design

> **Scope.** This is the moment-to-moment and encounter-level combat design for THE
> AWAKENER, derived from two sources of truth: the astra rulebook in
> `narrative_engine/combat.py` (counters, restrictions, guna/tapasya gates, moral
> weight) and the combat *philosophy* locked in `tools/read_pass/STORY_BIBLE.md`
> (Acts II–III + Part IV). It is buildable from: a UE5 dev should be able to wire
> the state machines, ability data, and boss encounter types directly off this
> doc.
>
> **The load-bearing inversion (read first).** This is an Assassin's-Creed-grade
> action game where, in Acts II–III, *the central encounters are not won by
> killing.* The bible's combat is "you do not defeat the divine; you endure until
> it turns toward you" (STORY_BIBLE.md Act II Beat 3; the python-hemorrhage vigil;
> Vishnu's grasp you cannot break). So combat has **two distinct combat verbs that
> share one input layer**: the **Duel** (a rare true martial exchange, the only
> place AC-style kill-combat lives) and the **Vigil** (endurance/perception under a
> force you cannot defeat). The design's job is to make both feel like *combat* —
> taut, skill-tested, failable — while keeping the second text-true.
>
> **Every weapon, counter, and restriction below traces to `combat.py`'s
> `_ASTRA_RULES` or to a corpus cite in the bible.** Anything not so traceable is
> flagged `[INVENTED]` (a game-mechanic scaffold around real rules) or
> `[NEEDS-INGESTION]` (a gap waiting on decode). The rule itself is never invented;
> only its *rendering as a mechanic* is.

---

## 0. The thesis combat must serve

From the bible's locked guardrails (Part VI):

1. **POV is reverent distance.** The player is the disciple, never Guruji, never a
   deity. In the Vigil set-pieces the *guru* is the one being seized across a gap;
   the player's inputs to reach him **fail by design** (Act II Beat 5: "every input
   to reach Guruji fails").
2. **Siddhis/astras are a TEMPTATION, not a power fantasy.** The corpus and bible
   are explicit: powers are a side-effect of the path and a trap if chased. Combat
   must make the *easy violent answer corrode the seeker* (this is already encoded:
   `_moral_weight` in `combat.py` pushes tamas for adharmic strikes). The game
   should reward restraint, surrender, and endurance over the kill.
3. **The climax is not a god-trophy.** There is no boss-rush ending. The last
   "combat" (Act III) is a perception-endurance trial against Time that is
   explicitly **"untouchable by weapon, fire, or wind"** (`bhp_05.07.001`,
   `mbh_02.009.014`) — a combat boss there would betray the source. The final
   "victory" is *not flinching*.

Combat therefore has an **anti-power-creep spine**: the more astras you accumulate
and the more you reach for them, the *farther* you drift from the granthi-path. The
mechanical loop must let a player who never fires a single astra reach the ending —
and reward them for it.

---

## 1. The three encounter REGISTERS = three combat intensities

The bible (Part IV) defines three escalating registers for how a figure appears:
**Told → Glimpsed → Beheld.** These are not just narrative tiers — they are the
**combat intensity bands**, and they map cleanly onto the two combat verbs:

| Register | What it is narratively | Combat form | Player agency | Failure = |
|---|---|---|---|---|
| **Told** | The disciple *hears* Guruji met a being (story/photo/witness) | **No real-time combat.** A scripted/cutscene or dialogue beat. May carry a QTE-light "recoil/steady" prompt. | Minimal (steady the camera, hold breath) | Cosmetic; you re-read the beat |
| **Glimpsed** | The disciple is *present at the edge* of the encounter (footprints, a flood, a garland) | **The Vigil.** Endurance/positioning/breath under a force you cannot defeat. *This is most of Acts II–III's "boss" content.* | Survive, hold, surrender, endure — NOT kill | Recoil (flinch back to safety), not death; repeatable |
| **Beheld** | The *principle* behind the figure becomes briefly perceptible to the disciple's own senses | **The Trial** (a Vigil at maximum intensity) OR, rarely, **the Duel** | Hold perception open; or, in a true duel, the full astra kit | Recoil at low cost / "death" only in the rare Duel |

**The rare true Duel** is the *only* place the AC-style kill-combat (the full
light/heavy/astra/parry kit, an enemy with a health bar that you reduce to zero)
lives. It is reserved for **demonic / adharmic / asuric opposition** — beings it is
*dharmic to strike* (the `_moral_weight` "righteous defense against a hostile"
branch, which holds/raises sattva). The divine is **never** a Duel; the divine is a
Vigil or a Trial.

> **Design read:** the player learns the action-combat grammar early (Act I, against
> low asuric/obstacle foes and the "body's own gravity" boss), then spends Acts
> II–III having that grammar **taken away** — the gods cannot be fought, only
> endured — which is the mechanical expression of the bible's whole gradient (love
> → scale → intimacy with the terrible → understanding).

---

## 2. The shared input layer (moment-to-moment)

One control scheme serves both Duel and Vigil; the *meaning* of each input shifts by
context. Target: Mac-first (keyboard+mouse and controller), then iOS (touch
mapping). Buttons named generically; bind in the UE Enhanced Input mapping context.

| Action | Controller | KB+M | Duel meaning | Vigil meaning |
|---|---|---|---|---|
| **Light** | ▢ / X | LMB | Fast strike, combo opener | Small steadying gesture (re-center stance) |
| **Heavy** | △ / Y | RMB | Slow, high-poise strike | Brace (plant against an incoming surge) |
| **Astra-Invoke** | R2 (hold) + face | Q (hold) + 1–4 | Charge & fire a chosen astra | **Mostly locked** (gods are not targets; firing an astra at the divine is a *temptation* — see §6) |
| **Counter / Parry** | L1 | F | Time a block to deflect; perfect-parry = riposte window | **Endure-parry:** time a breath against a surge to avoid recoil |
| **Surrender** | hold L1+R1 (or hold ✕) | hold Shift | Lay down arms — a *real* tactical option (see Narayanastra §4) | The Vigil's core verb: stop forcing, let the force pass through |
| **Breath (prana/apana)** | hold L2 + Crown/stick | Space (hold) + WASD pulse | Regulates stamina/poise recovery; gates astra use | **The primary Vigil input** — the 60fps breath/yantra UI; stillness drives the win condition |
| **Dodge / Step** | ✕ / A | LShift-tap | I-frame evade | Reposition out of an environmental hazard (flood, fire) — never an attack |

**Stamina is "Prana," not a generic bar.** It depletes on Light/Heavy/Dodge and on
holding khechari/breath; it recovers through the Breath input (the Act I prana/apana
balance skill, `bhp_02.x`). This makes the Act I austerity mechanic the literal
resource economy for all later combat — the breath you learned to balance is the
breath that lets you act and endure. **[GROUNDED — Act I prerequisites]**

---

## 3. The astra system — text-rules surfaced as mechanics

`combat.py`'s `_ASTRA_RULES` is the canonical weapon table. Each rule already carries
`countered_by`, `restrictions`, `special_rules`, `guna_requirement`,
`tapasya_requirement`, and `source_text`. The mechanic for each is a *direct render*
of those fields. **Do not author astra balance numbers freehand — derive them from
the rule dict and the graph grounding (`ground_astra`).**

### 3.1 Acquisition & gating (you cannot just have an astra)

An astra is only usable if `available_abilities(seeker, memory)` returns it as
`status: "ready"`. That function enforces, per `combat.py`:

- **Boon required:** the astra must be in `seeker.boons` (you *received* it — earned
  via the granthi-path / an encounter, never bought). No boon ⇒ not even listed.
- **Guna gate:** `seeker.guna.sattva >= guna_requirement.min_sattva`
  (Brahmastra 0.25, Narayanastra 0.30, Pashupatastra 0.35).
- **Tapasya gate:** `seeker.tapasya[deity].accumulated >= min`
  (Brahmastra: brahma ≥50; Narayanastra: vishnu ≥80; Pashupatastra: shiva ≥100).
- **Curse block:** any matching curse in `seeker.curses` hard-blocks it (the
  Karna-curse pattern — `combat.py` docstring line 12).

**UE surfacing:** the astra wheel (radial menu on hold-Astra-Invoke) shows each
known astra with one of three states fed straight from `available_abilities`:
`ready` (lit gold, per ART_DIRECTION inner-radiance), `blocked` (dim, with the
`reasons[]` string as tooltip — "guna imbalance (need sattva ≥ 0.35)",
"insufficient tapasya with shiva", "blocked by curse"), or absent (no boon).

> **Anti-temptation hook:** the *more powerful* the astra, the *higher* its sattva
> AND tapasya gate — but firing it at a non-asuric/kin/teacher target **drops
> sattva** via `_moral_weight`, which can push you back below the gate of the very
> astra you just used. Power used wrongly disarms you. This loop is the bible's
> "siddhis are a temptation" made mechanical and is already half-built in
> `encounter()`.

### 3.2 The counter/annihilation rules (surface them as parry timings)

`resolve_attack(attacker, astra, defender, defender_action, memory)` already
resolves the four canonical interactions. Render each as a real-time mechanic:

| Text rule (from `_ASTRA_RULES`) | `resolve_attack` outcome | Real-time mechanic |
|---|---|---|
| **Brahmastra ↔ Brahmastra → mutual annihilation** (`countered_by: ["brahmastra"]`, MBh) | `defender_action="counter_with:brahmastra"` ⇒ `outcome="neutralized"`, *"both annihilated"* | A **mirror-parry**: both fighters charge Brahmastra; the screen goes to the "thousands of suns" white (ART_DIRECTION). If the defender's invoke completes within the parry window, **both astras and a chunk of the battlefield are consumed** — no winner. A failed mirror = the world-ending hit lands. Encodes the MBh lesson: two Brahmastras must never both be loosed. |
| **Narayanastra: stronger vs resistance, neutralized by surrender** (`special_rules`, MBh) | `resist` ⇒ `outcome="devastating"`; `surrender` ⇒ `outcome="neutralized"` | See §4 — the **Surrender mechanic.** This is the single most important counter in the game thematically. |
| **Pashupatastra: cannot be used against lesser warriors; destroys everything** | restriction enforced at invoke-time | If the locked target is below a "worthiness" threshold (a graph-derived foe rank), the invoke is **refused** — the astra will not arm. Firing it at all carries the highest moral weight. Reserved; never usable in a Vigil. **[GROUNDED restriction]** |
| **Elemental counters (fire/water/wind, Nagastra↔Garuda)** | see §3.3 | Counter by *opposing element / opposing astra*, a rock-paper-scissors layer on parry. |

### 3.3 Elemental & creature counters

The bible's prompt names the classic Puranic counter-pairs (fire↔water, wind, Naga
astra ↔ Garuda). These are **partially in `_ASTRA_RULES` and partially
`[NEEDS-INGESTION]`** — only Brahmastra/Narayanastra/Pashupatastra/Sudarshana/
Gandiva/Vajra/Trishula are currently encoded. Build the elemental layer as a data
extension to `_ASTRA_RULES` (same shape), *gated behind decode*:

| Astra | Counter | Status |
|---|---|---|
| **Agneyastra (fire)** | **Varunastra (water)** quenches it; Parjanya/cloud | `[NEEDS-INGESTION]` — add to `_ASTRA_RULES` with `countered_by: ["varunastra"]` once the verses decode. Until then, flag any Agneyastra encounter EARLY DRAFT. |
| **Varunastra (water)** | **Agneyastra / Vayavyastra (wind)** disperses | `[NEEDS-INGESTION]` |
| **Vayavyastra (wind)** | Parvatastra (mountain), Mountain-astra anchors | `[NEEDS-INGESTION]` |
| **Nagastra / Nagapasha (serpent-noose)** | **Garudastra** (Garuda devours serpents) | `[NEEDS-INGESTION]` — canonical pairing, MBh; add once grounded. |
| **Sudarshana Chakra** | *uncounterable* (`countered_by: []`, "cannot be stopped once launched") | `[GROUNDED]` — by rule, **never** appears as a survivable Vigil hazard the player can parry; it is a *cutscene-only* force (only Vishnu/avatars wield it). |

**Mechanic for the elemental layer (when grounded):** the parry's "perfect" window
is widened if the defender invokes the *correct counter-element* astra and shrunk to
near-zero for a wrong element — i.e., knowing the text's counter is the skill being
tested, not raw reaction time. This is where `resolve_attack` is the authority: the
real-time parry only *opens the window*; the **outcome string from `resolve_attack`
is the canonical result** the UE layer must display ("varunastra counters agneyastra
— both annihilated"). Never let the renderer invent an outcome the rulebook didn't
return.

> **Build note — single source of truth:** the UE combat resolver should call into a
> thin JSON-contract wrapper around `resolve_attack`/`encounter` (per the workspace
> Rule-0 tool pattern) and render only its `data` — never re-implement counter logic
> in Blueprint/C++. A `combat_resolve` tool under `tools/` is the right home; build
> it tests-first against captured `resolve_attack` envelopes (see §9).

---

## 4. SURRENDER as a real combat option (Narayanastra) — the keystone mechanic

This is the mechanic the whole combat philosophy hangs on, and it is already in
`combat.py`:

```
Narayanastra.special_rules = ["grows stronger against resistance",
                              "neutralized by laying down arms"]
resolve_attack(..., defender_action="surrender") ⇒ outcome="neutralized"
resolve_attack(..., defender_action="resist")    ⇒ outcome="devastating"
```

**The mechanic.** When the Narayanastra is loosed at the player (a scripted
high-stakes beat), the HUD presents the player's instinct — *fight back / dodge /
raise your own astra* — and **every aggressive response makes the attack stronger
and kills you** (`devastating`). The only survival is the **Surrender input**
(hold L1+R1 / hold Shift): lay down arms, lower the camera, drop the weapon. The
astra passes over harmlessly (`neutralized`).

Why this matters mechanically and thematically:
- It **inverts the action-game reflex.** A trained AC player will parry/dodge — and
  die. The game must *teach* surrender as a verb earlier (low-stakes) so this beat
  reads as skill, not a gotcha.
- It is the **rehearsal for the Vigil and the climax.** Act II Beat 3 (Hanuman
  vigil) and Beat 6 (Still the Heartbeats) both reward "endure, don't force"; the
  Narayanastra teaches the same hand at weapon-scale. Bible Act II Beat 6: *"only
  surrender… lets the pulse fall."*
- **Moral weight is correct already:** striking one who has surrendered is the
  gravest adharma in `_moral_weight` (`struck_surrendered` ⇒ `tamas +0.12, sattva
  -0.06`, *"gravely adharmic"*). So if the *player* is the one wielding Narayanastra
  and the foe surrenders, continuing to strike corrodes the seeker hardest of all.

**Single-use enforcement.** Narayanastra `restrictions: ["single use per
incarnation"]` — the UE layer must consume it permanently on fire (one charge per
run/incarnation). Reflect in the astra wheel as a spent slot.

---

## 5. The VIGIL — the endurance/survival "boss" (Acts II–III core)

The Vigil is the bible's signature encounter: **survive, don't kill.** Three are
named in the bible; build the type once, parameterize per beat.

### 5.1 The Vigil state machine

```
                 ┌──────────────────────────────────────────────┐
                 │                   VIGIL                       │
                 │  win = SURVIVE to the scripted turn, NOT kill │
                 └──────────────────────────────────────────────┘
   ENTER ──► [ENDURE] ◄────────────► [SURGE] ──(unhandled)──► [RECOIL]
              │  hold breath/        │ the force lashes        │ flinch back
              │  stillness; the      │ (a god's grasp, a       │ to safety —
              │  Composure meter      │ hemorrhage, a flood)    │ NOT death.
              │  fills slowly         │ handle via Brace /      │ Vigil resets
              │                       │ Endure-parry / Surrender│ to last phase
              ▼                       ▼                         │
          [THRESHOLD] ── Composure full at the scripted moment ─┘
              │
              ▼
        [THE TURN] ── the force TURNS TOWARD YOU: rescue is GRANTED,
                      not forced (Hanuman stops the bleeding; the knot breaks)
```

- **No enemy health bar.** The "boss" has no HP. The player has a **Composure**
  resource (not health) that must be *held*, not spent. The win condition is a
  **timeline**, not a kill — you must keep Composure above zero until the scripted
  Turn.
- **Surges** are telegraphed environmental/divine events (per beat: a python's
  constriction, the screen desaturating toward white as the guru bleeds out, Vishnu
  closing his hand, the Yamuna flooding). The player handles each surge with
  **Brace** (Heavy), **Endure-parry** (timed breath against the surge), or
  **Surrender** (let it pass) — *never* by attacking the source.
- **RECOIL, not death.** Failure = the disciple flinches back to safety (Act III
  Beat 3 makes this explicit: "failure-state is not death — it's recoil"). The Vigil
  resets to the start of the current phase, optionally with the narrator's calm
  thinning one degree. This keeps the set-piece *failable and tense* without a
  game-over screen that would break the reverent tone.
- **The Turn is granted.** Critically, the rescue/relief is **not** something the
  player executes — it arrives because they endured (Act II Beat 3: "rescue is
  granted, not forced"). The final input before the Turn is often *Surrender*, not a
  triumphant blow.

### 5.2 The three named Vigils (parameterize the type)

| Vigil | Bible beat | Surge(s) | Win = the Turn | Player verbs |
|---|---|---|---|---|
| **The Hemorrhage Vigil** | Act II Beat 3 — python attack, Guruji hemorrhages, prays to Babaji, **Hanuman stops the bleeding**, names him "Yogiraj" | Screen desaturates toward white; constriction pressure; blood-loss timer | Hold Composure (prayer/breath) until **Hanuman appears** and stops the bleeding | Brace, Endure-parry, **pray** (a hold-input that channels toward Babaji) |
| **Vishnu's Grasp** | Act II Beat 5 — Vishnu seizes Guruji; **Shiva tears him free**; flood; rudraksha grows | The camera **locks across the courtyard**; *every input to reach Guruji fails* (by design); the flood rises | Survive the helplessness until **Shiva pulls the guru free** | Almost none — the verb is *witness*. Inputs to cross the gap return a "you cannot reach him" feedback. The only meaningful input is to **not look away** (hold camera on the guru). |
| **Still the Heartbeats** | Act II Beat 6 — the heart-knot trial on the **Sri Yantra** | The heartbeat races (Vishnu's grasp flashes back) when the player forces it | Bring the heartbeat **asymptotically to zero**; the nine triangles converge on the **bindu**; the knot *bhidyate* (BhP 1.2.21) | **Breath input + stillness ONLY.** Effort = the heart races. Surrender = the pulse falls. This is the Vigil with *zero* aggressive options. |

**"Vishnu's Grasp" is the design's boldest beat:** a boss fight where the player's
controls are *deliberately inert* against the threat. This must be authored
carefully — telegraph early (via the Hemorrhage Vigil and the Narayanastra lesson)
that *reaching/forcing fails*, so the locked camera reads as the intended horror of
reverent distance, not a bug. The corrective feedback ("the courtyard you cannot
cross") is itself the message (bible POV guardrail #1).

### 5.3 "Still the Heartbeats" — the breath/yantra Vigil in detail

This is where the 60fps breath UI (the bible's `YantraLoader.tsx`-class
`requestAnimationFrame` rig) becomes a **biofeedback combat puzzle**:

- The **Sri Yantra's nine triangles** are driven by a live heartbeat signal (a
  visible, audible pulse). The triangles' separation = current heart rate.
- **Input:** the prana/apana Breath skill from Act I. Smooth, slow, balanced breath
  *lowers* the rate; jerky/forced input *raises* it.
- **The trap (anti-power, anti-force):** any attempt to "push" the rate down fast —
  hammering the input — triggers a **Vishnu's-grasp flashback** (a Surge) that spikes
  the heart. The asymptote can only be approached by *letting go*. Surrender is
  literally the optimal play.
- **Win:** triangles converge on the **bindu**; a single still point; the act's
  chaotic presences (all the gods who arrived) snap into one point. The knot breaks.
  Reward = "a room in the chest you can always come back to" (a persistent nightly
  mechanic, per bible Beat 7), NOT a stat.

`[NEEDS-INGESTION]`: the *exact* heart-center breath-technique Babaji taught is not
in the distilled bio (bible Beat 6 note). Build the mechanic grounded (BhP 1.2.21 is
solid) but mark the *literal breath choreography* evocative-placeholder until the
Awakener heart-kriya chapters decode.

---

## 6. The astra as TEMPTATION (the anti-power-creep system)

The bible's prompt is explicit: *"siddhis/powers are a TEMPTATION you shouldn't
chase."* This is a **first-class system**, not flavor. It already has its mechanical
spine in `combat.py`'s `_moral_weight` + `encounter()`:

### 6.1 The corrosion loop (built)

Every astra strike runs through `encounter()` → `_moral_weight()`, which reads the
attacker↔defender relationship from the graph and applies a guna shift:

- Strike **kin** (graph `_KIN_RELS`) ⇒ `tamas +0.10, sattva -0.05` ("the Gita's
  central anguish").
- Strike a **guru/teacher** (`_GURU_RELS`) ⇒ `tamas +0.08, sattva -0.04`.
- Strike one who **surrendered** ⇒ `tamas +0.12, sattva -0.06` (worst).
- A clean martial act vs. a hostile ⇒ `rajas +0.06, tamas +0.02, sattva -0.02`
  ("combat is never wholly clean").
- Meeting force with **restraint** (`neutralized`) ⇒ `sattva +0.03` — the *only*
  guna-positive combat outcome.

**The temptation surfaces as a feedback loop the player can feel:**
1. Reaching for astras drifts sattva *down* (even "clean" kills cost a little
   sattva).
2. Lower sattva *locks higher astras* (§3.1 gates) — Pashupata needs sattva ≥0.35.
3. So the power-chaser **disarms themselves** and drifts toward tamas-dominant
   (`guna.dominant`), which the narrative engine reads as straying from the path.
4. Only **restraint, surrender, and endurance** raise sattva — the same verbs the
   Vigils and the granthi-path reward.

### 6.2 The "do not reach for it" UI cue

In Vigils and divine encounters, the astra wheel is **present but should not be
used** — firing an astra at a deity is *the temptation*. Design: the wheel still
opens (the option is real, like in the Mahabharata where the choice exists), but:
- The target-lock on a divine being shows a **"this is not a foe"** state — invoking
  anyway either *refuses to arm* (for Pashupata-class) or fires and **carries
  maximal moral weight** (huge tamas spike, possible curse acquisition).
- The narrator's calm thins faster if the player habitually reaches for power.
- There is **no astra reward** for "beating" a god — there is no god to beat.

> **The clean expression of the thesis:** a skilled action-gamer's instinct (use
> the strongest tool, win the fight) is precisely the temptation the game is built
> to surface and gently defeat. The player who *puts the weapon down* progresses; the
> player who chases siddhis stalls in tamas. This is the bible's "the truth is the
> tribute" rendered as a balance loop.

---

## 7. The rare true DUEL (where AC-combat lives)

The Duel is the *only* full action-combat encounter type, and it is deliberately
**rare and confined to dharmic targets** — asuric/obstacle foes it is *righteous to
strike* (the `_moral_weight` "default martial act against a non-kin opponent"
branch, which costs little sattva and grants rajas). Examples that fit the bible: the
exorcism **darbars** Hanuman commissions Guruji over ("Yogiraj," Act II Beat 3) — the
disciple, secondhand, faces the malefic spirits/obstacles of those darbars; Act I's
asuric obstacles on the road to the true guru.

### 7.1 Duel state machine (AC-grade)

```
[NEUTRAL] ──Light/Heavy──► [COMBO] ──Astra-Invoke──► [ASTRA RESOLVE → resolve_attack]
   ▲   │                       │                            │
   │   └──Dodge (i-frame)──────┘                            │
   │                                                        ▼
   └──Counter/Parry ◄── enemy tell ──► [PERFECT PARRY → riposte]   [outcome string
                                                                    drives VFX/result]
```

- **Light/Heavy/Dodge/Parry** = standard action-combat (poise, stamina=Prana,
  perfect-parry riposte windows). Tunable per UE `GameplayAbilitySystem` (GAS)
  recommended — model each astra as a `GameplayAbility`, each gate as a
  `GameplayEffect`/attribute check mirroring `available_abilities`.
- **Astra-Invoke** in a Duel resolves through `resolve_attack`/`encounter`; the
  **outcome string is canon** (`hit`/`devastating`/`neutralized`/`unknown`). The
  renderer plays VFX for the returned outcome — it never decides the outcome itself.
- **The Duel still feeds the temptation loop:** even winning a Duel cleanly costs a
  little sattva (`rajas +0.06, sattva -0.02`). You can win every fight and still be
  drifting from the path — which the granthi gates will eventually surface.
- **`is_canon` gating:** `encounter()` returns `draft_warnings` and `is_canon`. If an
  astra is `confidence: "none"` or `"absorbed"` (not yet graph-grounded), the Duel
  must render an **EARLY DRAFT** banner and treat that astra's powers as placeholder
  — never ship a Duel that presents an ungrounded astra as canon.

### 7.2 What is NEVER a Duel

- **Any Tier-1/Tier-2 figure** (Babaji, Lahiri, Satyacharan, Shiva, Vishnu, Adi
  Shakti) — these are Glimpsed/Beheld principles, never HP bags.
- **Time itself** (Act III trial) — "untouchable by weapon, fire, wind"
  (`bhp_05.07.001`). A weapon here is a category error.
- **The surrendered.** Striking a yielded foe is the worst moral weight; the Duel's
  win-screen for a foe who surrenders is to *accept the surrender* (the dharmic
  resolution), not to execute.

---

## 8. Act III — the Trial (combat dissolves into perception)

Act III's "boss" (bible Act III Beat 3) is the **Trial**: a Vigil at maximum
intensity where the threat is **not a being but unmanifest Time**, explicitly
**untouchable by weapon, fire, or wind**. There is *no astra layer at all* — the
astra wheel is empty/withdrawn. The combat verbs collapse to one: **do not flinch.**

- **Mechanic:** hold the Omkar state (a sustained breath/sound input) while Time
  *stops wearing a face* — the four-armed Vasudev loses its arms, its blue, its
  form, and **keeps being there**. The smashan stops being a place and becomes a
  *moment* (everything always-already burning).
- **Failure = recoil, repeatedly allowed.** The disciple can flinch back into the
  safety of form (back up to the gentle Vasudev). The game *lets* him, again and
  again. The Trial is passed only when he **stops flinching** — keeps perception
  open on Time-without-mercy.
- **There is no kill, no clear, no trophy.** Passing the Trial → the Revelation →
  voluntary samadhi (the reward and the ending are the *same event*, bible Beat 6–7).
  No "YOU UNLOCKED: GOD."

`[NEEDS-INGESTION]`: the first-person sensory texture of "unmanifest Time" needs the
Awakener Srikalahasti air-lingam (~L151/L307) + Muladhar/57th-birthday Omkar
passages before the Trial's vision lines are scripted (bible Part V item 3).

---

## 9. Build plan & data contract (UE5 + the `tools/` resolver)

**Architecture (per workspace Rule-0):** combat *outcomes* are decided by Python
(the rulebook is `combat.py`, the authority); UE5 owns *presentation, timing windows,
and input*. Wire them through a thin JSON-contract tool, not duplicated logic.

1. **`tools/combat_resolve/` (build this, tests-first).** A JSON-in/JSON-out wrapper
   over `resolve_attack` + `encounter` + `available_abilities`, returning the
   standard envelope `{success, data, metadata, errors}`. `data` carries the outcome
   string, moral-weight guna shift, grounding confidence, and `draft_warnings`.
   - **Tests-first (Precondition A):** capture 2–3 real `resolve_attack`/`encounter`
     envelopes as fixtures (Brahmastra-mirror, Narayanastra-vs-surrender,
     strike-kin) and assert *fixture-in → envelope-out*. Must run as
     `venv/bin/python -m tools.combat_resolve.test_check` and exit 0.
   - Register it in `tools/README.md`.
2. **UE5 layer (GAS).** Model each astra as a `UGameplayAbility`; the gate checks
   (`min_sattva`, tapasya, curse) as `UGameplayEffect`/attribute queries mirroring
   `available_abilities`. The ability's *activation* calls `combat_resolve` (over
   local IPC / a localhost FastAPI bridge — the same `:8000` pattern the backend
   uses) and plays VFX for the returned outcome.
3. **Two boss base-classes (C++/BP):** `AVigilEncounter` (Composure timeline, Surge
   telegraphs, Turn trigger, recoil-not-death) and `ADuelEncounter` (standard
   GAS combat + astra resolve). Most of Acts II–III are `AVigilEncounter` instances
   parameterized by the §5.2 table; the rare darbar/asuric fights are `ADuelEncounter`.
4. **Input mapping context** per §2; one context, two `EnableInput` profiles (Duel
   enables the astra wheel + dodge; Vigil disables astra-at-divine and surfaces
   Surrender/Breath as primary).
5. **Art/feel (ART_DIRECTION):** astra VFX = inner radiance, gold = the body of
   consciousness; Brahmastra-mirror = the "thousands of suns" white; awakened beings
   carry the golden rim-aura; bloom used sparingly (brilliance, not neon). The Vigil
   desaturation-toward-white (Hemorrhage) and the courtyard light-lock (Vishnu's
   Grasp) are the two signature combat looks.

---

## 10. One-paragraph summary for the dev

THE AWAKENER's combat has **two verbs over one input layer**: the rare **Duel**
(full AC-grade kill-combat, reserved for asuric/dharmic-to-strike foes, astras
resolved by `combat.py`'s rulebook) and the **Vigil** (endure-don't-kill set-pieces
that are the heart of Acts II–III — a Composure *timeline* with telegraphed Surges,
no enemy HP, failure = recoil-not-death, and a rescue that is *granted* when you
endure, not executed). The three encounter **registers** Told/Glimpsed/Beheld are the
three combat intensities. **Surrender** is a real, often-optimal input
(Narayanastra: resist→devastating, surrender→neutralized). The **astra system** is a
direct render of `_ASTRA_RULES` (Brahmastra↔Brahmastra mutual annihilation,
elemental/Naga↔Garuda counters `[NEEDS-INGESTION]`, Pashupata refused vs. lesser
foes, guna+tapasya gates from `available_abilities`). Powers are a **temptation**:
`_moral_weight` corrodes sattva for adharmic/forced violence, which *re-locks* the
high astras — so the power-chaser disarms himself and only restraint/surrender/
endurance raise sattva. Act III dissolves combat entirely into a **perception Trial**
against unmanifest Time (no weapons, no kill, no trophy) that resolves into voluntary
samadhi. Build outcomes in a tested `tools/combat_resolve` JSON-contract tool; UE5
(GAS) owns timing/input/VFX and renders only what the rulebook returns.
