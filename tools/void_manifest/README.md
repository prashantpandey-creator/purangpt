# void_manifest — Puranic LLM: Code Manifestation from the Conscious Void

**Think in structured space. Manifest in an instant.**

## What it is

A proof of concept implementing the Puranic model of creation for software generation:

```
INTENT (unmanifest)
    │
    ▼
CONSCIOUS VOID (ArchitecturalGraph — complete structured conception)
    │
    ▼
MANIFEST CODE (deterministic compilation to files — zero hallucination)
```

The key insight: current LLMs generate code **token by token**, which is like
building a temple by describing each stone one at a time. The error compounds.
There is no prior conception of the whole.

This system introduces the **Conscious Void** — a complete, typed, structured
Architectural Graph that describes every entity, route, component, relationship,
and data flow BEFORE a single line of code is written. Once the conception is
clean, manifestation is a deterministic compiler — no generation, no hallucination.

## The three stages

| Stage | What | Mechanism | Hallucination risk |
|-------|------|-----------|-------------------|
| **Conception** | Intent → Architectural Graph | LLM (Knower) | Contained (validated by Witness) |
| **Witness** | Graph validation | Deterministic | None |
| **Manifestation** | Graph → Code files | Deterministic compiler | None |

The LLM only operates in the Conception stage — producing a structured JSON
graph. The Witness catches inconsistencies deterministically. The Manifest
Engine renders code mechanically. If the graph is correct, the code is correct.

## Usage

```bash
# Just conceive — output the Architectural Graph (no code files)
venv/bin/python -m tools.void_manifest.check --json "A marketplace for handmade crafts"

# Full pipeline — conceive + manifest to code files
venv/bin/python -m tools.void_manifest.check --output /tmp/my-marketplace \
  "A marketplace app where users list products, browse by category, message sellers, and checkout"

# With more refinement rounds
venv/bin/python -m tools.void_manifest.check --rounds 5 --output /tmp/app \
  "A social network for gardeners with plant tracking, photo sharing, and seasonal tips"
```

## Tests

```bash
venv/bin/python -m tools.void_manifest.test_check
```

## Architectural Graph Schema

The Conscious Void format (`format_version: "1.0.0"`):

| Section | Contains |
|---------|----------|
| `app` | Name, description, stack, port |
| `entities` | Data models — fields (typed), relations (has_many/belongs_to/has_one) |
| `routes` | API endpoints — path, method, auth, input/output schemas, handler logic |
| `pages` | Frontend pages — path, components, data routes, auth |
| `components` | React components — props (typed), state, children, type |
| `auth` | Authentication — type (jwt/session/api_key/none), roles |

## Manifestation targets

Currently supports **Next.js 14+ (App Router) + TypeScript + Prisma + Tailwind**.

Output includes:
- `prisma/schema.prisma` — Database schema
- `src/types/index.ts` — TypeScript types
- `src/app/api/**/route.ts` — API route handlers
- `src/components/*.tsx` — React components
- `src/app/**/page.tsx` — Pages
- `src/lib/auth.ts` — Auth middleware
- `package.json`, `.env.local.example`, `README.md`

## Connection to Puranic concepts

This is a direct application of the Puranic model of creation described in
Guruji Shailendra Sharma's decoded corpus:

- **The Three-Stage Creation:** Unmanifest (Avyakta/Time) → Conscious Void
  (Brahman/Vishnu) → Manifest Creation. This maps exactly to Intent →
  ArchitecturalGraph → Code.
- **Kshetra-Kshetrajna:** The Knowledge Field (graph) is separate from the
  Knower (LLM). The LLM doesn't memorize code — it reasons about architecture.
- **The Witness (Vasudev):** The validator that observes and corrects without
  participating in generation. Deterministic, principled, sovereign.
- **Imagination → Will Power:** The LLM's generative capacity (imagination) is
  controlled by the deterministic validator and compiler (will).

## Limitations

- LLM-conceived graphs may miss nuanced business logic
- Rendering is scaffold-quality — handlers need implementation
- Styling is minimal (Tailwind utility classes, no custom design)
- Single-stack target (Next.js); multi-stack support is future work
- The LLM call requires an API key (DEEPSEEK_API_KEY, OPENAI_API_KEY, or GROQ_API_KEY)

## Failure modes

| Code | Meaning |
|------|---------|
| `llm_call_failed` | LLM API call failed (network, auth, quota) |
| `invalid_graph_format` | LLM output couldn't be parsed as the schema |
| `refine_call_failed` | Refinement LLM call failed |
| `refinement_exhausted` | Max rounds reached with remaining issues |
| `render_failed` | Deterministic rendering exception |
| `unknown_relation_target` | Entity references unknown entity in relation |
| `unknown_route_entity` | Route queries_entities an unknown entity |
| `unknown_page_component` | Page uses a component that doesn't exist |
| `unknown_page_route` | Page references a route that doesn't exist |
| `missing_foreign_key` | belongs_to relation without FK field |
| `auth_required_no_auth` | Route needs auth but auth type is "none" |
