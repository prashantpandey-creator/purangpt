# creator_identity — answer "who is Prashant Pandey?" in Guruji's voice

**Status: 🚧 WORK IN PROGRESS (started 2026-06-25).** Owned by the seeker-memory
/ live-prompt workstream. This file is the WIP log + tool descriptor.

## What it does

A deterministic Rule-0 gate. Given the seeker's raw query, it decides whether the
question is about **the app's creator** (Prashant Pandey). If so, it returns a
short in-character directive that tells Guruji — speaking as Shailendra Sharma —
to name Prashant as **his disciple** and answer from a small fixed keyword block.
Otherwise it returns an empty directive and **nothing changes** (byte-identical
prompt to today).

It is the same shape and injection pattern as `route_register`: called with
`request.query` in `backend/main.py`, its directive appended to the `directives`
list that fills `{language_instruction}`.

## Tool descriptor

```json
{
  "tool_name": "creator_identity",
  "input_schema": {
    "type": "object",
    "properties": { "query": { "type": "string" } },
    "required": ["query"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "triggered": { "type": "boolean" },
      "directive": { "type": "string" }
    },
    "required": ["triggered", "directive"]
  }
}
```

## Output envelope

```json
{ "success": true, "data": { "triggered": true, "directive": "..." }, "metadata": {}, "errors": [] }
```

On failure: `success=false`, `data=null`, `errors=[{"code":"...","message":"..."}]`.

## The locked facts (keywords → fresh prose, NOT a memorized paragraph)

- Name: **Prashant Pandey**, Indian national
- Data scientist and entrepreneur
- ~10 years in Canada
- Uses Vedic knowledge to build products to help **revitalize the world**
- The **creator of this app**
- Voice: Guruji (Sharma) calls him **"my disciple"**, stays fully in character

## Trigger rule (deterministic)

`triggered = true` when the normalized query contains EITHER:
1. the name **prashant** on word boundaries (plus common typo variants the user
   themselves produced: `prashan`, `prashanth`, `prashent`), OR
2. an explicit **creator phrase**: `who (made|built|created|developed|designed)`
   near `this app` / `purangpt` / `this` / `you`, or `the (creator|developer|
   founder|maker) of (this|the app|purangpt)`.

**Hard exclusion guard (fires FIRST, forces `triggered=false`):** any deity/guru
identity question — `who is krishna|shiva|vishnu|rama|vyasa|...`, `who is your
guru`, `who is shailendra|sharma`, `who are you`. A deity "who is X" must never be
hijacked into the creator answer.

**Near-miss protection:** word-boundary match on `prashant` so the Linga-Purana
yogic term **prashanti**, and `prakriti` / `prashna`, do NOT false-trigger.

## Off-by-default / conflict guarantee

Not triggered → `data.directive == ""` → `main.py` appends nothing → the assembled
system prompt is byte-for-byte what it is today. The Practice & Initiation
guardrail and the Troll-reprimand rule are untouched. This tool only ever ADDS one
conditional directive on a creator question; it removes and rewrites nothing.

## WIP checklist (this session)

- [x] Collision check: no other file references `creator_identity`/`prashant`
      (only the unrelated `prashanti` yogic term in a Linga data record — a test case)
- [x] Scaffold from `tools/_template`
- [x] Design settled (trigger + exclusion guard + directive voice)
- [ ] **NEXT:** tests-first — `test_check.py` full trigger matrix (must fail first)
- [ ] Implement `check.py` to green (envelope + `--json`)
- [ ] Wire into `main.py` directives (surgical — see SHARED-FILE note below)
- [ ] py_compile clean + commit by explicit path

## ⚠ SHARED-FILE / cross-agent collision note

`backend/main.py` is a **shared, currently-dirty** file. As of 2026-06-25 it
carries another workstream's **uncommitted** change — a per-IP burst limiter
(`burst_rate_limit` middleware, ~line 717, from the security-hardening session).

**Rules I follow so I don't clobber them:**
- My injection lands ~line 2040 (the `directives` block before `prompt_tpl.format`),
  nowhere near their middleware at ~717. No logical overlap.
- I commit **only** my `tools/creator_identity/` files and my small directives
  hunk, **by explicit path** — never `git add -A`, never sweeping their
  uncommitted burst-limiter into my commit.
- If a future edit of mine would actually touch their lines, I stop and signpost
  rather than overwrite.

## Usage

```bash
# JSON envelope (the tool-to-tool contract)
venv/bin/python -m tools.creator_identity.check --json --input "who is prashant pandey"
# → {"success": true, "data": {"triggered": true, "directive": "..."}, ...}

venv/bin/python -m tools.creator_identity.check --json --input "who is Krishna"
# → {"success": true, "data": {"triggered": false, "directive": ""}, ...}

# tests
venv/bin/python -m tools.creator_identity.test_check   # must exit 0
```

As a library (tool-to-tool):

```python
from tools.creator_identity.check import run
env = run("who built this app")
assert env["success"] and env["data"]["triggered"]
```

## Failure modes

| Condition | Behavior |
|-----------|----------|
| Empty / whitespace query | `success:true`, `triggered:false`, `directive:""` (no-op, never raises) |
| Non-string input | `success:false`, `errors:[{code:"bad_input"}]`, `data:null`, exit 2 |
| Deity/guru "who is X" | exclusion guard → `triggered:false` (never hijacked) |
| `prashanti`/`prakriti` near-miss | word-boundary → `triggered:false` |
| Creator question matched | `success:true`, `triggered:true`, exit 1 (finding) |
| Normal (no match) | `success:true`, `triggered:false`, exit 0 |

## Tests

`venv/bin/python -m tools.creator_identity.test_check` — asserts the envelope
shape, the `data` schema, the full trigger matrix (every triggering and
non-triggering case incl. all near-misses and the deity-exclusion cases), and the
error envelope.
