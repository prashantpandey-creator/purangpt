# Narrative Engine

Game-facing API layer over PuranGPT's verified knowledge graph. Any client — text
adventure, Godot, UE5, web browser, Vision Pro — hits these endpoints and gets back
JSON it can render.

## Architecture

```
Game Client (any platform)
    │
    ▼
narrative_engine/api.py  ── 17 endpoints under /api/game/
    │
    ├── world.py       — locations, residents, spatial navigation
    ├── character.py   — NPC sheets, abilities, dialogue grounding
    ├── combat.py      — astra rules, guna-based ability resolution
    ├── seeker.py      — player state (guna, tapasya, boons, karma)
    └── narrative.py   — story events, consequence chains, dharmic forks
         │
         ▼
    recall() + decode() + factsheet() + graph  (existing read_pass modules)
         │
         ▼
    graph_manifest.json + guruji_ram.json  (verified knowledge graph)
```

## Endpoints

### Scene (one-call screen assembly)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/game/scene` | Everything to paint one screen: location + self + available actions. Moves the seeker if `location` given. |

### World
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/game/world/locations` | All navigable Puranic locations |
| POST | `/api/game/world/location` | Location detail: residents, events, exits |
| POST | `/api/game/world/npcs` | NPCs at a location |
| POST | `/api/game/world/nearby` | Reachable places (BFS nav graph) |
| POST | `/api/game/world/journey` | Places a character visits (chapter co-occurrence) |

### Character
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/game/character/sheet` | Full NPC profile (identity, family, weapons, decode) |
| POST | `/api/game/character/abilities` | Combat abilities: weapons, boons, curses |
| POST | `/api/game/character/relationships` | All relationships via graph recall |
| POST | `/api/game/character/dialogue` | Grounded dialogue context for LLM NPC speech |

### Combat
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/game/combat/astra/rules` | Rules for a divine weapon (from the texts) |
| POST | `/api/game/combat/astra/grounding` | Graph evidence for an astra (wielders, cites, confidence) |
| POST | `/api/game/combat/astra/available` | What the seeker can currently use |
| POST | `/api/game/combat/astra/fire` | Resolve an astra attack (stateless) |
| POST | `/api/game/combat/encounter` | Full exchange: attack → guna consequence → karma (feeds the arc) |

### Seeker (Player)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/game/seeker/state` | Current guna, tapasya, boons, curses, karma |
| GET | `/api/game/seeker/karma` | The path you walked — choices, guna drift, turning points |
| POST | `/api/game/seeker/meditate` | Tapasya toward a deity (shifts guna; persists) |
| POST | `/api/game/seeker/choice` | Record a dharmic choice (persists) |
| DELETE | `/api/game/seeker/state` | Reset — clears cache + persisted row |

Pass `x-session-id` to scope a seeker; optional `x-user-id` ties it to a logged-in user.

### Narrative
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/game/narrative/events` | Events in a text (by verse prefix) |
| POST | `/api/game/narrative/consequences` | Cause-effect chain from an entity |

### Meta
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/game/meta/stats` | Graph statistics |
| GET | `/api/game/meta/health` | Engine operational status |

## Tests

```bash
venv/bin/python -m narrative_engine.test_engine
```

58 assertions against real graph data (graph_manifest.json + guruji_ram.json).

## Key Design Decisions

- **Guna system is NOT a morality meter.** Sattva/rajas/tamas are three qualities
  that color every action. The goal (per Gita 14) is to transcend all three. High
  sattva opens certain paths; high tamas opens others. Neither is "good" or "bad."

- **Combat rules come from the texts.** Brahmastra-vs-Brahmastra = neutralized.
  Narayanastra-vs-surrender = neutralized. These aren't game-designer inventions.

- **Violence costs something.** `combat/encounter` derives a guna consequence from
  the act's dharmic weight — striking kin, a teacher, or one who surrendered pushes
  tamas (the Gita's central anguish); meeting force with restraint nudges sattva. The
  kinship/teacher classification reads the attacker↔defender relationship from the
  graph, so it sharpens automatically as the graph improves. The graph-independent
  rules (surrendered-strike, neutralized-restraint) fire today.

- **Every response traces to the graph.** No invented geography, relationships, or
  events. If the graph doesn't know it, the API says so honestly.

- **Seeker state persists to Postgres.** `persistence.py` stores each seeker as one
  JSONB blob in a self-contained `game_seekers` table (bootstrapped lazily via the
  backend's pooled `get_db_conn`). The API keeps an in-memory hot cache and loads from
  the DB on a miss. If there's no DB (`VECTOR_DB_URL` unset), it degrades gracefully to
  in-memory — the game never crashes for lack of a database. Reset via `DELETE /seeker/state`.

## Known Limitations

- Identity merging means Krishna resolves to Vishnu's merged node. The 2,006 typed
  identity edges (avatar_of, same_as) from identity.py are built but not yet applied
  to the manifest — applying them would let Krishna and Vishnu be distinct-but-linked.

- Spatial predicates are sparse. Locations show few residents because the graph
  captures relationships well but doesn't always tag characters with spatial predicates
  like "resides_in." Improves as more texts are decoded.

- 70% of the current graph_manifest is fabricated data (16 of 24 texts were Bhagavata
  clones). Rebuild from only the 8 verified texts is pending.
