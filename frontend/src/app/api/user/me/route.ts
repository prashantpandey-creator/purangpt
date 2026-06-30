import { type NextRequest, NextResponse } from 'next/server';
import { parseGoogleSession, parseLogtoSession } from '@/lib/session';
import { getSubscription, upsertSubscription } from '@/lib/db';

export const runtime = 'nodejs';

/**
 * GET /api/user/me
 * Returns the current user's profile + plan from the session cookie.
 * Creates a subscription record for new users (plan = free).
 */
export async function GET(request: NextRequest): Promise<Response> {
  // 1. Parse session from either cookie
  const googleCookie = request.cookies.get('purangpt_session')?.value;
  const logtoCookie  = request.cookies.get('logto_session')?.value;

  const user =
    (googleCookie ? await parseGoogleSession(googleCookie) : null) ??
    (logtoCookie  ? await parseLogtoSession(logtoCookie)   : null);

  if (!user) {
    return NextResponse.json({ error: 'Unauthenticated' }, { status: 401 });
  }

  // 2. Fetch (or create) subscription record. The session cookie is the source
  //    of truth for *authentication* — the DB only enriches with the plan. So a
  //    DB error must NOT 401/500 the user (that would log out a valid session in
  //    the client). Degrade gracefully to the free plan instead.
  let sub = null;
  try {
    sub = await getSubscription(user.sub);
    if (!sub) {
      // First sign-in: provision a free subscription record
      sub = await upsertSubscription(user.sub, {
        plan: 'free',
        status: 'active',
      });
    }
  } catch (err) {
    console.error('[user/me] subscription lookup failed — defaulting to free plan:', err);
  }

  return NextResponse.json({
    sub:          user.sub,
    email:        user.email,
    name:         user.name,
    picture:      user.picture,
    provider:     user.provider,
    display_name: (sub?.display_name as string | null) ?? null,
    plan:         (sub?.plan as string) ?? 'free',
    plan_status:  (sub?.status as string) ?? 'active',
    plan_current_period_end: (sub?.current_period_end as string | null) ?? null,
  });
}
