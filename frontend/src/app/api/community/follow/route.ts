import { type NextRequest, NextResponse } from 'next/server';
import { getSessionUser } from '@/lib/session';
import { ensureProfile, setFollow } from '@/lib/community';
import { resolveAuthorName } from '@/app/api/community/posts/route';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/**
 * POST /api/community/follow — open follow graph; anyone may follow anyone.
 * Body: { target_sub: string, follow: boolean }
 */
export async function POST(request: NextRequest): Promise<Response> {
  const user = await getSessionUser(request);
  if (!user) return NextResponse.json({ error: 'Sign in to follow' }, { status: 401 });

  let body: { target_sub?: string; follow?: boolean };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 });
  }

  const targetSub = (body.target_sub ?? '').trim();
  if (!targetSub) {
    return NextResponse.json({ error: 'Missing target_sub' }, { status: 400 });
  }
  if (targetSub === user.sub) {
    return NextResponse.json({ error: 'You cannot follow yourself' }, { status: 400 });
  }

  try {
    // Make sure the follower has a profile row so they appear in graphs.
    await ensureProfile({
      user_sub: user.sub,
      display_name: await resolveAuthorName(user),
      picture: user.picture || null,
    });
    const result = await setFollow(user.sub, targetSub, body.follow !== false);
    return NextResponse.json(result);
  } catch (err) {
    if (err instanceof Error && err.message === 'CANNOT_FOLLOW_SELF') {
      return NextResponse.json({ error: 'You cannot follow yourself' }, { status: 400 });
    }
    console.error('[community] follow failed:', err);
    return NextResponse.json({ error: 'Failed to update follow' }, { status: 500 });
  }
}
