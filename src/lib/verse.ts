// Render-time cleanup for scripture verses.
//
// The corpus is stored as GRETIL-style romanized Sanskrit with editorial markup that
// reads as gibberish to a normal reader: pada/metrical markers ($ & %), inline verse
// tags (bhp_01.01.001*, ViP_2,13.8, mbh_…), dandas (//), scrape junk ("Mahabharata
// online"), and stray digits glued to words ("1nārada"). This strips the noise and
// turns dandas into line breaks so each verse reads as clean, separated lines.
//
// Non-destructive: display only. The underlying data is untouched (the exact verse
// reference is still shown separately from the verse_range field).
export function cleanVerse(raw: string | undefined | null): string {
  let t = raw || "";
  // Source-scrape junk lines ("Mahabharata online", "... online").
  t = t.replace(/\b[\w-]+ online\b/gi, " ");
  // Inline verse markers: bhp_01.01.001*, ViP_2,13.8, mbh_01.001.001, garp_3,19.1 …
  t = t.replace(/\b[A-Za-z]{2,6}_[\d.,]+\*?/g, " ");
  // GRETIL pada / metrical separators.
  t = t.replace(/[$&%]/g, " ");
  // Dandas → line breaks (verse boundaries).
  t = t.replace(/\s*\/\/+\s*/g, "\n");
  // Stray digits glued to the front of a word (verse numbers that ran together).
  t = t.replace(/(^|\n)\s*\d{1,3}(?=[A-Za-zāīūṛṅñṭḍṇśṣĀĪŪṚṄÑṬḌṆŚṢ])/g, "$1");
  // Tidy whitespace.
  t = t.replace(/[ \t]{2,}/g, " ");
  t = t.replace(/[ \t]*\n[ \t]*/g, "\n").replace(/\n{2,}/g, "\n");
  return t.trim();
}

// Detect encoding-rotted corpus text — e.g. the Skanda Kashi-Khand / Bhavishya rows
// that surface as "i: mb å E EC Er be SE md KE E De OR: GF". Such rot is dominated by
// lone letters and short all-caps Latin OCR fragments, where a clean IAST/Devanagari
// verse is made of long, mostly-lowercase words. Conservative by design: it flags only
// clear rot and never real Sanskrit (long-word passages score ~0 on both signals).
//
// Step 1 of the filter → reclean → rejoin plan: a temporary symptom filter for search.
// Once a text is re-cleaned at the source, its verses pass this check and rejoin
// automatically — there is no text-id blocklist to maintain.
export function isGarbled(raw: string | undefined | null): boolean {
  const t = (raw || "").trim();
  if (t.length < 12) return false;
  const tokens = t.split(/\s+/).filter(Boolean);
  if (tokens.length < 5) return false;
  const letterLen = (tok: string) => tok.replace(/[^\p{L}]/gu, "").length;
  // Fraction of tokens that are 1–2 letters (lone-letter rot).
  const shortFrac = tokens.filter((tok) => letterLen(tok) <= 2).length / tokens.length;
  // Short all-caps Latin fragments are the signature of the OCR rot (E, EC, BN, GF…).
  const capJunk = tokens.filter((tok) => /^[A-Z]{1,3}[:.,;]?$/.test(tok)).length;
  return shortFrac > 0.5 || capJunk >= 3;
}
