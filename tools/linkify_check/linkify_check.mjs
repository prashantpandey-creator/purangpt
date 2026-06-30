/**
 * linkify_check — load the REAL linkifyTerms()/GLOSSARY from
 * src/lib/sanskritGlossary.ts (no re-implementation) and report, for a given
 * answer string, which Sanskrit terms get auto-linked.
 *
 * Why a tool: the linking rules now carry real logic (skip common-vocab words,
 * hard density cap). That is a deterministic decision tree — exactly what Rule 0
 * says to script + test against the real source rather than eyeball in a browser.
 *
 * The .ts source is self-contained (no `@/` imports), so we transpile it
 * in-memory with the TypeScript compiler (already a dep) and import the result.
 *
 * Input:  analyze(markdown: string) -> envelope
 * Output (envelope.data): { linked: [{term, slug}], count, maxLinks, output }
 */
import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, resolve } from "node:path";
import ts from "typescript";

export const ENVELOPE_KEYS = ["success", "data", "metadata", "errors"];

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC = resolve(__dirname, "../../src/lib/sanskritGlossary.ts");

// Transpile the real glossary module to ESM and import it via a data: URL, so
// the test exercises the shipped code path, not a copy.
let _mod = null;
async function loadGlossaryModule() {
  if (_mod) return _mod;
  const tsSource = readFileSync(SRC, "utf8");
  const js = ts.transpileModule(tsSource, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const dataUrl = "data:text/javascript;base64," + Buffer.from(js).toString("base64");
  _mod = await import(dataUrl);
  return _mod;
}

function envelope(success, data, metadata, errors) {
  return { success, data, metadata: metadata ?? {}, errors: errors ?? [] };
}

/** Parse `[term](term:slug)` links out of linkified markdown. */
function extractLinks(md) {
  const re = /\[([^\]]+)\]\(term:([a-z]+)\)/g;
  const out = [];
  let m;
  while ((m = re.exec(md)) !== null) out.push({ term: m[1], slug: m[2] });
  return out;
}

export async function analyze(markdown) {
  if (typeof markdown !== "string") {
    return envelope(false, null, {}, [{ code: "bad_input", message: "markdown must be a string" }]);
  }
  const { linkifyTerms, MAX_LINKS } = await loadGlossaryModule();
  const output = linkifyTerms(markdown);
  const linked = extractLinks(output);
  return envelope(
    true,
    { linked, count: linked.length, maxLinks: MAX_LINKS, output },
    { inputLen: markdown.length },
    []
  );
}

// CLI: read text from --text "..." or stdin, print envelope with --json.
if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  const argv = process.argv.slice(2);
  const asJson = argv.includes("--json");
  let text = "";
  const ti = argv.indexOf("--text");
  if (ti !== -1) text = argv[ti + 1] ?? "";
  const env = await analyze(text);
  if (asJson) {
    console.log(JSON.stringify(env, null, 2));
  } else if (!env.success) {
    console.error(`ERROR: ${env.errors[0].message}`);
    process.exit(2);
  } else {
    const d = env.data;
    console.log(`linked ${d.count}/${d.maxLinks}: ${d.linked.map((l) => l.term).join(", ") || "(none)"}`);
  }
  process.exit(env.success ? 0 : 2);
}
