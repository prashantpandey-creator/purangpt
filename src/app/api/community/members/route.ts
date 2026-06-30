import { type NextRequest, NextResponse } from 'next/server';
import { getSessionUser } from '@/lib/session';
import { listMembers, countMembers, type MemberSort } from '@/lib/community';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const SORTS: MemberSort[] = ['active', 'popular', 'new'];
const PAGE_SIZE = 30;

/**
 * GET /api/community/members — the member directory ("who's here").
 * Query: ?sort=active|popular|new&q=<search>&offset=<n>
 * Lists everyone with a community profile. `total` is returned only on the
 * first page (offset=0) so the header can show the full count cheaply.
 */
export async function GET(request: NextRequest): Promise<Response> {
  const viewer = await getSessionUser(request);
  const { searchParams } = request.nextUrl;

  const sortParam = searchParams.get('sort') ?? 'active';
  const sort: MemberSort = SORTS.includes(sortParam as MemberSort)
    ? (sortParam as MemberSort)
    : 'active';
  const search = searchParams.get('q');
  const offset = Math.max(parseInt(searchParams.get('offset') ?? '0', 10) || 0, 0);

  try {
    const members = await listMembers({
      sort,
      search,
      offset,
      limit: PAGE_SIZE,
      viewerSub: viewer?.sub ?? null,
    });
    const total = offset === 0 ? await countMembers(search) : undefined;
    return NextResponse.json({
      members,
      total,
      has_more: members.length === PAGE_SIZE,
    });
  } catch (err) {
    console.error('[community] list members failed:', err);
    return NextResponse.json({ error: 'Failed to load members' }, { status: 500 });
  }
}
