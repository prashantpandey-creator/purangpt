/**
 * Tests for linkify_check — exercises the REAL linkifyTerms()/GLOSSARY.
 * Run: node tools/linkify_check/test_linkify_check.mjs   (from purangpt-next/)
 * Must exit 0.
 *
 * Pins the "organic, meaningful" highlighting behaviour the user asked for:
 *   - words already in common English (yoga, karma, om, guru, dharma…) are
 *     NEVER auto-linked, even when present;
 *   - genuinely unfamiliar terms (ojas-tier: vairagya, viveka, prakriti…) ARE
 *     linked;
 *   - never more than MAX_LINKS total per answer;
 *   - code spans / existing links are left untouched;
 *   - each term links at most once.
 */
import { analyze, ENVELOPE_KEYS } from "./linkify_check.mjs";

let failures = 0;
function assert(cond, msg) {
  if (!cond) { console.error(`  FAIL: ${msg}`); failures++; }
}

function linkedSlugs(data) { return data.linked.map((l) => l.slug); }

async function test_envelope_shape() {
  const env = await analyze("hello world");
  assert(JSON.stringify(Object.keys(env).sort()) ===
         JSON.stringify([...ENVELOPE_KEYS].sort()), "envelope keys");
  assert(env.success === true, "success true");
  assert(Array.isArray(env.data.linked), "linked is array");
  console.log("  ok  envelope_shape");
}

async function test_common_words_never_linked() {
  // Every word here is in general English usage → expect ZERO links.
  const md = "The path of yoga and karma leads to moksha. Chant Om, honour your guru, " +
             "walk your dharma, and you transcend maya, samsara, and the chakra of rebirth.";
  const { data } = await analyze(md);
  assert(data.count === 0, `common-only text linked ${data.count} (expected 0): ${linkedSlugs(data)}`);
  console.log("  ok  common_words_never_linked");
}

async function test_esoteric_words_linked() {
  // These are genuinely unfamiliar → expect them linked (up to the cap).
  const md = "True freedom asks for vairagya and viveka, a steady santosha, and the " +
             "discernment of purusha from prakriti.";
  const { data } = await analyze(md);
  const slugs = linkedSlugs(data);
  assert(data.count > 0, "esoteric text should link something");
  assert(slugs.includes("vairagya"), `expected vairagya linked, got ${slugs}`);
  assert(slugs.includes("viveka"), `expected viveka linked, got ${slugs}`);
  console.log("  ok  esoteric_words_linked");
}

async function test_density_cap() {
  // Six esoteric terms present; cap must hold the link count to maxLinks.
  const md = "vairagya, viveka, santosha, prakriti, purusha, and sadhana are the marks of the seeker.";
  const { data } = await analyze(md);
  assert(data.count <= data.maxLinks, `count ${data.count} exceeds cap ${data.maxLinks}`);
  assert(data.count === data.maxLinks, `expected to hit cap ${data.maxLinks}, got ${data.count}`);
  console.log("  ok  density_cap");
}

async function test_each_term_once() {
  const md = "vairagya now, vairagya again, and vairagya once more.";
  const { data } = await analyze(md);
  const vair = linkedSlugs(data).filter((s) => s === "vairagya");
  assert(vair.length === 1, `vairagya linked ${vair.length} times (expected 1)`);
  console.log("  ok  each_term_once");
}

async function test_code_and_links_protected() {
  const md = "Use `vairagya` in code, and [viveka](term:viveka) is already a link.";
  const { data } = await analyze(md);
  // Nothing inside the inline-code span or the existing link may be rewritten —
  // so linkify must return the input UNCHANGED (output === input). (data.count
  // is 1 here, but that is the pre-existing viveka link in the input, not one we
  // added — hence the equality check rather than a count check.)
  assert(data.output === md, `protected spans were rewritten: ${data.output}`);
  console.log("  ok  code_and_links_protected");
}

async function test_mixed_realistic_answer() {
  // A realistic Guruji answer: common words flow as plain text, one or two
  // unfamiliar terms glow. This is the "invitation, not an index" target.
  const md = "Your dharma is not a burden but a door. The restless mind is calmed not " +
             "by force but by vairagya — a quiet letting-go — and steadied by santosha, " +
             "contentment with what is. This is the yoga the lineage has always taught.";
  const { data } = await analyze(md);
  const slugs = linkedSlugs(data);
  assert(!slugs.includes("dharma"), "dharma (common) must not link");
  assert(!slugs.includes("yoga"), "yoga (common) must not link");
  assert(slugs.includes("vairagya"), "vairagya should link");
  assert(data.count <= data.maxLinks, "cap respected");
  console.log(`  ok  mixed_realistic_answer (linked: ${slugs.join(", ")})`);
}

const tests = [
  test_envelope_shape,
  test_common_words_never_linked,
  test_esoteric_words_linked,
  test_density_cap,
  test_each_term_once,
  test_code_and_links_protected,
  test_mixed_realistic_answer,
];

for (const t of tests) await t();

if (failures > 0) {
  console.error(`\n${failures} assertion(s) FAILED.`);
  process.exit(1);
}
console.log(`\nAll ${tests.length} linkify_check tests passed.`);
