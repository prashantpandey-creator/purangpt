/**
 * community.ts — Data layer for the Reddit-style community / discussion mode.
 *
 * Tables (created in scripts/init-db.js):
 *   community_posts     — top-level posts open for discussion
 *   community_comments  — threaded comments (parent_id self-reference)
 *   community_votes     — one row per (user, target) upvote/downvote
 *   community_profiles  — public member profile (name, picture, bio, bot flag)
 *   community_follows   — open follow graph (anyone may follow anyone)
 *   community_reports   — moderation reports; N distinct reporters auto-hide
 *
 * Scores are denormalised onto posts/comments and kept in sync inside the
 * vote transaction so feed/listing queries stay cheap.
 */
import type postgres from 'postgres';
import { sql } from '@/lib/db';

/** Distinct reporters required before a post/comment is auto-hidden. */
export const REPORT_HIDE_THRESHOLD = 3;

/** Allowed discussion categories (kept in sync with the UI). */
export const CATEGORIES = [
  'discussion',
  'question',
  'wisdom',
  'scripture',
  'experience',
  'announcement',
] as const;

export type Category = (typeof CATEGORIES)[number];

export type SortMode = 'hot' | 'new' | 'top';

export interface Post {
  id: number;
  user_sub: string;
  author_name: string;
  author_picture: string | null;
  is_bot: boolean;
  title: string;
  body: string;
  category: string;
  score: number;
  comment_count: number;
  created_at: string;
  updated_at: string;
  my_vote?: number; // -1 | 0 | 1 for the requesting user
}

export interface Comment {
  id: number;
  post_id: number;
  parent_id: number | null;
  user_sub: string;
  author_name: string;
  author_picture: string | null;
  is_bot: boolean;
  body: string;
  score: number;
  is_deleted: boolean;
  is_hidden: boolean;
  created_at: string;
  my_vote?: number;
}

export interface Profile {
  user_sub: string;
  display_name: string;
  picture: string | null;
  bio: string;
  is_bot: boolean;
  follower_count: number;
  following_count: number;
  post_count: number;
  is_following?: boolean; // does the viewer follow this profile?
}

function ensureDb() {
  if (!sql) throw new Error('DATABASE_URL is not configured');
  return sql;
}

export function isValidCategory(c: string): c is Category {
  return (CATEGORIES as readonly string[]).includes(c);
}

// ── Posts ────────────────────────────────────────────────────────────────

export async function listPosts(opts: {
  sort?: SortMode;
  category?: string | null;
  search?: string | null;
  limit?: number;
  offset?: number;
  viewerSub?: string | null;
  feed?: 'all' | 'following';
  authorSub?: string | null;
}): Promise<Post[]> {
  const db = ensureDb();
  const sort = opts.sort ?? 'hot';
  const limit = Math.min(Math.max(opts.limit ?? 25, 1), 100);
  const offset = Math.max(opts.offset ?? 0, 0);
  const viewer = opts.viewerSub ?? null;
  const category = opts.category && isValidCategory(opts.category) ? opts.category : null;
  const search = opts.search?.trim() ? `%${opts.search.trim()}%` : null;
  const followingOnly = opts.feed === 'following' && viewer != null;
  const authorSub = opts.authorSub ?? null;

  // "hot" ranks by a time-decayed score (Reddit-style): score / (age_hours+2)^1.5
  const orderBy =
    sort === 'new'
      ? db`p.created_at DESC`
      : sort === 'top'
        ? db`p.score DESC, p.created_at DESC`
        : db`(p.score / power(EXTRACT(EPOCH FROM (now() - p.created_at)) / 3600 + 2, 1.5)) DESC, p.created_at DESC`;

  const rows = await db`
    SELECT
      p.id, p.user_sub, p.author_name, p.author_picture, p.title, p.body,
      p.category, p.score, p.comment_count, p.created_at, p.updated_at,
      COALESCE(pr.is_bot, FALSE) AS is_bot,
      COALESCE(v.value, 0) AS my_vote
    FROM community_posts p
    LEFT JOIN community_votes v
      ON v.target_type = 'post' AND v.target_id = p.id AND v.user_sub = ${viewer}
    LEFT JOIN community_profiles pr ON pr.user_sub = p.user_sub
    WHERE p.is_deleted = FALSE AND p.is_hidden = FALSE
      ${category ? db`AND p.category = ${category}` : db``}
      ${search ? db`AND (p.title ILIKE ${search} OR p.body ILIKE ${search})` : db``}
      ${authorSub ? db`AND p.user_sub = ${authorSub}` : db``}
      ${
        followingOnly
          ? db`AND p.user_sub IN (SELECT following_sub FROM community_follows WHERE follower_sub = ${viewer})`
          : db``
      }
    ORDER BY ${orderBy}
    LIMIT ${limit} OFFSET ${offset}
  `;
  return rows as unknown as Post[];
}

export async function getPost(id: number, viewerSub?: string | null): Promise<Post | null> {
  const db = ensureDb();
  const rows = await db`
    SELECT
      p.id, p.user_sub, p.author_name, p.author_picture, p.title, p.body,
      p.category, p.score, p.comment_count, p.created_at, p.updated_at,
      COALESCE(pr.is_bot, FALSE) AS is_bot,
      COALESCE(v.value, 0) AS my_vote
    FROM community_posts p
    LEFT JOIN community_votes v
      ON v.target_type = 'post' AND v.target_id = p.id AND v.user_sub = ${viewerSub ?? null}
    LEFT JOIN community_profiles pr ON pr.user_sub = p.user_sub
    WHERE p.id = ${id} AND p.is_deleted = FALSE AND p.is_hidden = FALSE
    LIMIT 1
  `;
  return (rows[0] as unknown as Post) ?? null;
}

/** Keep the canonical profile fresh whenever a member is active. Tx-scoped. */
async function touchProfileTx(
  tx: postgres.TransactionSql,
  p: { user_sub: string; display_name: string; picture?: string | null; is_bot?: boolean; postDelta?: number },
) {
  await tx`
    INSERT INTO community_profiles (user_sub, display_name, picture, is_bot, post_count)
    VALUES (${p.user_sub}, ${p.display_name}, ${p.picture ?? null}, ${p.is_bot ?? false}, ${Math.max(p.postDelta ?? 0, 0)})
    ON CONFLICT (user_sub) DO UPDATE SET
      display_name = EXCLUDED.display_name,
      picture = COALESCE(EXCLUDED.picture, community_profiles.picture),
      post_count = community_profiles.post_count + ${p.postDelta ?? 0},
      updated_at = now()
  `;
}

export async function createPost(data: {
  user_sub: string;
  author_name: string;
  author_picture?: string | null;
  title: string;
  body: string;
  category: string;
  is_bot?: boolean;
}): Promise<Post> {
  const db = ensureDb();
  const category = isValidCategory(data.category) ? data.category : 'discussion';
  return (await db.begin(async (tx) => {
    const rows = await tx`
      INSERT INTO community_posts (user_sub, author_name, author_picture, title, body, category)
      VALUES (${data.user_sub}, ${data.author_name}, ${data.author_picture ?? null},
              ${data.title}, ${data.body}, ${category})
      RETURNING *, 0 AS my_vote
    `;
    await touchProfileTx(tx, {
      user_sub: data.user_sub,
      display_name: data.author_name,
      picture: data.author_picture ?? null,
      is_bot: data.is_bot ?? false,
      postDelta: 1,
    });
    const post = rows[0] as unknown as Post;
    post.is_bot = data.is_bot ?? false;
    return post;
  })) as Post;
}

export async function deletePost(id: number, userSub: string): Promise<boolean> {
  const db = ensureDb();
  // Soft delete, owner only.
  const rows = await db`
    UPDATE community_posts
    SET is_deleted = TRUE, updated_at = now()
    WHERE id = ${id} AND user_sub = ${userSub} AND is_deleted = FALSE
    RETURNING id
  `;
  return rows.length > 0;
}

// ── Comments ───────────────────────────────────────────────────────────────

export async function listComments(postId: number, viewerSub?: string | null): Promise<Comment[]> {
  const db = ensureDb();
  // Hidden (moderated) comments keep their slot in the thread but their content
  // is masked so replies underneath still make sense.
  const rows = await db`
    SELECT
      c.id, c.post_id, c.parent_id, c.user_sub,
      CASE WHEN c.is_hidden THEN '[removed]' ELSE c.author_name END AS author_name,
      CASE WHEN c.is_hidden THEN NULL ELSE c.author_picture END AS author_picture,
      CASE WHEN c.is_hidden THEN '[removed by moderation]' ELSE c.body END AS body,
      c.score, c.is_deleted, c.is_hidden, c.created_at,
      COALESCE(pr.is_bot, FALSE) AS is_bot,
      COALESCE(v.value, 0) AS my_vote
    FROM community_comments c
    LEFT JOIN community_votes v
      ON v.target_type = 'comment' AND v.target_id = c.id AND v.user_sub = ${viewerSub ?? null}
    LEFT JOIN community_profiles pr ON pr.user_sub = c.user_sub
    WHERE c.post_id = ${postId}
    ORDER BY c.score DESC, c.created_at ASC
    LIMIT 500
  `;
  return rows as unknown as Comment[];
}

export async function createComment(data: {
  post_id: number;
  parent_id?: number | null;
  user_sub: string;
  author_name: string;
  author_picture?: string | null;
  body: string;
}): Promise<Comment> {
  const db = ensureDb();
  return (await db.begin(async (tx) => {
    // Validate the post exists and is live.
    const post = await tx`SELECT id FROM community_posts WHERE id = ${data.post_id} AND is_deleted = FALSE`;
    if (post.length === 0) throw new Error('POST_NOT_FOUND');

    // Validate parent belongs to the same post when replying.
    if (data.parent_id != null) {
      const parent = await tx`
        SELECT id FROM community_comments WHERE id = ${data.parent_id} AND post_id = ${data.post_id}
      `;
      if (parent.length === 0) throw new Error('PARENT_NOT_FOUND');
    }

    const rows = await tx`
      INSERT INTO community_comments (post_id, parent_id, user_sub, author_name, author_picture, body)
      VALUES (${data.post_id}, ${data.parent_id ?? null}, ${data.user_sub},
              ${data.author_name}, ${data.author_picture ?? null}, ${data.body})
      RETURNING *, 0 AS my_vote
    `;
    await tx`
      UPDATE community_posts SET comment_count = comment_count + 1, updated_at = now()
      WHERE id = ${data.post_id}
    `;
    await touchProfileTx(tx, {
      user_sub: data.user_sub,
      display_name: data.author_name,
      picture: data.author_picture ?? null,
    });
    const comment = rows[0] as unknown as Comment;
    comment.is_bot = false;
    comment.is_hidden = false;
    return comment;
  })) as Comment;
}

export async function deleteComment(id: number, userSub: string): Promise<boolean> {
  const db = ensureDb();
  return (await db.begin(async (tx) => {
    // Soft delete (preserve thread structure), owner only.
    const rows = await tx`
      UPDATE community_comments
      SET is_deleted = TRUE, body = '[deleted]', author_name = '[deleted]', author_picture = NULL
      WHERE id = ${id} AND user_sub = ${userSub} AND is_deleted = FALSE
      RETURNING post_id
    `;
    if (rows.length === 0) return false;
    // Keep the post's denormalised comment_count honest (createComment bumped it
    // on insert; a tombstone shouldn't keep inflating the visible count). Floor
    // at 0 so a double-delete can't drive it negative.
    const postId = (rows[0] as { post_id: number }).post_id;
    await tx`
      UPDATE community_posts
      SET comment_count = GREATEST(comment_count - 1, 0), updated_at = now()
      WHERE id = ${postId}
    `;
    return true;
  })) as boolean;
}

/** True if this author posted within the last `hours` (used to keep the Aurom
 *  bot idempotent — a re-run / retried cron must not double-post). */
export async function hasRecentPost(userSub: string, hours: number): Promise<boolean> {
  const db = ensureDb();
  const rows = await db`
    SELECT 1 FROM community_posts
    WHERE user_sub = ${userSub}
      AND created_at > now() - (${hours} || ' hours')::interval
    LIMIT 1
  `;
  return rows.length > 0;
}

// ── Voting ───────────────────────────────────────────────────────────────

const TARGET_TABLE: Record<'post' | 'comment', string> = {
  post: 'community_posts',
  comment: 'community_comments',
};

/**
 * Cast (value=1|-1) or clear (value=0) a vote. Idempotent: re-sending the same
 * value clears it (toggle). Returns the new denormalised score and the
 * viewer's resulting vote.
 */
export async function vote(
  targetType: 'post' | 'comment',
  targetId: number,
  userSub: string,
  value: number,
): Promise<{ score: number; my_vote: number }> {
  const db = ensureDb();
  const table = TARGET_TABLE[targetType];
  const normalized = value > 0 ? 1 : value < 0 ? -1 : 0;

  return (await db.begin(async (tx) => {
    // Lock the target row for the whole tx so concurrent votes on the SAME
    // post/comment serialize. Without this, two requests (e.g. a double-tap or
    // the optimistic UI firing twice) both read the old vote, both compute the
    // same delta, and the denormalised score drifts (+2 while one vote survives).
    const locked = await tx`SELECT id FROM ${tx(table)} WHERE id = ${targetId} FOR UPDATE`;
    if (locked.length === 0) throw new Error('TARGET_NOT_FOUND');

    const existing = await tx`
      SELECT value FROM community_votes
      WHERE user_sub = ${userSub} AND target_type = ${targetType} AND target_id = ${targetId}
    `;
    const prev = existing.length ? (existing[0] as { value: number }).value : 0;

    // Toggle: clicking the same arrow again removes the vote.
    const next = normalized === prev ? 0 : normalized;
    const delta = next - prev;

    if (next === 0) {
      await tx`
        DELETE FROM community_votes
        WHERE user_sub = ${userSub} AND target_type = ${targetType} AND target_id = ${targetId}
      `;
    } else {
      await tx`
        INSERT INTO community_votes (user_sub, target_type, target_id, value)
        VALUES (${userSub}, ${targetType}, ${targetId}, ${next})
        ON CONFLICT (user_sub, target_type, target_id)
        DO UPDATE SET value = EXCLUDED.value
      `;
    }

    let score = 0;
    if (delta !== 0) {
      const updated = await tx`
        UPDATE ${tx(table)} SET score = score + ${delta} WHERE id = ${targetId} RETURNING score
      `;
      if (updated.length === 0) throw new Error('TARGET_NOT_FOUND');
      score = (updated[0] as { score: number }).score;
    } else {
      const cur = await tx`SELECT score FROM ${tx(table)} WHERE id = ${targetId}`;
      if (cur.length === 0) throw new Error('TARGET_NOT_FOUND');
      score = (cur[0] as { score: number }).score;
    }

    return { score, my_vote: next };
  })) as { score: number; my_vote: number };
}

// ── Profiles ───────────────────────────────────────────────────────────────

/** Ensure a profile row exists (used before follow / on first sight). */
export async function ensureProfile(p: {
  user_sub: string;
  display_name: string;
  picture?: string | null;
}): Promise<void> {
  const db = ensureDb();
  await db`
    INSERT INTO community_profiles (user_sub, display_name, picture)
    VALUES (${p.user_sub}, ${p.display_name}, ${p.picture ?? null})
    ON CONFLICT (user_sub) DO UPDATE SET
      display_name = EXCLUDED.display_name,
      picture = COALESCE(EXCLUDED.picture, community_profiles.picture),
      updated_at = now()
  `;
}

export async function getProfile(userSub: string, viewerSub?: string | null): Promise<Profile | null> {
  const db = ensureDb();
  const rows = await db`
    SELECT
      pr.user_sub, pr.display_name, pr.picture, pr.bio, pr.is_bot,
      (SELECT COUNT(*)::int FROM community_follows f WHERE f.following_sub = pr.user_sub) AS follower_count,
      (SELECT COUNT(*)::int FROM community_follows f WHERE f.follower_sub = pr.user_sub) AS following_count,
      (SELECT COUNT(*)::int FROM community_posts p WHERE p.user_sub = pr.user_sub AND p.is_deleted = FALSE AND p.is_hidden = FALSE) AS post_count,
      EXISTS (
        SELECT 1 FROM community_follows f
        WHERE f.following_sub = pr.user_sub AND f.follower_sub = ${viewerSub ?? null}
      ) AS is_following
    FROM community_profiles pr
    WHERE pr.user_sub = ${userSub}
    LIMIT 1
  `;
  return (rows[0] as unknown as Profile) ?? null;
}

export async function updateBio(userSub: string, bio: string): Promise<void> {
  const db = ensureDb();
  await db`
    UPDATE community_profiles SET bio = ${bio.slice(0, 500)}, updated_at = now()
    WHERE user_sub = ${userSub}
  `;
}

// ── Member directory ("who's here") ─────────────────────────────────────────

export type MemberSort = 'active' | 'popular' | 'new';

export interface Member extends Profile {
  created_at: string;
}

/**
 * List everyone who has a community profile, for the member directory.
 * sort: 'active' (most posts) | 'popular' (most followers) | 'new' (most recent).
 * Counts are computed live so they match the profile page exactly.
 */
export async function listMembers(opts: {
  sort?: MemberSort;
  search?: string | null;
  limit?: number;
  offset?: number;
  viewerSub?: string | null;
}): Promise<Member[]> {
  const db = ensureDb();
  const limit = Math.min(Math.max(opts.limit ?? 30, 1), 60);
  const offset = Math.max(opts.offset ?? 0, 0);
  const viewer = opts.viewerSub ?? null;
  const search = (opts.search ?? '').trim();
  const sort = opts.sort ?? 'active';

  // ORDER BY references the computed aliases (Postgres allows alias ordering).
  const orderBy =
    sort === 'new'
      ? db`pr.created_at DESC`
      : sort === 'popular'
        ? db`follower_count DESC, pr.created_at DESC`
        : db`post_count DESC, follower_count DESC, pr.created_at DESC`;

  const rows = await db`
    SELECT
      pr.user_sub, pr.display_name, pr.picture, pr.bio, pr.is_bot, pr.created_at,
      (SELECT COUNT(*)::int FROM community_follows f WHERE f.following_sub = pr.user_sub) AS follower_count,
      (SELECT COUNT(*)::int FROM community_follows f WHERE f.follower_sub = pr.user_sub) AS following_count,
      (SELECT COUNT(*)::int FROM community_posts p WHERE p.user_sub = pr.user_sub AND p.is_deleted = FALSE AND p.is_hidden = FALSE) AS post_count,
      EXISTS (
        SELECT 1 FROM community_follows f
        WHERE f.following_sub = pr.user_sub AND f.follower_sub = ${viewer}
      ) AS is_following
    FROM community_profiles pr
    ${search ? db`WHERE pr.display_name ILIKE ${'%' + search + '%'}` : db``}
    ORDER BY ${orderBy}
    LIMIT ${limit} OFFSET ${offset}
  `;
  return rows as unknown as Member[];
}

/** Total number of members (optionally matching a display-name search). */
export async function countMembers(search?: string | null): Promise<number> {
  const db = ensureDb();
  const q = (search ?? '').trim();
  const rows = await db`
    SELECT COUNT(*)::int AS c FROM community_profiles pr
    ${q ? db`WHERE pr.display_name ILIKE ${'%' + q + '%'}` : db``}
  `;
  return (rows[0] as { c: number }).c;
}

// ── Following (open graph — anyone may follow anyone) ───────────────────────

export async function setFollow(
  followerSub: string,
  followingSub: string,
  follow: boolean,
): Promise<{ following: boolean; follower_count: number }> {
  const db = ensureDb();
  if (followerSub === followingSub) throw new Error('CANNOT_FOLLOW_SELF');

  if (follow) {
    await db`
      INSERT INTO community_follows (follower_sub, following_sub)
      VALUES (${followerSub}, ${followingSub})
      ON CONFLICT (follower_sub, following_sub) DO NOTHING
    `;
  } else {
    await db`
      DELETE FROM community_follows
      WHERE follower_sub = ${followerSub} AND following_sub = ${followingSub}
    `;
  }

  const counts = await db`
    SELECT COUNT(*)::int AS c FROM community_follows WHERE following_sub = ${followingSub}
  `;
  return { following: follow, follower_count: (counts[0] as { c: number }).c };
}

// ── Reporting / lightweight moderation ──────────────────────────────────────

/**
 * File a report against a post/comment. Once REPORT_HIDE_THRESHOLD distinct
 * members have reported the same target it is auto-hidden from listings.
 * Re-reporting the same target is a no-op (idempotent).
 */
export async function report(
  reporterSub: string,
  targetType: 'post' | 'comment',
  targetId: number,
  reason: string,
): Promise<{ reported: boolean; hidden: boolean }> {
  const db = ensureDb();
  const table = TARGET_TABLE[targetType];

  return (await db.begin(async (tx) => {
    const exists = await tx`SELECT id FROM ${tx(table)} WHERE id = ${targetId} AND is_deleted = FALSE`;
    if (exists.length === 0) throw new Error('TARGET_NOT_FOUND');

    await tx`
      INSERT INTO community_reports (reporter_sub, target_type, target_id, reason)
      VALUES (${reporterSub}, ${targetType}, ${targetId}, ${reason.slice(0, 500)})
      ON CONFLICT (reporter_sub, target_type, target_id) DO NOTHING
    `;

    const counted = await tx`
      SELECT COUNT(DISTINCT reporter_sub)::int AS c
      FROM community_reports
      WHERE target_type = ${targetType} AND target_id = ${targetId}
        AND resolved = FALSE
    `;
    const distinct = (counted[0] as { c: number }).c;

    let hidden = false;
    if (distinct >= REPORT_HIDE_THRESHOLD) {
      await tx`UPDATE ${tx(table)} SET is_hidden = TRUE WHERE id = ${targetId}`;
      hidden = true;
    }
    return { reported: true, hidden };
  })) as { reported: boolean; hidden: boolean };
}
