import { NextResponse } from "next/server";

// ---------------------------------------------------------------------------
// /api/followup-suggestions — contextual "what to ask next" pills
// ---------------------------------------------------------------------------
// After every assistant answer the chat fires this with the last Q&A turn; we
// return 3 short, natural follow-up questions the seeker is most likely to want
// next — so they can keep the conversation going with one tap, never hitting a
// dead end. Grounded in the same DeepSeek→Gemini fallback the rest of the app
// uses. Falls back to evergreen continuations if both LLMs are unavailable.
// ---------------------------------------------------------------------------

export const runtime = "nodejs";

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

// Language label woven into the prompt so the follow-ups match the answer's tongue.
const LANG_NAME: Record<string, string> = {
  en: "English",
  hi: "Hindi (Devanagari)",
  ru: "Russian",
};

export type FollowupSuggestion = { label: string; query: string };

// Evergreen continuations — used only if both LLMs fail.
const EVERGREEN_EN: FollowupSuggestion[] = [
  { label: "What scripture says", query: "What do the sacred texts say about this topic in greater depth?" },
  { label: "Daily practice", query: "How can I apply this teaching practically in my daily spiritual life?" },
  { label: "Related story", query: "Can you share a related story or parable from the Puranas about this?" },
  { label: "Guruji's view", query: "What would Guruji Sri Shailendra Sharma say about this teaching?" },
  { label: "Gita's perspective", query: "How does the Bhagavad Gita address or illuminate this topic?" },
  { label: "Common misconception", query: "What are common misconceptions about this that the scriptures correct?" },
];
const EVERGREEN_HI: FollowupSuggestion[] = [
  { label: "शास्त्र क्या कहते हैं", query: "इस विषय में शास्त्र विस्तार से क्या कहते हैं?" },
  { label: "दैनिक साधना", query: "मैं इस शिक्षा को अपनी दैनिक साधना में कैसे उतारूँ?" },
  { label: "संबंधित कथा", query: "क्या पुराणों में इससे जुड़ी कोई कथा या दृष्टान्त है?" },
  { label: "गुरुजी का मार्गदर्शन", query: "गुरुजी श्री शैलेन्द्र शर्मा इस विषय में क्या मार्गदर्शन देंगे?" },
  { label: "गीता का दृष्टिकोण", query: "भगवद्‌गीता इस विषय को किस दृष्टि से देखती है?" },
  { label: "भ्रांति का सत्य", query: "इस विषय में क्या सामान्य भ्रांतियाँ हैं जो शास्त्र दूर करते हैं?" },
];
const EVERGREEN_RU: FollowupSuggestion[] = [
  { label: "Что говорят писания", query: "Что говорят священные тексты об этой теме подробнее?" },
  { label: "Ежедневная практика", query: "Как применить это учение в своей ежедневной духовной практике?" },
  { label: "Связанная история", query: "Есть ли в Пуранах связанная история или притча об этом?" },
  { label: "Совет Гуруджи", query: "Что Гуруджи Шри Шайлендра Шарма сказал бы об этом учении?" },
  { label: "Взгляд Гиты", query: "Как Бхагавад-гита рассматривает или освещает эту тему?" },
  { label: "Распространённое заблуждение", query: "Какие распространённые заблуждения об этом исправляют писания?" },
];

function evergreen(lang: string): FollowupSuggestion[] {
  const pool = lang === "hi" ? EVERGREEN_HI : lang === "ru" ? EVERGREEN_RU : EVERGREEN_EN;
  return [...pool].sort(() => Math.random() - 0.5).slice(0, 3);
}

/** Parse model text into up to 3 {label, query} objects, tolerating ```json fences. */
function parseFollowups(raw: string): FollowupSuggestion[] | null {
  if (!raw) return null;
  const cleaned = raw.trim().replace(/^```(?:json)?\n?/, "").replace(/\n?```$/, "");
  try {
    const parsed = JSON.parse(cleaned);
    if (!Array.isArray(parsed)) return null;
    const out = parsed
      .filter(
        (s: unknown): s is FollowupSuggestion =>
          typeof s === "object" &&
          s !== null &&
          typeof (s as any).label === "string" &&
          (s as any).label.trim().length > 0 &&
          typeof (s as any).query === "string" &&
          (s as any).query.trim().length > 0
      )
      .map((s: any) => ({ label: s.label.trim(), query: s.query.trim() }))
      .filter((s) => s.label.length <= 50 && s.query.length <= 200)
      .slice(0, 3);
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
        max_tokens: 320,
        temperature: 0.8,
      }),
      signal: AbortSignal.timeout(10_000),
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
            temperature: 0.8,
            maxOutputTokens: 360,
            responseMimeType: "application/json",
          },
        }),
        signal: AbortSignal.timeout(10_000),
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

function partOfDay(h: number | null): string {
  if (h == null || !Number.isFinite(h)) return "";
  if (h < 5) return "the small hours";
  if (h < 12) return "morning";
  if (h < 17) return "afternoon";
  if (h < 21) return "evening";
  return "night";
}

export async function POST(request: Request) {
  let question = "";
  let answer = "";
  let mode = "guide";
  let lang = "en";
  let priorTurns: string[] = [];
  let timezone = "";
  let localHour: number | null = null;
  let localDate = "";
  try {
    const body = await request.json();
    question = String(body?.question ?? "").slice(0, 1200);
    answer = String(body?.answer ?? "").slice(0, 2400);
    mode = String(body?.mode ?? "guide");
    lang = ["en", "hi", "ru"].includes(body?.language) ? body.language : "en";
    priorTurns = Array.isArray(body?.priorTurns)
      ? (body.priorTurns as unknown[])
          .filter((t): t is string => typeof t === "string" && t.trim().length > 0)
          .map((t) => t.trim().slice(0, 160))
          .slice(-5)
      : [];
    timezone = typeof body?.timezone === "string" ? body.timezone : "";
    localHour = typeof body?.localHour === "number" ? body.localHour : null;
    localDate = typeof body?.localDate === "string" ? body.localDate : "";
  } catch {
    return NextResponse.json({ suggestions: evergreen("en") });
  }

  if (!question && !answer) {
    return NextResponse.json({ suggestions: evergreen(lang) });
  }

  const langName = LANG_NAME[lang] || "English";
  const acceptLanguage = (request.headers.get("accept-language") || "").split(",")[0];
  const tod = partOfDay(localHour);

  // The thread so far — so follow-ups advance the arc instead of circling back
  // to ground already covered earlier in the conversation.
  const arcBlock = priorTurns.length
    ? `\nEARLIER IN THIS THREAD the seeker already asked (oldest→newest):\n${priorTurns.map((t, i) => `${i + 1}. ${t}`).join("\n")}\nDo NOT re-suggest anything they've already explored above — carry the journey FORWARD.`
    : "";

  // The moment — region/time, used only to *tint* an angle when it fits (a
  // festival drawing near, a practice suited to the hour), never forced.
  const momentBits: string[] = [];
  if (localDate) momentBits.push(`today is ${localDate}${tod ? `, ${tod} for them` : ""}`);
  if (timezone || acceptLanguage) momentBits.push(`locale ${[timezone, acceptLanguage].filter(Boolean).join(" / ")}`);
  const momentBlock = momentBits.length
    ? `\nTHIS MOMENT: ${momentBits.join("; ")}. If — and only if — a season, nearby Hindu festival, or the time of day naturally fits one follow-up, let it tint that angle. Never state the region or force it.`
    : "";

  const prompt = `You are PuranGPT, a guide to Hindu sacred texts (Puranas, Gita, Upanishads, Yoga, and Guruji Sri Shailendra Sharma's commentaries). A seeker just had this exchange:

SEEKER ASKED:
${question || "(opening question)"}

YOU ANSWERED:
${answer || "(answer omitted)"}
${arcBlock}${momentBlock}

Generate exactly 3 follow-up questions the seeker would most naturally and eagerly want to ask NEXT. Rules:
- Each must build directly on THIS specific exchange — deepen a point, branch to a related teaching, or ask how to apply it. Never generic.
- Name the actual story, character, text, verse, or idea where you can — concrete beats vague.
- "query" is the full question phrased in the SEEKER'S OWN VOICE (first person): 8 to 20 words.
- "label" is an ultra-compact 2-4 word pill label that hints at the topic (${langName}).
- Make the three DISTINCT (one deeper, one wider, one practical).
- BANNED filler (never use, nor any near-paraphrase): "tell me more", "inner peace", "finding your path", "restless mind", "letting go", "in dark times". No doom or current-news framing.
- Write both "label" and "query" in ${langName}.

Output ONLY a JSON array of exactly 3 objects with "label" and "query" keys — no other text:
[{"label": "Deepen this", "query": "Full follow-up question phrased as the seeker?"}, ...]`;

  const out =
    parseFollowups((await callDeepSeek(prompt)) || "") ??
    parseFollowups((await callGemini(prompt)) || "");

  return NextResponse.json({ suggestions: out ?? evergreen(lang) });
}
