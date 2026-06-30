import { NextResponse } from "next/server";

// ---------------------------------------------------------------------------
// /api/guru-suggestions — Daily-refreshed, scripture-grounded prompt chips
// ---------------------------------------------------------------------------
// Architecture:
//  • On cache hit (< 24h old): returns cached JSON instantly.
//  • On cache miss: calls the backend LLM to generate 3 topic-mapped prompts.
//    No external news API required — the LLM generates internally plausible
//    "trending" spiritual angles. Results cached in-memory for the process.
//  • Always falls back to 3 evergreen prompts if the LLM call fails.
// ---------------------------------------------------------------------------

export const runtime = "nodejs";

interface Suggestion {
  topic: string;
  prompt: string;
  color: "saffron" | "gold" | "blue";
}

// A pool of evergreen, scripture-grounded chips. When the LLM is unavailable we
// shuffle this and take 3, so the refresh button always yields a visibly fresh
// set instead of repeating the same trio.
// A large, deliberately VARIED pool — stories, characters, cosmology, piercing
// philosophy, practice, raw human dilemmas, and "did the texts really say that?"
// curiosities. The whole point is range, so suggestions never feel repetitive.
// (color is overwritten on pick; the UI now cycles its own pastel set.)
const EVERGREEN_POOL: Suggestion[] = [
  // ── Stories & characters ──
  { topic: "Karna's tragic loyalty", prompt: "Karna learned the Pandavas were his own brothers yet fought them to the death — what does the Mahabharata teach through his loyalty and fate?", color: "gold" },
  { topic: "Draupadi's burning question", prompt: "When Draupadi asked whether a man who has already gambled away himself can stake his wife, what does the Mahabharata reveal about dharma?", color: "gold" },
  { topic: "Nachiketa bargains with Death", prompt: "In the Katha Upanishad a boy faces Yama himself and demands to know what lies beyond death — what answer does the Lord of Death finally give?", color: "gold" },
  { topic: "Prahlada and the pillar", prompt: "How does Prahlada's unshakeable devotion — against his own tyrant father — summon Narasimha from a stone pillar, and what does it mean for faith?", color: "gold" },
  { topic: "Savitri outwits Yama", prompt: "How did Savitri follow Death itself and win her husband's life back through sheer wit and an unbending vow?", color: "gold" },
  { topic: "Eklavya's thumb", prompt: "Eklavya gave his thumb to a teacher who never taught him — what does this unsettling story say about devotion, fairness, and the guru?", color: "gold" },
  { topic: "Markandeya inside the god", prompt: "The sage Markandeya wandered for ages inside the body of the sleeping Vishnu — what does that vision reveal about reality and illusion?", color: "gold" },
  { topic: "Yudhishthira's loyal dog", prompt: "At heaven's gate Yudhishthira refused to enter without a stray dog who had followed him — why does the Mahabharata end on this test?", color: "gold" },
  // ── Cosmology & the mind-bending ──
  { topic: "The churning of the ocean", prompt: "Why did gods and demons together churn the cosmic ocean, and what does Shiva drinking the world-poison reveal about sacrifice?", color: "gold" },
  { topic: "The four ages of the world", prompt: "The Puranas say we live in Kali Yuga, the darkest age — what are the four yugas, and what happens when the cycle finally ends?", color: "gold" },
  { topic: "A king who time-traveled", prompt: "King Kakudmi visited Brahma's realm briefly and returned to find ages had passed on earth — did the Puranas describe time dilation long ago?", color: "gold" },
  { topic: "The fourteen worlds", prompt: "What are the fourteen lokas of Puranic cosmology, and where does the soul actually travel between one life and the next?", color: "gold" },
  { topic: "When the cosmos dissolves", prompt: "What do the Puranas say happens at pralaya — the great dissolution — when even the gods melt back into the One?", color: "gold" },
  { topic: "Why Vishnu keeps descending", prompt: "Vishnu comes as fish, tortoise, boar, man-lion, then man — what does the order of the ten avatars quietly hint about evolution?", color: "gold" },
  // ── Upanishadic philosophy ──
  { topic: "Thou art That", prompt: "What do the Upanishads mean by 'Tat Tvam Asi' — that the Self within you is the very same ground as all of reality?", color: "gold" },
  { topic: "Not this, not this", prompt: "How does the Upanishadic method of 'neti, neti' strip away everything we are not until only the unnameable remains?", color: "gold" },
  { topic: "The five veils of the Self", prompt: "The Taittiriya Upanishad maps five sheaths over the Self — how do food, breath, mind, intellect and bliss hide who we really are?", color: "gold" },
  { topic: "Who is the witness?", prompt: "Thoughts and feelings come and go — but who is the silent one watching them? Is that the Atman the Upanishads point to?", color: "gold" },
  // ── Yoga & practice ──
  { topic: "The eight limbs of yoga", prompt: "What are Patanjali's eight limbs, and how do ethics, posture and breath actually prepare the mind for stillness?", color: "gold" },
  { topic: "Harder than the wind", prompt: "Krishna says the mind is harder to restrain than the wind — what exact method do he and the Yoga Sutras prescribe to tame it?", color: "gold" },
  { topic: "Three roads to the divine", prompt: "The Gita lays out the paths of action, devotion and knowledge — how do I tell which one is truly mine?", color: "gold" },
  { topic: "The bridge of the breath", prompt: "What do the yogic texts mean when they call prana, the life-breath, the bridge between the body and pure consciousness?", color: "gold" },
  // ── Raw human dilemmas, reframed ──
  { topic: "When duty wounds love", prompt: "Like Arjuna facing his own kin, what do we do when our duty means hurting the people we love — and how does Krishna resolve it?", color: "gold" },
  { topic: "Ambition without clinging", prompt: "Can I chase a great goal and still be free? What is the Gita's secret of acting with everything yet releasing the result?", color: "gold" },
  { topic: "When someone betrays you", prompt: "When a trusted one betrays us, what do the epics teach about anger, justice, and the harder strength of letting go?", color: "gold" },
  { topic: "A grief that won't lift", prompt: "How do the scriptures meet a grief that will not lift — and what do they say the one we lost has actually become?", color: "gold" },
  { topic: "Wealth and the soul", prompt: "Is wealth a spiritual trap or a sacred duty? What do the texts say about earning and giving with a clear heart?", color: "gold" },
  { topic: "The ego's disguises", prompt: "How do the Upanishads expose the subtle disguises of the ego — and what is left standing when the 'I' is finally seen through?", color: "gold" },
  // ── Curiosities ──
  { topic: "Weapons of the gods", prompt: "The epics describe astras that could scorch the sky — what were these divine weapons, and what were the rules that bound their use?", color: "gold" },
  { topic: "The soul's journey after death", prompt: "Step by step, what do the Garuda Purana and the Upanishads say the soul experiences from the last breath to the next birth?", color: "gold" },
];

/** Shuffle the pool and return 3 chips with stable rotating colors. */
function pickEvergreen(): Suggestion[] {
  const shuffled = [...EVERGREEN_POOL].sort(() => Math.random() - 0.5).slice(0, 3);
  return shuffled.map((s, i) => ({ ...s, color: COLORS[i % 3] }));
}

const COLORS: Suggestion["color"][] = ["saffron", "gold", "blue"];

// ── LLM providers ────────────────────────────────────────────────────────
// DeepSeek is primary; Gemini is the fallback. (OpenAI intentionally dropped.)
// Gemini key is read from the common alias names so it matches whatever the
// server already has configured.
const GEMINI_MODEL = process.env.GEMINI_MODEL || "gemini-2.0-flash";

function geminiKey(): string {
  return (
    process.env.GEMINI_API_KEY ||
    process.env.GOOGLE_GEMINI_API_KEY ||
    process.env.GOOGLE_GENERATIVE_AI_API_KEY ||
    process.env.GOOGLE_API_KEY ||
    ""
  );
}

/** Parse model text into up to 3 valid suggestions, tolerating ```json fences. */
function parseSuggestions(raw: string): Suggestion[] | null {
  if (!raw) return null;
  const cleaned = raw.trim().replace(/^```(?:json)?\n?/, "").replace(/\n?```$/, "");
  try {
    const parsed = JSON.parse(cleaned);
    if (!Array.isArray(parsed) || parsed.length === 0) return null;
    const out = parsed.slice(0, 3).map((s: any, i: number): Suggestion => ({
      topic: (String(s?.topic ?? "").trim() || "Reflection").slice(0, 48),
      prompt: String(s?.prompt ?? "").trim().slice(0, 240),
      color: ["saffron", "gold", "blue"].includes(s?.color) ? s.color : COLORS[i % 3],
    })).filter((s) => s.prompt.length > 0);
    return out.length ? out : null;
  } catch {
    return null;
  }
}

async function callDeepSeek(prompt: string): Promise<string | null> {
  const key = process.env.DEEPSEEK_API_KEY;
  if (!key) return null;
  try {
    const res = await fetch("https://api.deepseek.com/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
      body: JSON.stringify({
        model: process.env.DEEPSEEK_MODEL || "deepseek-chat",
        messages: [{ role: "user", content: prompt }],
        max_tokens: 500,
        temperature: 0.85,
      }),
      signal: AbortSignal.timeout(12_000),
    });
    if (!res.ok) return null;
    const json = await res.json();
    return json.choices?.[0]?.message?.content?.trim() || null;
  } catch {
    return null;
  }
}

async function callGemini(prompt: string): Promise<string | null> {
  const key = geminiKey();
  if (!key) return null;
  try {
    const res = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${key}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: {
            temperature: 0.85,
            maxOutputTokens: 600,
            responseMimeType: "application/json",
          },
        }),
        signal: AbortSignal.timeout(12_000),
      }
    );
    if (!res.ok) return null;
    const json = await res.json();
    return (
      json.candidates?.[0]?.content?.parts?.map((p: any) => p?.text ?? "").join("").trim() || null
    );
  } catch {
    return null;
  }
}

/** Try DeepSeek first, then Gemini. Returns parsed suggestions or null. */
async function llmSuggestions(prompt: string): Promise<Suggestion[] | null> {
  return parseSuggestions((await callDeepSeek(prompt)) || "")
    ?? parseSuggestions((await callGemini(prompt)) || "");
}

function hashThemes(themes: string[]): string {
  return themes.map((t) => t.toLowerCase().slice(0, 60)).join("|").slice(0, 400);
}

/** Condense a long user question into a 3–5 word topic label. */
function shortLabel(text: string): string {
  const stop = new Set([
    "the", "a", "an", "of", "to", "in", "on", "and", "or", "what", "how", "does",
    "do", "is", "are", "i", "my", "me", "when", "why", "for", "about", "with",
    "can", "should", "according", "explain", "tell",
  ]);
  const words = text
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .split(/\s+/)
    .filter((w) => w.length > 2 && !stop.has(w.toLowerCase()));
  const pick = (words.length ? words : text.split(/\s+/)).slice(0, 4).join(" ");
  const label = pick.charAt(0).toUpperCase() + pick.slice(1);
  return label.slice(0, 36) || "Your path";
}

/** Lowercase clause form of a theme for weaving into a sentence. */
function clause(text: string): string {
  return text.replace(/[?.!\s]+$/g, "").replace(/\s+/g, " ").trim().slice(0, 70).toLowerCase();
}

/** Deterministic, meaningful personalization without needing an LLM. */
function synthesizePersonal(themes: string[]): Suggestion[] {
  const templates = [
    (t: string) => `Earlier you reflected on ${clause(t)} — what do the Puranas and the Gita add that deepens this?`,
    (t: string) => `Continuing your inquiry into ${clause(t)}, what daily sadhana does scripture prescribe?`,
    (t: string) => `How would Guruji counsel someone still sitting with ${clause(t)} when doubt arises?`,
  ];
  const uniq = Array.from(new Set(themes.map((t) => t.trim()).filter(Boolean)));
  return uniq.slice(0, 3).map((t, i) => ({
    topic: shortLabel(t),
    prompt: templates[i % templates.length](t),
    color: COLORS[i % COLORS.length],
  }));
}

// Distinct "lenses" — three are drawn at random each generation so the trio is
// varied and never settles into the same handful of themes.
const LENSES = [
  "a vivid story or character from the Mahabharata, Ramayana, or a Purana (e.g. Karna, Draupadi, Prahlada, Nachiketa, Markandeya, Savitri, Eklavya) and the dilemma they faced",
  "a mind-bending cosmological idea (the four yugas and cyclic time, pralaya / cosmic dissolution, the fourteen lokas, the churning of the ocean, time dilation, Vishnu's ten avatars)",
  "a piercing Upanishadic insight (Tat Tvam Asi, neti-neti, the five koshas, the witness-Self, maya, the deathless Atman)",
  "a concrete question of yoga or sadhana (Patanjali's eight limbs, taming the mind, prana and the breath, the three paths of action / devotion / knowledge)",
  "a raw, real human dilemma reframed by scripture (betrayal, ambition vs detachment, grief, wealth and dharma, anger, the ego, a duty that wounds loved ones)",
  "a surprising 'did the ancient texts really say that?' curiosity (divine astras / weapons, vimanas, the soul's step-by-step journey after death, why the gods take human form)",
];

function pick3<T>(arr: T[]): T[] {
  return [...arr].sort(() => Math.random() - 0.5).slice(0, 3);
}

// ── Context-aware generation ───────────────────────────────────────────────
// Everything the moment can tell us, woven into one prompt. Nothing hard-coded
// to a position — the LLM composes from the live context; the pool is only a
// last-resort failsafe.
interface Ctx {
  themes: string[];        // recent conversation themes (any user, from local history)
  language: string;        // app UI language (en/hi/ru…)
  timezone: string;        // IANA tz, e.g. "Asia/Kolkata" — our best region/country signal
  localHour: number | null;// 0-23 in the seeker's local time
  localDate: string;       // human date string from the client
  acceptLanguage: string;  // browser Accept-Language header (locale + country subtag)
}

function partOfDay(h: number | null): string {
  if (h == null || !Number.isFinite(h)) return "";
  if (h < 5) return "the small hours";
  if (h < 12) return "morning";
  if (h < 17) return "afternoon";
  if (h < 21) return "evening";
  return "night";
}

function regionHint(ctx: Ctx): string {
  const bits: string[] = [];
  if (ctx.timezone) bits.push(`timezone ${ctx.timezone}`);
  if (ctx.acceptLanguage) bits.push(`browser locale ${ctx.acceptLanguage.split(",")[0]}`);
  if (ctx.language) bits.push(`app language ${ctx.language}`);
  return bits.join(", ");
}

async function generateContextual(ctx: Ctx): Promise<{ suggestions: Suggestion[]; personalized: boolean }> {
  const lenses = pick3(LENSES);
  const hasHistory = ctx.themes.length > 0;
  const region = regionHint(ctx);
  const tod = partOfDay(ctx.localHour);
  const date = ctx.localDate || new Date().toDateString();

  const historyBlock = hasHistory
    ? `The seeker has recently explored these themes (most recent first):
${ctx.themes.slice(0, 6).map((t, i) => `${i + 1}. ${t}`).join("\n")}
Make 1-2 of the three chips a genuine NEXT STEP from these (deepen, connect, or branch — never a repeat), and at least 1 fresh and surprising.`
    : `This seeker is new — no history yet. Make all three vivid and inviting; there is no fixed objective, so lean on the moment (date, season, festival, region) to feel timely.`;

  const systemPrompt = `You are the curator of a sacred-text AI for the Hindu scriptures (18 Mahapuranas, Ramayana, Mahabharata, Bhagavad Gita, Upanishads, Yoga Sutras). Craft exactly 3 prompt chips a seeker will *itch* to tap — vivid, specific, surprising, and CONTEXT-AWARE of this exact moment.

This moment:
- Today is ${date}${tod ? `, ${tod} for the seeker` : ""}.
- Seeker's locale: ${region || "unknown"}. Infer their region/country and culture; only where it feels natural, let it tint an angle (a regional deity, temple, pilgrimage, or festival). Never force it or state the region outright.
- SEASON / FESTIVAL: consider the season and any major Hindu festival within ~7 days of today (Diwali, Navaratri, Holi, Janmashtami, Maha Shivaratri, Ram Navami, Guru Purnima, Ekadashi, Makar Sankranti, Ganesh Chaturthi, Raksha Bandhan…). If one is near, anchor exactly ONE chip to it, naturally.
${historyBlock}

For the remaining chips, draw from these distinct angles (in order; a festival/history chip may take a slot):
1. ${lenses[0]}
2. ${lenses[1]}
3. ${lenses[2]}

Rules:
- Name the actual story, character, idea, festival, or text — concrete, never vague.
- Each "prompt" is a sincere, curious question (15-28 words) answerable from the scriptures above.
- BANNED generic phrasings (never use, nor any near-paraphrase): "inner peace", "dharma in dark times", "suffering and impermanence", "finding your path", "restless mind", "letting go", "equanimity". Avoid doom / current-news framing.
- Vary sentence shapes; no two chips begin the same way.

Output ONLY a valid JSON array, nothing else:
[
  { "topic": "3-5 word hook", "prompt": "the vivid question", "color": "saffron" },
  { "topic": "3-5 word hook", "prompt": "the vivid question", "color": "gold" },
  { "topic": "3-5 word hook", "prompt": "the vivid question", "color": "blue" }
]`;

  const out = await llmSuggestions(systemPrompt);
  if (out) return { suggestions: out, personalized: hasHistory };
  // Failsafe only (LLM unavailable): synthesize from history if we have it,
  // padding to 3 with fresh evergreen picks; else a clean pool shuffle.
  if (hasHistory) {
    const personal = synthesizePersonal(ctx.themes);
    if (personal.length >= 3) return { suggestions: personal.slice(0, 3), personalized: true };
    const seen = new Set(personal.map((s) => s.topic));
    const fill = pickEvergreen().filter((s) => !seen.has(s.topic));
    const merged = [...personal, ...fill].slice(0, 3).map((s, i) => ({ ...s, color: COLORS[i % 3] }));
    return { suggestions: merged, personalized: true };
  }
  return { suggestions: pickEvergreen(), personalized: false };
}

// Context cache — keyed by the live signature (date · region · language · history)
// so different moments get different sets, but identical context reuses the LLM call.
const ctxCache = new Map<string, { data: Suggestion[]; personalized: boolean; at: number }>();
const CTX_TTL_MS = 6 * 60 * 60 * 1000; // 6 hours

function ctxKey(ctx: Ctx): string {
  return [ctx.localDate || "", ctx.timezone || "", ctx.language || "", hashThemes(ctx.themes)].join("|").slice(0, 320);
}

function ctxFromRequest(request: Request, body: Record<string, unknown> = {}): Ctx {
  const themes = Array.isArray(body.themes)
    ? (body.themes as unknown[]).filter((t): t is string => typeof t === "string" && t.trim().length > 0).slice(0, 8)
    : [];
  const lh = body.localHour;
  return {
    themes,
    language: typeof body.language === "string" ? body.language : "",
    timezone: typeof body.timezone === "string" ? body.timezone : "",
    localHour: typeof lh === "number" ? lh : null,
    localDate: typeof body.localDate === "string" && body.localDate ? body.localDate : new Date().toDateString(),
    acceptLanguage: request.headers.get("accept-language") || "",
  };
}

function pruneCtxCache() {
  if (ctxCache.size > 300) {
    const oldest = [...ctxCache.entries()].sort((a, b) => a[1].at - b[1].at)[0]?.[0];
    if (oldest) ctxCache.delete(oldest);
  }
}

// GET — first paint / no body. Still date- and locale-aware via request headers.
export async function GET(request: Request) {
  const forceRefresh = new URL(request.url).searchParams.get("refresh") === "1";
  const ctx = ctxFromRequest(request, {});
  const key = ctxKey(ctx);
  const hit = ctxCache.get(key);
  if (!forceRefresh && hit && Date.now() - hit.at < CTX_TTL_MS) {
    return NextResponse.json({ suggestions: hit.data, personalized: hit.personalized, cached: true });
  }
  const { suggestions, personalized } = await generateContextual(ctx);
  ctxCache.set(key, { data: suggestions, personalized, at: Date.now() });
  pruneCtxCache();
  return NextResponse.json({ suggestions, personalized, cached: false, refreshedAt: new Date().toISOString() });
}

// POST — full context (history, language, timezone, local time) for everyone.
export async function POST(request: Request) {
  let body: Record<string, unknown> = {};
  let refresh = false;
  try {
    body = (await request.json()) as Record<string, unknown>;
    refresh = body?.refresh === true;
  } catch {
    body = {};
  }
  const ctx = ctxFromRequest(request, body);
  const key = ctxKey(ctx);
  const hit = ctxCache.get(key);
  if (!refresh && hit && Date.now() - hit.at < CTX_TTL_MS) {
    return NextResponse.json({ suggestions: hit.data, personalized: hit.personalized, cached: true });
  }
  const { suggestions, personalized } = await generateContextual(ctx);
  ctxCache.set(key, { data: suggestions, personalized, at: Date.now() });
  pruneCtxCache();
  return NextResponse.json({ suggestions, personalized, cached: false, refreshedAt: new Date().toISOString() });
}
