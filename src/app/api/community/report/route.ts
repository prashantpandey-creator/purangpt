import { type NextRequest, NextResponse } from 'next/server';
import { getSessionUser } from '@/lib/session';
import { report } from '@/lib/community';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/**
 * POST /api/community/report — flag a post or comment for moderation.
 * Body: { target_type: 'post' | 'comment', target_id: number, reason?: string }
 */
export async function POST(request: NextRequest): Promise<Response> {
  const user = await getSessionUser(request);
  if (!user) return NextResponse.json({ error: 'Sign in to report' }, { status: 401 });

  let body: { target_type?: string; target_id?: number; reason?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 });
  }

  const targetType = body.target_type === 'comment' ? 'comment' : body.target_type === 'post' ? 'post' : null;
  const targetId = Number(body.target_id);
  if (!targetType || !Number.isInteger(targetId)) {
    return NextResponse.json({ error: 'Invalid target' }, { status: 400 });
  }

  try {
    const result = await report(user.sub, targetType, targetId, (body.reason ?? '').trim());
    return NextResponse.json(result);
  } catch (err) {
    if (err instanceof Error && err.message === 'TARGET_NOT_FOUND') {
      return NextResponse.json({ error: 'Content not found' }, { status: 404 });
    }
    console.error('[community] report failed:', err);
    return NextResponse.json({ error: 'Failed to submit report' }, { status: 500 });
  }
}
