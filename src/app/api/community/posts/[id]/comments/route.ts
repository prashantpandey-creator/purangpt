import { type NextRequest, NextResponse } from 'next/server';
import { getSessionUser } from '@/lib/session';
import { createComment, listComments } from '@/lib/community';
import { resolveAuthorName } from '@/app/api/community/posts/route';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/** GET /api/community/posts/[id]/comments — flat list (public). */
export async function GET(
  request: NextRequest,
  context: { params: Promise<{ id: string }> },
): Promise<Response> {
  const { id } = await context.params;
  const postId = Number(id);
  if (!Number.isInteger(postId)) {
    return NextResponse.json({ error: 'Invalid post id' }, { status: 400 });
  }
  const viewer = await getSessionUser(request);
  try {
    const comments = await listComments(postId, viewer?.sub ?? null);
    return NextResponse.json({ comments });
  } catch (err) {
    console.error('[community] list comments failed:', err);
    return NextResponse.json({ error: 'Failed to load comments' }, { status: 500 });
  }
}

/** POST /api/community/posts/[id]/comments  body: { body, parent_id? } */
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
    return NextResponse.json({ error: 'Sign in to comment' }, { status: 401 });
  }

  let body: { body?: string; parent_id?: number | null };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 });
  }

  const text = body.body?.trim() ?? '';
  if (text.length < 1) {
    return NextResponse.json({ error: 'Comment cannot be empty' }, { status: 400 });
  }
  if (text.length > 10000) {
    return NextResponse.json({ error: 'Comment is too long (max 10000 characters)' }, { status: 400 });
  }

  const parent_id =
    body.parent_id != null && Number.isInteger(Number(body.parent_id))
      ? Number(body.parent_id)
      : null;

  try {
    const author_name = await resolveAuthorName(user);
    const comment = await createComment({
      post_id: postId,
      parent_id,
      user_sub: user.sub,
      author_name,
      author_picture: user.picture || null,
      body: text,
    });
    return NextResponse.json({ comment }, { status: 201 });
  } catch (err) {
    if (err instanceof Error && err.message === 'POST_NOT_FOUND') {
      return NextResponse.json({ error: 'Post not found' }, { status: 404 });
    }
    if (err instanceof Error && err.message === 'PARENT_NOT_FOUND') {
      return NextResponse.json({ error: 'Parent comment not found' }, { status: 400 });
    }
    console.error('[community] create comment failed:', err);
    return NextResponse.json({ error: 'Failed to post comment' }, { status: 500 });
  }
}
