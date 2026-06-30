/**
 * llm.ts — Minimal server-side LLM client for one-shot text generation.
 *
 * Mirrors the provider chain already used in /api/guru-suggestions:
 * DeepSeek (primary) → Gemini (fallback). All keys are read from env; if none
 * are configured every call resolves to null so callers can fall back cleanly.
 */

const GEMINI_MODEL = process.env.GEMINI_MODEL || 'gemini-2.0-flash';

function geminiKey(): string {
  return (
    process.env.GEMINI_API_KEY ||
    process.env.GOOGLE_GEMINI_API_KEY ||
    process.env.GOOGLE_GENERATIVE_AI_API_KEY ||
    process.env.GOOGLE_API_KEY ||
    ''
  );
}

export interface LlmOptions {
  maxTokens?: number;
  temperature?: number;
  timeoutMs?: number;
}

async function callDeepSeek(prompt: string, opts: LlmOptions): Promise<string | null> {
  const key = process.env.DEEPSEEK_API_KEY;
  if (!key) return null;
  try {
    const res = await fetch('https://api.deepseek.com/chat/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${key}` },
      body: JSON.stringify({
        model: process.env.DEEPSEEK_MODEL || 'deepseek-chat',
        messages: [{ role: 'user', content: prompt }],
        max_tokens: opts.maxTokens ?? 800,
        temperature: opts.temperature ?? 0.85,
      }),
      signal: AbortSignal.timeout(opts.timeoutMs ?? 20_000),
    });
    if (!res.ok) return null;
    const json = await res.json();
    return json.choices?.[0]?.message?.content?.trim() || null;
  } catch {
    return null;
  }
}

async function callGemini(prompt: string, opts: LlmOptions): Promise<string | null> {
  const key = geminiKey();
  if (!key) return null;
  try {
    const res = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${key}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: {
            temperature: opts.temperature ?? 0.85,
            maxOutputTokens: opts.maxTokens ?? 800,
          },
        }),
        signal: AbortSignal.timeout(opts.timeoutMs ?? 20_000),
      },
    );
    if (!res.ok) return null;
    const json = await res.json();
    return (
      json.candidates?.[0]?.content?.parts?.map((p: { text?: string }) => p?.text ?? '').join('').trim() ||
      null
    );
  } catch {
    return null;
  }
}

/** Generate text via DeepSeek, falling back to Gemini. Returns null if both fail. */
export async function generateText(prompt: string, opts: LlmOptions = {}): Promise<string | null> {
  return (await callDeepSeek(prompt, opts)) ?? (await callGemini(prompt, opts));
}

/** True when at least one LLM provider is configured. */
export function hasLlm(): boolean {
  return Boolean(process.env.DEEPSEEK_API_KEY || geminiKey());
}
