import { type NextRequest, NextResponse } from 'next/server';
import { getSessionUser } from '@/lib/session';
import { vote } from '@/lib/community';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/** POST /api/community/posts/[id]/vote  body: { value: 1 | -1 | 0 } */
export async function POST(
  request: NextRequest,
  context: { params: Promise<{ id: string }> },
): Promise<Response> {
  const { id } = await context.params;
  const postId = Number(id);
  if (!Number.isInteger(postId)) {
    return NextResponse.json({ error: 'Invalid post id' }, { status: 400 });
  }

  const user = await getSessionUser(request);
  if (!user) {
    return NextResponse.json({ error: 'Sign in to vote' }, { status: 401 });
  }

  let body: { value?: number };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 });
  }

  try {
    const result = await vote('post', postId, user.sub, Number(body.value) || 0);
    return NextResponse.json(result);
  } catch (err) {
    if (err instanceof Error && err.message === 'TARGET_NOT_FOUND') {
      return NextResponse.json({ error: 'Post not found' }, { status: 404 });
    }
    console.error('[community] vote post failed:', err);
    return NextResponse.json({ error: 'Failed to vote' }, { status: 500 });
  }
}
