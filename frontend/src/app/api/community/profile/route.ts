import { type NextRequest, NextResponse } from 'next/server';
import { getSessionUser } from '@/lib/session';
import { ensureProfile, getProfile, updateBio } from '@/lib/community';
import { resolveAuthorName } from '@/app/api/community/posts/route';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/** GET /api/community/profile — the signed-in member's own profile. */
export async function GET(request: NextRequest): Promise<Response> {
  const user = await getSessionUser(request);
  if (!user) return NextResponse.json({ error: 'Unauthenticated' }, { status: 401 });

  await ensureProfile({
    user_sub: user.sub,
    display_name: await resolveAuthorName(user),
    picture: user.picture || null,
  });
  const profile = await getProfile(user.sub, user.sub);
  return NextResponse.json({ profile });
}

/** PATCH /api/community/profile — update own bio. Body: { bio: string } */
export async function PATCH(request: NextRequest): Promise<Response> {
  const user = await getSessionUser(request);
  if (!user) return NextResponse.json({ error: 'Unauthenticated' }, { status: 401 });

  let body: { bio?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 });
  }

  const bio = (body.bio ?? '').trim();
  if (bio.length > 500) {
    return NextResponse.json({ error: 'Bio is too long (max 500 characters)' }, { status: 400 });
  }

  try {
    await ensureProfile({
      user_sub: user.sub,
      display_name: await resolveAuthorName(user),
      picture: user.picture || null,
    });
    await updateBio(user.sub, bio);
    const profile = await getProfile(user.sub, user.sub);
    return NextResponse.json({ profile });
  } catch (err) {
    console.error('[community] update bio failed:', err);
    return NextResponse.json({ error: 'Failed to update profile' }, { status: 500 });
  }
}
