export const meta = {
  name: 'bori-batch-decode',
  description: 'Decode one batch of BORI Mahabharata chapters into the inhouse cache (verify-gated fold happens after, in run.py)',
  phases: [
    { title: 'Decode', detail: 'one Claude subagent per chapter → comprehend to schema → write inhouse cache' },
  ],
}

// args: { manifest, batch, size }  — batch is 0-indexed; size defaults 120.
// The full manifest (1987 remaining chapters) was built once by inhouse.dump_prompts.
// Each batch decodes manifest.chapters[batch*size : (batch+1)*size] into the
// prompt-keyed inhouse cache. Idempotent: a chapter already cached is skipped by the
// subagent (it checks first), so re-running a batch is cheap and resume-safe.
const manifestPath = (args && args.manifest) || 'tools/read_pass/out/bori_full_manifest.json'
const batch = (args && Number.isInteger(args.batch)) ? args.batch : 0
const size = (args && args.size) || 120

const lo = batch * size
// the script can't read the manifest, so the subagents discover their own bounds;
// we pass the explicit index list and let each one no-op if its index is past the end.
const idxs = Array.from({ length: size }, (_, i) => lo + i)

phase('Decode')
log(`BORI batch ${batch}: chapters at manifest idx [${lo}:${lo + size}]`)

const RECEIPT = {
  type: 'object',
  required: ['index', 'cache_written'],
  properties: {
    index: { type: 'integer' },
    chapter_label: { type: 'string' },
    prompt_key: { type: 'string' },
    cache_written: { type: 'boolean', description: 'true if JSON written to inhouse cache (or already cached)' },
    already_cached: { type: 'boolean' },
    out_of_range: { type: 'boolean', description: 'true if this index is past the end of the manifest' },
    entities: { type: 'integer' },
    relationships: { type: 'integer' },
    teachings: { type: 'integer' },
    note: { type: 'string' },
  },
}

const receipts = await parallel(idxs.map((idx) => () =>
  agent(
    `You are decoding ONE chapter of the Mahabharata (BORI critical edition) into a structured comprehension record for the PuranGPT corpus graph. Work from repo root: /Users/badenath/projects/vedic puran/purangpt

STEP 0 — bounds + idempotency check. Run from repo root:
  venv/bin/python -c "
import json, os
from tools.read_pass import inhouse
man = json.load(open('${manifestPath}'))
chs = man['chapters']
i = ${idx}
if i >= len(chs):
    print('OUT_OF_RANGE'); raise SystemExit(0)
ch = chs[i]
path = os.path.join(inhouse.DEFAULT_CACHE, ch['prompt_key']+'.json')
print('LABEL', ch['chapter_label'])
print('KEY', ch['prompt_key'])
print('CACHED', os.path.exists(path))
"
- If it prints OUT_OF_RANGE: return StructuredOutput {index:${idx}, out_of_range:true, cache_written:false}. STOP.
- If CACHED True: this chapter is already decoded. Return {index:${idx}, chapter_label:<LABEL>, prompt_key:<KEY>, already_cached:true, cache_written:true}. STOP — do NOT redo it (idempotent/resume).
- Else continue.

STEP 1 — read your prompt. Read ${manifestPath}, take chapters[${idx}]. Its "prompt" field is the COMPLETE comprehension prompt (Sharma lens + source verses with mbh_ markers + the JSON schema). Do exactly what it instructs.

STEP 2 — comprehend to valid JSON (chapter_summary, entities, relationships, story, teachings).
CRITICAL GROUNDING RULE — every node is verify-gated downstream: any entity/relationship/teaching whose cited verse marker (verse_ranges, e.g. "mbh_01.009.012") does NOT literally appear in THIS chapter's source verses will be PRUNED and discarded. So:
  - Cite ONLY mbh_ markers you actually see in this chapter's source block.
  - NEVER invent/extrapolate markers. NEVER cite bhp_ markers (those are the lens example, not your source).
  - Prefer fewer well-grounded nodes over many speculative ones. Fill verse_ranges on every node.
  - Keep entity.kind within the schema enum. Do not assert famous cross-text identities (e.g. "X is Vishnu") unless THIS chapter's verses state it.

STEP 3 — write to the inhouse cache (the fold pass finds it by hashing the exact prompt):
  venv/bin/python -c "
import json
from tools.read_pass import inhouse
man = json.load(open('${manifestPath}'))
ch = man['chapters'][${idx}]
my_json = r'''<PASTE YOUR COMPREHENSION JSON>'''
obj = json.loads(my_json)
path = inhouse.write_response(inhouse.DEFAULT_CACHE, ch['prompt'], json.dumps(obj, ensure_ascii=False))
print('WROTE', path)
"
Ensure it prints WROTE with no exception; if json.loads fails, fix and retry.

STEP 4 — return StructuredOutput: index ${idx}, the chapter_label and prompt_key, cache_written true (false only if you truly couldn't write valid JSON), and counts of entities/relationships/teachings. Any caveat in note.`,
    { label: `b${batch}:ch${idx}`, phase: 'Decode', schema: RECEIPT, agentType: 'general-purpose' }
  )
))

const ok = receipts.filter(Boolean)
const inRange = ok.filter((r) => !r.out_of_range)
const written = inRange.filter((r) => r.cache_written)
const freshDecoded = written.filter((r) => !r.already_cached)
const totalNodes = inRange.reduce((s, r) => s + (r.entities || 0) + (r.relationships || 0) + (r.teachings || 0), 0)

log(`batch ${batch}: ${inRange.length} in range, ${written.length} cached (${freshDecoded.length} freshly decoded), ${totalNodes} raw nodes`)

return {
  batch,
  in_range: inRange.length,
  cache_written: written.length,
  freshly_decoded: freshDecoded.length,
  already_cached: written.length - freshDecoded.length,
  failed_write: inRange.length - written.length,
  total_raw_nodes: totalNodes,
  failures: inRange.filter((r) => !r.cache_written).map((r) => ({ index: r.index, note: r.note || '' })),
}
