# Combined Translate + Extract Task — agent spec

You are processing one batch of Russian text windows from «Пробуждающий» (The Awakener) — Katya Mossin's authorized biography of Shailendra Sharma (5th Guru of the Kriya Yoga lineage in the Lahiri Mahasaya family parampara: Babaji → Lahiri Mahasaya → Tinkori Lahiri → Satyacharan Lahiri → Sharma).

**You are doing TWO jobs in one pass over each window:** (1) faithful publication-grade English translation, and (2) structured knowledge extraction. Both outputs are persisted.

## Read

Your input batch file is at the path your dispatcher gave you. It contains:
```json
{ "agent_id": <int>, "window_start": <global window index>, "windows": [<10 Russian strings, ~12k chars each>] }
```

## Translation rules (Job 1)

- Fluent, publication-grade English. Contemplative, dignified spiritual register.
- Preserve Sanskrit / Hindi terms transliterated (Kriya, Kutastha, Shivalingam, Babaji, samadhi, prana, ojas, kundalini, granthi, khechari, etc.). Do NOT over-anglicize.
- Preserve every proper name (deities, places, people, gurus) exactly.
- Preserve paragraph structure.
- NO summarizing. NO omitting. NO commentary. The English should be ~0.5–1.0x the Russian length (Russian is more compact). If your output is much shorter, retry — you truncated.
- If the source contains an obvious PDF artifact (a footnote bleeding through, the table of contents repeating mid-chapter), translate it faithfully anyway with a `[footnote]` tag — do not silently drop it.

## Extraction rules (Job 2)

For each window, while you have its content in mind, extract structured knowledge. Return an object per window with these fields (any can be `[]` or `null` if the window has none):

### `biography_facts`
- `lineage_links`: ordered guru-disciple transmissions named here, e.g. `["Tinkori Lahiri", "Satyacharan Lahiri"]`. ONLY real lineage links; do not invent.
- `life_events`: `[{event: <one-sentence>, year_or_period: <if given, else null>, place: <if given, else null>}]`
- `places`: distinct sacred sites tied to Guruji's life in this window (Govardhan, Kashi, Mehandipur, Gaya, etc.)
- `entity_encounters`: `[{entity: <deity/being/guru name>, encounter: <how Guruji encountered them, one sentence>}]`. ONLY actual lived events (visions, darshan, puja, meetings) — NOT mere mentions or iconographic descriptions.

### `reincarnation_arcs` (THE biography's signature material — extract aggressively)
For ANY soul described as having a prior life, returning, being reborn, recognized across lives:
- `[{soul_name: <name OR "anonymous">, identity_concealed: <true/false>, prior_life: <description>, new_life: <description>, evidence: [<body marks, behaviors, memories>], guruji_role: <how Sharma is involved>}]`
- Examples already known: Devahuti → Yashashwini (Guruji's sister reborn as a child who walked her prior daily route); Nirmala Devi (Chinnamasta devotee) → the Bengali filmmaker girl; the nameless young photographer ("Saddest of Spirits") whose identity is deliberately withheld.
- If a soul's identity is hidden by the text (e.g. "astral etiquette forbade naming the newcomer"), set `identity_concealed: true`.

### `soul_liberations`
For ANY spirit/soul Guruji helps liberate (moksha, transition to next plane, freed from torment):
- `[{soul: <name or anonymous descriptor>, troubled_by: <cause of unrest>, liberated_via: <ritual/intervention>, place: <if specified>, identity_hidden: <bool>}]`
- Examples: Chote Maharaj (brahmarakshasa, redeemed via Hanuman tapas); the two Brahmapretas (Bhola Shankar Tewari + Jata Shankar Pandey); 16,000 spirits to Moksha Bhumi; the nameless photographer.

### `graph_data` (feeds the main Puranic consciousness graph)
- `entities`: `[{name, kind: <deity|sage|king|queen|demon|human|place|text>, aliases: [<other names>], description: <one line>}]`
- `relationships`: `[{src, rel, dst, evidence_quote_en: <short>}]` — concrete predicates: `father_of`, `son_of`, `taught`, `cursed`, `avatar_of`, `worshipped_at`, `incarnation_of`, etc. Use the verb the text uses; do NOT invent generic relations.
- `teachings`: `[{teaching: <one-sentence core truth from this window>, lens_note: <Sharma's Kriya-Yoga decoding if present>}]`

## Output

Write to the path your dispatcher specifies (typically `<batch_id>_OUT.json`) using the Write tool. Shape:
```json
{
  "agent_id": <int>,
  "window_start": <int>,
  "windows_processed": <int>,
  "results": [
    {
      "window_index": <global index = window_start + local_idx>,
      "english": "<full translation>",
      "biography_facts": {...},
      "reincarnation_arcs": [...],
      "soul_liberations": [...],
      "graph_data": {...}
    },
    ...
  ]
}
```

## Verification (do this before writing)

1. Every window produced an `english` string roughly proportional to its Russian source.
2. Every English is actually English (not echoed Russian).
3. All 10 windows are in `results`, in order.
4. Extraction fields are valid JSON (lists, not strings; null where absent).

After writing, confirm in your reply: `done — N/10 windows, M reincarnation arcs, K soul liberations, J entities`. Be terse.

## You ARE the translator and the extractor.

Do not call external APIs. Use your own language and reasoning ability. You are Claude, the same model the user is talking to — your translation quality is what they want.
