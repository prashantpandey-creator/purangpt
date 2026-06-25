"""narrative_engine — the game-facing layer over PuranGPT's knowledge graph.

Translates "I'm standing in Ayodhya, what do I see?" into graph queries and
returns world state any client (text adventure, Godot, UE5, web) can render.

Architecture:
  world.py      — location/entity queries, spatial model of Puranic geography
  character.py  — NPC factsheets, abilities, dialogue grounding
  combat.py     — astra rules, guna-based ability resolution
  seeker.py     — player state: guna balance, tapasya, boons, karma
  narrative.py  — story progression, dharmic choices, consequence chains
  api.py        — FastAPI router exposing all of the above as JSON endpoints
"""
