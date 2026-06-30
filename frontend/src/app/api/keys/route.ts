import { type NextRequest, NextResponse } from 'next/server';
import { getSessionUser } from '@/lib/session';
import { getSubscription, isProPlan } from '@/lib/db';
import { createApiKey, listApiKeys } from '@/lib/apiKeys';

export const runtime = 'nodejs';

// Cap how many active keys a single account can hold.
const MAX_KEYS = 5;

/** GET /api/keys — list the signed-in user's active API keys (metadata only). */
export async function GET(request: NextRequest): Promise<Response> {
  const user = await getSessionUser(request);
  if (!user) return NextResponse.json({ error: 'Unauthenticated' }, { status: 401 });

  const keys = await listApiKeys(user.sub);
  return NextResponse.json({ keys });
}

/**
 * POST /api/keys — issue a new API key. Pro-only. The plaintext key is returned
 * exactly once in this response and is never retrievable again.
 */
export async function POST(request: NextRequest): Promise<Response> {
  const user = await getSessionUser(request);
  if (!user) return NextResponse.json({ error: 'Unauthenticated' }, { status: 401 });

  const sub = await getSubscription(user.sub);
  if (!isProPlan(sub?.plan)) {
    return NextResponse.json(
      { error: 'API access is a Pro feature. Upgrade to generate API keys.' },
      { status: 403 },
    );
  }

  const existing = await listApiKeys(user.sub);
  if (existing.length >= MAX_KEYS) {
    return NextResponse.json(
      { error: `You can have at most ${MAX_KEYS} active keys. Revoke one to create another.` },
      { status: 409 },
    );
  }

  let name: string | undefined;
  try {
    const body = await request.json();
    if (typeof body?.name === 'string' && body.name.trim()) {
      name = body.name.trim().slice(0, 60);
    }
  } catch {
    /* body is optional */
  }

  const { plaintext, row } = await createApiKey(user.sub, name);
  return NextResponse.json({ key: plaintext, meta: row }, { status: 201 });
}
