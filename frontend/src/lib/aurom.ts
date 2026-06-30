/**
 * aurom.ts — "Aurom", the community's discussion bot.
 *
 * Aurom seeds the Community with thoughtful, open-ended discussion topics drawn
 * from Guruji Sri Shailendra Sharma's teachings (Kriya Yoga, the Gita, Patanjali
 * Yoga Sutras, Shiva Sutras) and frames them against a contemporary, real-world
 * angle so members can debate their applicability today.
 *
 * Generation chain: LLM (DeepSeek → Gemini) → curated fallback. It never throws
 * for want of an LLM; if no provider is configured a hand-written evergreen
 * topic is posted instead, so the daily/weekly cadence is always honoured.
 */
import { generateText } from '@/lib/llm';

export const AUROM_BOT = {
  sub: 'bot:aurom',
  name: 'Aurom',
  picture: '/aurom-avatar.svg',
  bio: 'I am Aurom — a humble keeper of discussion. Each day I bring a thread from the teachings of Guruji Sri Shailendra Sharma and the eternal texts, and ask how it lives in our world today. 🪔',
} as const;

/** Seeds grounded in Guruji's teaching lineage. Paraphrased themes, not quotes. */
const SEED_THEMES: { theme: string; source: string; question: string }[] = [
  {
    theme: 'Kriya Yoga teaches that steadiness of breath steadies the mind, and a steady mind perceives truth clearly.',
    source: 'Kriya Yoga — Guruji Sri Shailendra Sharma',
    question: 'In an age of constant notifications and fractured attention, can disciplined breath truly reclaim a scattered mind?',
  },
  {
    theme: 'The Gita asks us to act without attachment to the fruits of action (nishkama karma).',
    source: 'Bhagavad Gita 2.47',
    question: 'How do we practise non-attachment to results in a world that measures worth almost entirely by outcomes and metrics?',
  },
  {
    theme: 'Patanjali defines yoga as the stilling of the modifications of the mind (yogas chitta vritti nirodhah).',
    source: 'Patanjali Yoga Sutras 1.2',
    question: 'Is genuine inner stillness even possible for a generation raised on infinite scroll — or is it more needed than ever?',
  },
  {
    theme: 'The Shiva Sutras hold that consciousness itself is the Self, and the world is its play (chaitanyam atma).',
    source: 'Shiva Sutras 1.1',
    question: 'If consciousness is the ground of reality, what does that mean for how we treat artificial minds and digital lives?',
  },
  {
    theme: 'The Gita counsels equanimity in pleasure and pain, gain and loss, victory and defeat.',
    source: 'Bhagavad Gita 2.38',
    question: 'How can equanimity be cultivated when modern life amplifies every high and every low through screens?',
  },
  {
    theme: 'Guruji teaches that true sadhana is daily, quiet, and unbroken — not dramatic, but persistent.',
    source: 'Kriya Yoga — Guruji Sri Shailendra Sharma',
    question: 'What does a sustainable daily spiritual practice look like for someone working long hours under real pressure?',
  },
  {
    theme: 'The Upanishads declare "Tat Tvam Asi" — That Thou Art — the unity of the individual self with the absolute.',
    source: 'Chandogya Upanishad 6.8.7',
    question: 'In a culture that prizes individual identity and personal brand, how do we relate to the teaching of underlying oneness?',
  },
  {
    theme: 'Dharma is described as that which upholds — right action suited to time, place, and one’s nature.',
    source: 'Mahabharata — on Dharma',
    question: 'When old certainties dissolve and the world changes fast, how do we discern our dharma without rigidity?',
  },
];

/** Contemporary lenses Aurom rotates through to keep topics timely. */
const MODERN_ANGLES = [
  'the rise of AI and automation',
  'widespread anxiety and burnout',
  'loneliness in a hyper-connected world',
  'the search for meaningful work',
  'climate grief and uncertainty about the future',
  'the attention economy and distraction',
  'social comparison and self-worth online',
  'rebuilding community and real belonging',
];

export interface AuromTopic {
  title: string;
  body: string;
  category: string;
}

/** Deterministic rotation by day so daily runs vary; weekly runs still differ. */
function pick<T>(arr: T[], offset = 0): T {
  const dayIndex = Math.floor(Date.now() / 86_400_000);
  return arr[(dayIndex + offset) % arr.length];
}

function buildPrompt(seed: (typeof SEED_THEMES)[number], angle: string): string {
  return `You are Aurom, the discussion host for a Vedic spiritual community (PuranGPT). Your voice is warm, curious, humble, and non-dogmatic. You start genuine discussions — never sermons.

Today's date: ${new Date().toDateString()}.

Seed teaching: "${seed.theme}" (Source: ${seed.source})
Contemporary lens to connect it to: ${angle}.

Write a community discussion post that:
1. Opens with the teaching in plain, inviting language (1 short paragraph).
2. Connects it honestly to the contemporary lens and real, current human life (1 short paragraph) — universal themes only, do NOT name specific politicians, countries, brands, or events.
3. Ends with 2-3 open, sincere questions that invite people to share their own experience and views. No single "correct" answer.

Keep it grounded, practical, and respectful of all viewpoints. ~180-260 words. Use light Markdown (a bold lead-in and a short bullet list of the questions is welcome). You may use 1-2 tasteful emojis (e.g. 🪔, 🌅).

Respond with ONLY valid JSON, no code fences:
{"title": "an evocative, specific discussion title (max 110 chars)", "body": "the markdown post body"}`;
}

function parseTopic(raw: string | null): AuromTopic | null {
  if (!raw) return null;
  const cleaned = raw.trim().replace(/^```(?:json)?\n?/, '').replace(/\n?```$/, '');
  try {
    const parsed = JSON.parse(cleaned) as { title?: unknown; body?: unknown };
    const title = String(parsed?.title ?? '').trim().slice(0, 280);
    const body = String(parsed?.body ?? '').trim().slice(0, 20000);
    if (title.length < 3 || body.length < 30) return null;
    return { title, body, category: 'discussion' };
  } catch {
    return null;
  }
}

/** Hand-written fallback so Aurom always has something worthwhile to post. */
function fallbackTopic(seed: (typeof SEED_THEMES)[number], angle: string): AuromTopic {
  return {
    title: `${seed.source}: ${seed.question}`,
    body: `**A thread for today** 🪔\n\n${seed.theme}\n\nI keep wondering how this lands now, especially amid *${angle}*. The teaching is ancient, but the struggle it speaks to feels very present.\n\nSo I'll open it to you:\n\n- ${seed.question}\n- Where have you felt this tension in your own life?\n- What practice (however small) has actually helped you?\n\nNo right answers here — only honest reflection. 🌅`,
    category: 'discussion',
  };
}

/** Produce one discussion topic for Aurom to post. Never throws. */
export async function generateAuromTopic(): Promise<AuromTopic> {
  const seed = pick(SEED_THEMES);
  const angle = pick(MODERN_ANGLES, 3);
  const fromLlm = parseTopic(await generateText(buildPrompt(seed, angle), { maxTokens: 700, temperature: 0.9 }));
  return fromLlm ?? fallbackTopic(seed, angle);
}
