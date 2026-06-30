import { type NextRequest, NextResponse } from 'next/server';
import { getSessionUser } from '@/lib/session';
import { revokeApiKey } from '@/lib/apiKeys';

export const runtime = 'nodejs';

/** DELETE /api/keys/:id — revoke one of the signed-in user's keys. */
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
): Promise<Response> {
  const user = await getSessionUser(request);
  if (!user) return NextResponse.json({ error: 'Unauthenticated' }, { status: 401 });

  const { id } = await params;
  const revoked = await revokeApiKey(user.sub, id);
  if (!revoked) {
    return NextResponse.json({ error: 'Key not found' }, { status: 404 });
  }
  return NextResponse.json({ ok: true });
}
