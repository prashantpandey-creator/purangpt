"""world_export — turn any graph location into the Unreal-consumable world JSON.

Rule-0 tool. Replaces the one-off, hand-made `ayodhya_world.json` with a
repeatable, tested, JSON-contract exporter: give it a location name, it queries
the verified knowledge graph and emits exactly the shape
`build_ayodhya_level.py` consumes — so any location (Ayodhya, the smashan,
Govardhan, Benares, ...) becomes a buildable Unreal level with no hand-editing.

Everything traces to the graph:
  - The CAST is assembled by BFS over the dramatis-personae edges (family,
    guru, close-associate) starting from the location's direct residents, then
    ranked by prominence (chapters present) and capped. This reproduces the
    Ramayana cast of Ayodhya from a single resident (Dasharatha) the same way a
    reader's mind does — by following who-is-bound-to-whom.
  - Per-NPC brief/weapons/family come from `character.character_sheet` (graph).
  - NPC placement + the skyline are the ONLY invented data: flagged
    [REASONED EXTENSION] in the aesthetic note, deterministic, never presented
    as cited (same discipline as ART_DIRECTION.md).

Input contract:  run(location, cap=8, hops=2, aesthetic=None, write_to=None,
                     memory=None, seeds=None) -> dict (envelope)
  `seeds` (optional) overrides the place-resident lookup: the BFS roots become the
  given being-names and the relevance anchor becomes the union of THEIR chapters.
  This is how a Sharma-biography level (whose true cast is the bible's named
  encounter-beings, NOT the place's Puranic residents) is built — including for
  places that are `not_found` as graph entities (e.g. "Mahurgad", "Srikalahasti"),
  which still emit a buildable level JSON when seeds are supplied.
Output contract (envelope.data on success): the world JSON —
  { location, aesthetic, skyline, npcs[], n_entities }
matching Content/ayodhya_world.json exactly.
"""
from __future__ import annotations

import json
import math
import os
import sys
from typing import Any, Dict, List, Optional

# Make the tool runnable both as a package module and as a bare script.
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from tools.read_pass.recall import Memory, _norm  # noqa: E402
from narrative_engine import world, character  # noqa: E402

# default graph + ram (the canonical paths the engine uses)
_GRAPH_PATH = os.environ.get("GRAPH_PATH",
                             os.path.join(_BACKEND, "tools/read_pass/out/graph_manifest.json"))
_RAM_PATH = os.environ.get("RAM_PATH",
                           os.path.join(_BACKEND, "tools/read_pass/out/guruji_ram.json"))

# the ART_DIRECTION "light beyond light" default palette (Ayodhya at golden height)
_DEFAULT_AESTHETIC = {
    "key_light_color": [1.0, 0.81, 0.46],
    "key_intensity": 6.0,
    "fog_color": [0.5, 0.32, 0.5],
    "fog_density": 0.02,
    "note": "lit from within; gold = body of consciousness; never grimdark",
}

# graph `kind`s that name something OTHER than a being who could stand in a level
# as an NPC. The decode (esp. the biography corpus) routes these onto a being's
# edges — "Kriya Yoga" (practice) as Babaji's founding, "Ramayana" (text) tied to
# Rama, "constable" (concept) as Sharma's friend — and the BFS then surfaces them
# as cast. A DENYLIST (not an allowlist): 1600 real entities carry an empty/unknown
# kind, so allow-listing character kinds would silently drop genuine unkinded
# characters and regress the Puranic courts. We only exclude what is provably not a
# being. (See FINDINGS.md Bug 3.)
_NON_CHARACTER_KINDS = frozenset({
    "concept", "practice", "text", "place", "plant",
    "object", "substance", "mountain", "clan",
})

# associative (non-family, non-guru) relationships that still bind a being to a
# location's dramatis personae — devotees, allies, ministers, companions.
_ASSOCIATE_HINTS = (
    "devotee", "serves", "servant", "ally", "allies", "companion",
    "friend", "minister", "advisor", "counsel", "general", "commander",
    "disciple", "follower", "attendant", "envoy", "messenger",
)


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data,
            "metadata": metadata, "errors": errors}


# character_sheet scans all ~24k edges every call; the cast assembly hits the
# same names many times (prominence sorts, kin expansion, record build). Memoize
# per (graph, normalized-name) so each being is computed exactly once.
_SHEET_CACHE: Dict[tuple, Any] = {}


def _sheet(name: str, memory: Memory) -> Optional[Dict[str, Any]]:
    key = (id(memory), _norm(name))
    if key not in _SHEET_CACHE:
        cs = character.character_sheet(name, memory)
        _SHEET_CACHE[key] = cs["data"] if (cs.get("success") and cs.get("data")) else None
    return _SHEET_CACHE[key]


def _prominence(name: str, memory: Memory) -> int:
    """Chapter count = how present a being is in the corpus (global weight)."""
    d = _sheet(name, memory)
    return d["identity"].get("chapters_present", 0) if d else 0


_KIND_CACHE: Dict[tuple, str] = {}


def _is_character(name: str, memory: Memory) -> bool:
    """True unless the entity is provably not a character.

    Two gates: (1) the graph `kind` is a denylisted non-being (text/concept/...);
    (2) the NAME is a narratological artifact the decoder mis-types as a 'sage'
    ('Narrator'/'Speaker') — caught by name since the kind passes. Unresolved names
    and the ~1600 empty-kind entities still pass (the gate only removes provable
    non-characters). Reuses character._ARTIFACT_NAMES as the single source.
    """
    if (name or "").strip().lower() in character._ARTIFACT_NAMES:
        return False  # 'Narrator'/'Speaker' — never a character, hard exclude
    ent = character._resolve_entity(_norm(name), memory)
    key = (id(memory), _norm(name))
    if key not in _KIND_CACHE:
        _KIND_CACHE[key] = ((ent.get("kind") or "").lower() if ent else "")
    if _KIND_CACHE[key] in _NON_CHARACTER_KINDS:
        # a denylisted kind is overridden when the entity has kin edges: concepts
        # don't have mothers, so it's a mis-typed being / personified abstraction.
        if ent and ent.get("id") in character._kin_participant_ids(memory):
            return True
        return False
    return True


_CHAPTERS_CACHE: Dict[tuple, frozenset] = {}


def _chapters(name: str, memory: Memory) -> frozenset:
    """The set of chapter-ids a being appears in (for co-presence scoring)."""
    key = (id(memory), _norm(name))
    if key not in _CHAPTERS_CACHE:
        ent = character._resolve_entity(_norm(name), memory)
        _CHAPTERS_CACHE[key] = frozenset(ent.get("chapters", []) if ent else [])
    return _CHAPTERS_CACHE[key]


def _relevance(name: str, anchor: frozenset, memory: Memory) -> float:
    """LOCAL SALIENCE: how much this being belongs to THIS location.

    Not raw co-presence (that still lets the pan-corpus deities — Indra, Brahma —
    leak in, because they DO appear in a few of a place's chapters), and not pure
    locality ratio (that floats obscure one-chapter walk-ons above the
    protagonist). The TF-IDF-flavoured blend `overlap² / total_chapters` rewards
    a being for BOTH appearing here a lot AND this place being a large share of
    where they appear at all:

        Dasharatha: 75²/75   = 75      (here is his whole world)
        Rama:       ~70²/339 ≈ 14      (here is much of his arc)
        Indra:      ~10²/791 ≈ 0.13    (passes through; belongs nowhere in particular)

    So Indra/Brahma sink below the cap while the city's own house leads.
    """
    if not anchor:
        return 0.0
    overlap = len(_chapters(name, memory) & anchor)
    if overlap == 0:
        return 0.0
    total = len(_chapters(name, memory)) or overlap
    return (overlap * overlap) / float(total)


def _kin_names(name: str, memory: Memory) -> List[str]:
    """1-hop dramatis-personae neighbours of `name`: family + gurus + associates.

    Pure graph: only edges character_sheet already partitioned, no invention.
    """
    d = _sheet(name, memory)
    if not d:
        return []
    out: List[str] = []
    for f in d.get("family", []):
        out.append(f.get("name", ""))
    for g in d.get("gurus", []):
        out.append(g.get("name", ""))
    for o in d.get("other_relationships", []):
        rel = (o.get("relationship") or "").lower()
        if any(h in rel for h in _ASSOCIATE_HINTS):
            out.append(o.get("name", ""))
    return [n for n in out if n]


def _assemble_cast(seeds: List[str], anchor: frozenset, memory: Memory,
                   cap: int, hops: int) -> List[str]:
    """Gather the location's dramatis personae and rank by LOCAL RELEVANCE.

    A BFS over family/guru/associate edges (bounded by `hops`) collects the
    candidate pool around the residents. Ranking is then by co-presence with
    THIS location (`_relevance`) — not global fame — so the corpus's most-present
    beings (Indra everywhere; Mahabharata villains from bridge edges) don't
    hijack a place they merely touch, while the place's own family — who saturate
    its chapters — lead. Prominence is only the tiebreak, so among equally-local
    kin the protagonist/ruler still lands front-and-centre. Residents are always
    kept (they define the location). Deterministic throughout.
    """
    seen_norm = set()
    candidates: List[str] = []

    def _fresh(nm: str) -> bool:
        # new, non-duplicate, AND a being (not a text/concept/practice/place...).
        # Mark non-characters seen too, so they're rejected once, not re-resolved.
        nn = _norm(nm)
        if not nn or nn in seen_norm:
            return False
        seen_norm.add(nn)
        return _is_character(nm, memory)

    seed_list = [nm for nm in seeds if _fresh(nm)]
    candidates.extend(seed_list)
    frontier = list(seed_list)

    for _ in range(max(0, hops)):
        nxt: List[str] = []
        for nm in frontier:
            for kin in _kin_names(nm, memory):
                if _fresh(kin):
                    nxt.append(kin)
                    candidates.append(kin)
        if not nxt:
            break
        frontier = nxt

    seed_norms = {_norm(nm) for nm in seed_list}

    def _rank(nm: str):
        # residents pinned to the top (they ARE the location); then local
        # relevance desc, prominence desc, name asc — all deterministic.
        return (0 if _norm(nm) in seed_norms else 1,
                -_relevance(nm, anchor, memory),
                -_prominence(nm, memory),
                _norm(nm))

    return sorted(candidates, key=_rank)[:cap]


def _npc_record(name: str, memory: Memory) -> Optional[Dict[str, Any]]:
    """Build one NPC dict in the ayodhya_world.json shape, from the graph."""
    d = _sheet(name, memory)
    if not d:
        return None
    ident = d["identity"]
    # weapons: the named astras/weapons only (not the source who armed them)
    weapons, seen_w = [], set()
    for w in d.get("weapons", []):
        if w.get("weapon_role") == "weapon":
            wn = w.get("name", "")
            if wn and wn.lower() not in seen_w:
                seen_w.add(wn.lower())
                weapons.append(wn)
    # family: "Name (relationship)" — exactly the shipped format
    family = []
    for f in d.get("family", []):
        fn, fr = f.get("name", ""), f.get("relationship", "")
        if fn:
            family.append("%s (%s)" % (fn, fr) if fr else fn)
    return {
        "name": ident.get("name", name),
        "kind": ident.get("kind", "being"),
        "chapters": ident.get("chapters_present", 0),
        "x": 0.0, "y": 0.0,  # filled by _place()
        "brief": d.get("literal_brief", ""),
        "weapons": weapons,
        "family": family,
    }


def _place(npcs: List[Dict[str, Any]], radius: float = 600.0) -> None:
    """[REASONED EXTENSION] arrange the cast on a ring; index 0 (most prominent)
    front-and-centre at (radius, 0), the rest spread evenly — deterministic."""
    n = len(npcs) or 1
    for i, npc in enumerate(npcs):
        ang = i * (2.0 * math.pi / n)
        npc["x"] = round(radius * math.cos(ang), 1)
        npc["y"] = round(radius * math.sin(ang), 1)


def _skyline(n: int = 5, span: float = 7200.0, depth: float = -7000.0
             ) -> List[List[float]]:
    """[REASONED EXTENSION] a deterministic gold-shikhara silhouette across the
    back of the stage. Heights crest toward the centre (the great temple)."""
    out: List[List[float]] = []
    if n <= 0:
        return out
    for i in range(n):
        t = (i / (n - 1)) if n > 1 else 0.5  # 0..1
        x = round(-span / 2 + t * span, 1)
        y = round(depth - abs(0.5 - t) * 800, 1)  # centre towers stand forward
        base = 700 + (i % 3) * 100
        centre = 1.0 - abs(0.5 - t) * 2.0  # 1 at middle, 0 at edges
        h = round(1400 + centre * 2000, 1)
        out.append([x, y, float(base), h])
    return out


def run(location: str = "Ayodhya", cap: int = 8, hops: int = 2,
        aesthetic: Optional[Dict[str, Any]] = None,
        write_to: Optional[str] = None,
        memory: Optional[Memory] = None,
        seeds: "list[str] | None" = None) -> Dict[str, Any]:
    """Export `location` to the Unreal world JSON. Returns the standard envelope.

    On unknown location / empty name, returns success=False with errors[] —
    never raises for the expected-failure case. EXCEPT: when `seeds` are supplied,
    a `not_found` location is NOT a failure — the cast comes wholly from the seeds,
    so a non-graph place (e.g. "Mahurgad") still builds a valid level JSON.
    """
    meta: Dict[str, Any] = {"location": location, "cap": cap, "hops": hops}

    if not location or not _norm(location):
        return _envelope(False, None, meta,
                         [{"code": "empty_name", "message": "no location name given"}])

    if memory is None:
        try:
            memory = Memory.load(_GRAPH_PATH, _RAM_PATH)
        except Exception as e:  # graph missing / unreadable
            return _envelope(False, None, meta,
                             [{"code": "graph_load_failed", "message": str(e)[:160]}])

    detail = world.location_detail(location, memory)
    found = bool(detail.get("success"))

    # Without seeds, an unknown location is the expected-failure case. WITH seeds,
    # the location is just a label and the cast is the seeds' ego-network, so a
    # `not_found` place is still buildable — don't fail.
    if not found and not seeds:
        errs = detail.get("errors") or [{"code": "not_found",
                                         "message": f"location '{location}' not in graph"}]
        return _envelope(False, None, meta, errs)

    if seeds:
        # SEED OVERRIDE (Sharma-biography levels): skip the place-resident lookup
        # entirely. BFS roots = the bible's named encounter-beings; relevance
        # anchor = the union of THEIR chapters, so the cast ranks by belonging to
        # the seeds' world rather than to the (often wrong, or absent) Puranic
        # place. See narrative_engine/design/world_level_design.md §0/§7.
        bfs_roots = list(seeds)
        residents: List[str] = []
        canonical_loc = (detail["data"]["location"].get("name", location)
                         if found else location)
        anchor_chapters: set = set()
        for s in bfs_roots:
            anchor_chapters |= _chapters(s, memory)
        anchor = frozenset(anchor_chapters)
    else:
        residents = [r["name"] for r in detail["data"].get("residents", []) if r.get("name")]
        canonical_loc = detail["data"]["location"].get("name", location)
        bfs_roots = residents or [canonical_loc]

        # Relevance anchor = the LOCATION's OWN chapters. A cast member belongs here
        # to the degree they co-appear in the place's own chapters. Do NOT union in a
        # resident's full chapter history: a location whose only tie is one tangential
        # resident — e.g. Govardhana, linked to Rama by a single "built" verse
        # (bndp_1,16.44) — would otherwise inherit that resident's ENTIRE epic, and
        # Rama's whole Ayodhya household (Sita/Lakshmana/Bharata/Kaikeyi/Shatrughna,
        # none of whom touch Govardhana) marched in as its "cast." Anchoring on the
        # location's own chapters keeps non-local kin below the cap while the
        # genuinely co-present cast leads. Only when a place has NO chapters of its
        # own do we fall back to its residents' chapters so ranking has something
        # local-ish to use. (See FINDINGS.md — third scope lesson.)
        anchor = frozenset(detail["data"]["location"].get("chapters", []))
        if not anchor:
            fallback = set()
            for r in bfs_roots:
                fallback |= _chapters(r, memory)
            anchor = frozenset(fallback)
    cast = _assemble_cast(bfs_roots, anchor, memory, cap, hops)
    npcs = [r for r in (_npc_record(nm, memory) for nm in cast) if r]
    _place(npcs)

    data = {
        "location": canonical_loc,
        "aesthetic": aesthetic or dict(_DEFAULT_AESTHETIC),
        "skyline": _skyline(),
        "npcs": npcs,
        "n_entities": len(memory.entities),
    }

    meta.update({"n_residents": len(residents), "n_cast": len(npcs),
                 "cast_names": [n["name"] for n in npcs]})

    if write_to:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(write_to)), exist_ok=True)
            with open(write_to, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
            meta["written_to"] = write_to
        except Exception as e:
            return _envelope(False, data, meta,
                             [{"code": "write_failed", "message": str(e)[:160]}])

    return _envelope(True, data, meta, [])


def main(argv: List[str]) -> int:
    as_json = "--json" in argv

    def _opt(flag, default=None):
        return argv[argv.index(flag) + 1] if flag in argv else default

    location = _opt("--location", "Ayodhya")
    cap = int(_opt("--cap", "8"))
    hops = int(_opt("--hops", "2"))
    write_to = _opt("--write")
    seeds_arg = _opt("--seeds")
    seeds = ([s.strip() for s in seeds_arg.split(",") if s.strip()]
             if seeds_arg else None)

    env = run(location, cap=cap, hops=hops, write_to=write_to, seeds=seeds)

    if as_json:
        print(json.dumps(env, indent=2, ensure_ascii=False))
    else:
        if not env["success"]:
            print(f"ERROR: {env['errors'][0]['message']}")
            return 2
        m = env["metadata"]
        print(f"OK: {env['data']['location']} — {m['n_cast']} NPCs "
              f"({', '.join(m['cast_names'])})")
        if m.get("written_to"):
            print(f"  wrote {m['written_to']}")

    return 0 if env["success"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
