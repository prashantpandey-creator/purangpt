import { type NextRequest, NextResponse } from 'next/server';
import { getSubscription, isProPlan } from '@/lib/db';
import { resolveApiKey } from '@/lib/apiKeys';

export const runtime = 'nodejs';

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

/**
 * POST /api/v1/chat — public, key-authenticated chat endpoint for Pro users.
 *
 * Auth:  Authorization: Bearer pgk_live_…   (created in Settings → API)
 * Body:  { "query": string, "mode"?: "research"|"guide", "language"?: "en"|"hi"|"ru",
 *          "top_k"?: number, "session_id"?: string, "stream"?: boolean }
 *
 * By default returns assembled JSON: { answer, citations, session_id, grounding_quality }.
 * Pass "stream": true (or Accept: text/event-stream) to receive the raw SSE stream.
 *
 * Pro status is re-checked on every call, so a key stops working if the owner's
 * subscription lapses.
 */
function bearer(request: NextRequest): string | null {
  const h = request.headers.get('authorization') || '';
  const m = h.match(/^Bearer\s+(.+)$/i);
  return m ? m[1].trim() : null;
}

export async function POST(request: NextRequest): Promise<Response> {
  if (!API_URL) {
    return NextResponse.json({ error: 'Service unavailable' }, { status: 503 });
  }

  // 1. Authenticate the API key → owner.
  const userSub = await resolveApiKey(bearer(request));
  if (!userSub) {
    return NextResponse.json(
      { error: 'Invalid or missing API key. Pass it as: Authorization: Bearer pgk_live_…' },
      { status: 401 },
    );
  }

  // 2. Re-verify the owner is still Pro.
  const sub = await getSubscription(userSub);
  if (!isProPlan(sub?.plan)) {
    return NextResponse.json(
      { error: 'This key is inactive because the account is no longer on a Pro plan.' },
      { status: 403 },
    );
  }

  // 3. Validate the request body.
  let body: Record<string, unknown>;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Body must be valid JSON' }, { status: 400 });
  }
  const query = typeof body.query === 'string' ? body.query.trim() : '';
  if (!query) {
    return NextResponse.json({ error: 'Field "query" is required' }, { status: 400 });
  }

  const mode = body.mode === 'guide' ? 'guide' : 'research';
  const language = ['en', 'hi', 'ru'].includes(String(body.language)) ? String(body.language) : 'en';
  const top_k = Number.isFinite(body.top_k as number) ? Math.min(Math.max(Number(body.top_k), 1), 25) : 10;
  const session_id = typeof body.session_id === 'string' && body.session_id ? body.session_id : `api:${userSub}`;
  const wantStream =
    body.stream === true || (request.headers.get('accept') || '').includes('text/event-stream');

  // 4. Call the real answer engine. Forward user identity via the internal
  //    service key so the backend enforces Pro limits (not guest limits).
  const internalKey = process.env.INTERNAL_SERVICE_KEY || '';
  let upstream: Response;
  try {
    upstream = await fetch(`${API_URL}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Device-ID': `apikey:${userSub}`,
        ...(internalKey ? {
          'X-Internal-Service-Key': internalKey,
          'X-Internal-User-Sub': userSub,
        } : {}),
      },
      body: JSON.stringify({ query, mode, session_id, top_k, model: 'auto', language, stream: true }),
    });
  } catch {
    return NextResponse.json({ error: 'Upstream request failed' }, { status: 502 });
  }

  if (upstream.status === 429) {
    return NextResponse.json(
      { error: 'Rate limit reached. Please slow down and retry shortly.' },
      { status: 429 },
    );
  }
  if (!upstream.ok || !upstream.body) {
    return NextResponse.json({ error: `Upstream error (${upstream.status})` }, { status: 502 });
  }

  // 5a. Stream passthrough.
  if (wantStream) {
    return new Response(upstream.body, {
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream; charset=utf-8',
        'Cache-Control': 'no-cache, no-transform',
        Connection: 'keep-alive',
      },
    });
  }

  // 5b. Assemble the SSE stream into a single JSON answer.
  const reader = upstream.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let answer = '';
  let citations: unknown[] = [];
  let doneMeta: Record<string, unknown> = {};
  let errorMessage: string | null = null;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = frames.pop() ?? '';
      for (const frame of frames) {
        const payload = frame
          .split(/\r?\n/)
          .filter((l) => l.startsWith('data:'))
          .map((l) => l.slice(5).trim())
          .join('');
        if (!payload || payload === '[DONE]') continue;
        let evt: { type?: string; content?: string; sources?: unknown[]; message?: string; [k: string]: unknown };
        try {
          evt = JSON.parse(payload);
        } catch {
          continue;
        }
        if (evt.type === 'token' && typeof evt.content === 'string') answer += evt.content;
        else if (evt.type === 'sources' && Array.isArray(evt.sources)) citations = evt.sources;
        else if (evt.type === 'error' && typeof evt.message === 'string') errorMessage = evt.message;
        else if (evt.type === 'done') doneMeta = evt;
      }
    }
  } finally {
    reader.releaseLock();
  }

  if (errorMessage && !answer) {
    return NextResponse.json({ error: errorMessage }, { status: 502 });
  }

  return NextResponse.json({
    answer,
    citations,
    session_id: (doneMeta.session_id as string) ?? session_id,
    grounding_quality: doneMeta.grounding_quality ?? null,
  });
}
