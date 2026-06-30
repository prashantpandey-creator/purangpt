import { type NextRequest, NextResponse } from 'next/server';
import { getSessionUser } from '@/lib/session';
import { deleteComment } from '@/lib/community';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/** DELETE /api/community/comments/[id] — soft delete, owner only. */
export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ id: string }> },
): Promise<Response> {
  const { id } = await context.params;
  const commentId = Number(id);
  if (!Number.isInteger(commentId)) {
    return NextResponse.json({ error: 'Invalid comment id' }, { status: 400 });
  }

  const user = await getSessionUser(request);
  if (!user) {
    return NextResponse.json({ error: 'Unauthenticated' }, { status: 401 });
  }

  try {
    const ok = await deleteComment(commentId, user.sub);
    if (!ok) {
      return NextResponse.json({ error: 'Not found or not yours' }, { status: 403 });
    }
    return NextResponse.json({ ok: true });
  } catch (err) {
    console.error('[community] delete comment failed:', err);
    return NextResponse.json({ error: 'Failed to delete comment' }, { status: 500 });
  }
}
