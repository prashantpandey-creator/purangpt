import { type NextRequest, NextResponse } from 'next/server';
import { getSessionUser, type SessionUser } from '@/lib/session';
import { getSubscription } from '@/lib/db';
import { createPost, listPosts, type SortMode } from '@/lib/community';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/** Best available display name for the author byline. */
export async function resolveAuthorName(user: SessionUser): Promise<string> {
  try {
    const sub = await getSubscription(user.sub);
    if (sub?.display_name) return sub.display_name;
  } catch {
    /* ignore — fall back to session fields */
  }
  if (user.name) return user.name;
  if (user.email) return user.email.split('@')[0];
  return 'Seeker';
}

/** GET /api/community/posts — list the feed (public read). */
export async function GET(request: NextRequest): Promise<Response> {
  const { searchParams } = new URL(request.url);
  const sort = (searchParams.get('sort') as SortMode) || 'hot';
  const category = searchParams.get('category');
  const search = searchParams.get('q');
  const feed = searchParams.get('feed') === 'following' ? 'following' : 'all';
  const limit = Number(searchParams.get('limit')) || 25;
  const offset = Number(searchParams.get('offset')) || 0;

  const viewer = await getSessionUser(request);

  try {
    const posts = await listPosts({
      sort: ['hot', 'new', 'top'].includes(sort) ? sort : 'hot',
      category,
      search,
      feed,
      limit,
      offset,
      viewerSub: viewer?.sub ?? null,
    });
    return NextResponse.json({ posts });
  } catch (err) {
    console.error('[community] list posts failed:', err);
    return NextResponse.json({ error: 'Failed to load posts' }, { status: 500 });
  }
}

/** POST /api/community/posts — create a post (auth required). */
export async function POST(request: NextRequest): Promise<Response> {
  const user = await getSessionUser(request);
  if (!user) {
    return NextResponse.json({ error: 'Sign in to create a post' }, { status: 401 });
  }

  let body: { title?: string; body?: string; category?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 });
  }

  const title = body.title?.trim() ?? '';
  const text = body.body?.trim() ?? '';
  const category = body.category?.trim() || 'discussion';

  if (title.length < 3) {
    return NextResponse.json({ error: 'Title must be at least 3 characters' }, { status: 400 });
  }
  if (title.length > 300) {
    return NextResponse.json({ error: 'Title is too long (max 300 characters)' }, { status: 400 });
  }
  if (text.length > 20000) {
    return NextResponse.json({ error: 'Post is too long (max 20000 characters)' }, { status: 400 });
  }

  try {
    const author_name = await resolveAuthorName(user);
    const post = await createPost({
      user_sub: user.sub,
      author_name,
      author_picture: user.picture || null,
      title,
      body: text,
      category,
    });
    return NextResponse.json({ post }, { status: 201 });
  } catch (err) {
    console.error('[community] create post failed:', err);
    return NextResponse.json({ error: 'Failed to create post' }, { status: 500 });
  }
}
