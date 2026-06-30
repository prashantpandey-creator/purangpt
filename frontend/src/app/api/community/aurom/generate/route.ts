import { type NextRequest, NextResponse } from 'next/server';
import { createPost, hasRecentPost } from '@/lib/community';
import { AUROM_BOT, generateAuromTopic } from '@/lib/aurom';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// Don't post again if Aurom already posted within this window — makes the cron
// idempotent so a re-run or a retried-after-timeout Action can't double-post.
const DEDUPE_HOURS = 20;
// Topic generation + an LLM round-trip can take a while.
export const maxDuration = 60;

/**
 * Aurom posts a fresh discussion topic. Intended to be invoked on a schedule
 * (daily or weekly) by a cron/GitHub Action that sends the shared secret.
 *
 *   curl -X POST https://purangpt.com/api/community/aurom/generate \
 *        -H "Authorization: Bearer $AUROM_CRON_SECRET"
 *
 * Auth: the request must present AUROM_CRON_SECRET via the Authorization
 * bearer header or an `?secret=` query param. If the secret env var is unset
 * the endpoint is disabled (returns 503) to prevent spam.
 */
async function handle(request: NextRequest): Promise<Response> {
  const secret = process.env.AUROM_CRON_SECRET;
  if (!secret) {
    return NextResponse.json({ error: 'Aurom is not configured' }, { status: 503 });
  }

  const auth = request.headers.get('authorization') || '';
  const bearer = auth.toLowerCase().startsWith('bearer ') ? auth.slice(7).trim() : '';
  const fromQuery = new URL(request.url).searchParams.get('secret') || '';
  if (bearer !== secret && fromQuery !== secret) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
  }

  try {
    // Idempotency guard: bail out if Aurom already posted recently.
    if (await hasRecentPost(AUROM_BOT.sub, DEDUPE_HOURS)) {
      return NextResponse.json({ ok: true, skipped: true, reason: 'already posted recently' });
    }
    const topic = await generateAuromTopic();
    const post = await createPost({
      user_sub: AUROM_BOT.sub,
      author_name: AUROM_BOT.name,
      author_picture: AUROM_BOT.picture,
      title: topic.title,
      body: topic.body,
      category: topic.category,
      is_bot: true,
    });
    return NextResponse.json({ ok: true, post_id: post.id, title: post.title });
  } catch (err) {
    console.error('[aurom] generate failed:', err);
    return NextResponse.json({ error: 'Failed to generate topic' }, { status: 500 });
  }
}

export async function POST(request: NextRequest): Promise<Response> {
  return handle(request);
}

export async function GET(request: NextRequest): Promise<Response> {
  return handle(request);
}
