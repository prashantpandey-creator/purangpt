# PuranGPT Search Architecture Notes

Use these notes when changing retrieval, Guide Mode, Research Mode, corpus loading, or production deployment.

## Do not break search sanctity

- Search must be content-first and cross-language. Never exclude relevant Sanskrit, Russian/Cyrillic, Hindi, or English sources just because the user asked in another language.
- The user query may be translated/enriched into backend search terms, but source eligibility must be based on meaning/relevance, not UI language.
- Preserve original source text for citation/provenance. Normalize only into derived search/prompt surfaces.
- If a source is not in the user's response language, translate/summarize its meaning in the answer while keeping citations tied to the original source record.

## Guruji/Sharma corpus behavior

- Guruji Sri Shailendra Sharma material is first-priority evidence for Guide Mode.
- Production raw path: `/data/purangpt/data/raw_texts/sharma`.
- Production raw Guruji corpus measured on 2026-06-16:
  - 387 raw files
  - about 6,950,220 chars / 1,126,724 approximate words
  - 190 English files, 196 Russian files, 1 mixed file
  - 104 Russian mirror files have English counterparts
  - 283 canonical normalized search texts after mirror dedupe
- Backend keeps `state.sharma_corpus` as original/provenance text and `state.sharma_search_corpus` as derived English-normalized search text.
- Russian mirror files with English counterparts should not create duplicate source hits. Index/search the canonical English partner; preserve the Russian file only as raw provenance.
- For Russian-only Guruji material, the correct next step is an offline local RU-to-EN translation cache, not request-time translation and not dropping the source.

## Research Mode behavior

- Research Mode is two-mode product architecture: `research` and `guide`; do not reintroduce old multi-mode UI assumptions.
- Research answers should start with a short conclusion paragraph synthesizing the retrieved references.
- Then provide "References and Analysis" with clickable citation numbers like `[1]`, explaining what each passage says and why it matters.
- Broad textual questions such as "creation of universe across the puranas" must retrieve across all relevant Purana/source neighborhoods, not only a single preferred text.
- Creation/cosmology retrieval should include Sanskrit anchors such as `sṛṣṭiviṣaya`, `jagatsarga`, `sargādikāraṇam`, `sargaśca pratisargaśca`, `pratisarga`, `sṛṣṭyādi`, `utpatti`, `brahmāṇḍa`, `hiraṇyagarbha`, `sarga`, and `sṛṣṭi`.

## pgvector / production retrieval

- Production uses local pgvector, not Supabase, as the vector/FTS store.
- Backend `VECTOR_DB_URL` points to `postgresql://postgres:postgres@purangpt-pgvector-1:5432/purangpt`.
- The backend container must be attached to both Docker networks:
  - `root_default`
  - `purangpt_default`
- If `index_ready` is false and logs say `database "purangpt" does not exist`, create/restore the `purangpt` database in `purangpt-pgvector-1`.
- Runtime chunk corpus is mounted at `/data/purangpt/data/chunks` into backend `/app/data/chunks`.
- On 2026-06-16, production pgvector FTS table was rebuilt from chunks with 314,309 rows. Embeddings were not fully re-created in that emergency rebuild; it restored FTS/hybrid function availability. A full semantic re-embedding can be done later as a separate long-running rebuild.
- Large chunk files that must be present in the mounted runtime corpus include Bhavishya, Brahma Vaivarta, Padma, Skanda, and Varaha; production previously missed these in `/data/purangpt/data/chunks` while they existed under `/root/purangpt/data/chunks`.

## Provider routing

- **DeepSeek is the SOLE LLM provider** (2026-06 rework). `stream_llm` and startup
  validation route only to DeepSeek; `LLM_PROVIDER` is ignored. Gemini/Groq/Ollama/
  Together/Zhipu code, keys and `stream_*` functions were deleted — do NOT reintroduce
  them or reference a `stream_gemini`/`stream_groq` (they don't exist).
- Chat uses `deepseek-chat`; Deep Research uses `deepseek-reasoner` (its own client).
- There are no longer separate Research/Guide routes — there is one adaptive chat mode.

## Deployment caveat

- Production files can drift from local repo files. When patching backend production, changes have been applied to `/root/purangpt/backend/main.py`, copied into `purangpt_backend:/app/backend/main.py`, and the container restarted.
- If the backend container is recreated from a stale image, re-copy the patched `main.py` or rebuild the image from the corrected source.
