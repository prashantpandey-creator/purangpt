import { type NextRequest, NextResponse } from 'next/server';
import { getSessionUser } from '@/lib/session';
import { getProfile, listPosts } from '@/lib/community';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/** GET /api/community/profile/[sub] — public profile + that member's posts. */
export async function GET(
  request: NextRequest,
  context: { params: Promise<{ sub: string }> },
): Promise<Response> {
  const { sub } = await context.params;
  const userSub = decodeURIComponent(sub);
  const viewer = await getSessionUser(request);

  try {
    const profile = await getProfile(userSub, viewer?.sub ?? null);
    if (!profile) {
      return NextResponse.json({ error: 'Profile not found' }, { status: 404 });
    }
    const posts = await listPosts({
      sort: 'new',
      authorSub: userSub,
      viewerSub: viewer?.sub ?? null,
      limit: 50,
    });
    return NextResponse.json({ profile, posts });
  } catch (err) {
    console.error('[community] get profile failed:', err);
    return NextResponse.json({ error: 'Failed to load profile' }, { status: 500 });
  }
}
