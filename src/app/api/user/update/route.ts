import { type NextRequest, NextResponse } from 'next/server';
import { parseGoogleSession, parseLogtoSession } from '@/lib/session';
import { updateSubscription, upsertSubscription } from '@/lib/db';

export const runtime = 'nodejs';

/**
 * PATCH /api/user/update
 * Updates a user's display_name (stored in subscriptions table).
 * Body: { display_name?: string }
 */
export async function PATCH(request: NextRequest): Promise<Response> {
  const googleCookie = request.cookies.get('purangpt_session')?.value;
  const logtoCookie  = request.cookies.get('logto_session')?.value;

  const user =
    (googleCookie ? await parseGoogleSession(googleCookie) : null) ??
    (logtoCookie  ? await parseLogtoSession(logtoCookie)   : null);

  if (!user) {
    return NextResponse.json({ error: 'Unauthenticated' }, { status: 401 });
  }

  let body: { display_name?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 });
  }

  // Ensure the subscription row exists before patching
  const ok = await updateSubscription(user.sub, {
    display_name: body.display_name?.trim() || null,
  });

  if (!ok) {
    // Row may not exist yet (no prior GET /me call) — upsert it
    await upsertSubscription(user.sub, {
      plan: 'free',
      status: 'active',
      display_name: body.display_name?.trim() || null,
    });
  }

  return NextResponse.json({ ok: true });
}
