import { type NextRequest, NextResponse } from 'next/server';
import { getSessionUser } from '@/lib/session';
import { deletePost, getPost, listComments } from '@/lib/community';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/** GET /api/community/posts/[id] — single post + its comment thread (public). */
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
    const post = await getPost(postId, viewer?.sub ?? null);
    if (!post) {
      return NextResponse.json({ error: 'Post not found' }, { status: 404 });
    }
    const comments = await listComments(postId, viewer?.sub ?? null);
    return NextResponse.json({ post, comments });
  } catch (err) {
    console.error('[community] get post failed:', err);
    return NextResponse.json({ error: 'Failed to load post' }, { status: 500 });
  }
}

/** DELETE /api/community/posts/[id] — soft delete, owner only. */
export async function DELETE(
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
    return NextResponse.json({ error: 'Unauthenticated' }, { status: 401 });
  }

  try {
    const ok = await deletePost(postId, user.sub);
    if (!ok) {
      return NextResponse.json({ error: 'Not found or not yours' }, { status: 403 });
    }
    return NextResponse.json({ ok: true });
  } catch (err) {
    console.error('[community] delete post failed:', err);
    return NextResponse.json({ error: 'Failed to delete post' }, { status: 500 });
  }
}
