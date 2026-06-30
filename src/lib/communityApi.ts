/**
 * communityApi.ts — Browser-side client for the community / discussion API.
 * Talks to the Next.js route handlers under /api/community (same origin), which
 * read the signed session cookie for auth — no token plumbing needed.
 */

export interface CommunityPost {
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
  my_vote: number;
}

export interface CommunityComment {
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
  my_vote: number;
}

export interface CommunityProfile {
  user_sub: string;
  display_name: string;
  picture: string | null;
  bio: string;
  is_bot: boolean;
  follower_count: number;
  following_count: number;
  post_count: number;
  is_following?: boolean;
}

export interface CommunityMember extends CommunityProfile {
  created_at: string;
}

export type SortMode = 'hot' | 'new' | 'top';
export type FeedMode = 'all' | 'following';
export type MemberSort = 'active' | 'popular' | 'new';

export interface CategoryMeta {
  id: string;
  label: string;
  emoji: string;
}

export const CATEGORIES: CategoryMeta[] = [
  { id: 'discussion', label: 'Discussion', emoji: '💬' },
  { id: 'question', label: 'Question', emoji: '❓' },
  { id: 'wisdom', label: 'Wisdom', emoji: '🪔' },
  { id: 'scripture', label: 'Scripture', emoji: '📜' },
  { id: 'experience', label: 'Experience', emoji: '🧘' },
  { id: 'announcement', label: 'Announcement', emoji: '📢' },
];

export function categoryMeta(id: string): CategoryMeta {
  return CATEGORIES.find((c) => c.id === id) ?? { id, label: id, emoji: '•' };
}

async function jsonOrThrow(res: Response) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data?.error || `Request failed (${res.status})`);
  }
  return data;
}

export const communityApi = {
  async listPosts(opts: {
    sort?: SortMode;
    category?: string | null;
    q?: string | null;
    feed?: FeedMode;
  } = {}): Promise<CommunityPost[]> {
    const params = new URLSearchParams();
    if (opts.sort) params.set('sort', opts.sort);
    if (opts.category) params.set('category', opts.category);
    if (opts.q) params.set('q', opts.q);
    if (opts.feed) params.set('feed', opts.feed);
    const res = await fetch(`/api/community/posts?${params.toString()}`, {
      cache: 'no-store',
    });
    const data = await jsonOrThrow(res);
    return data.posts as CommunityPost[];
  },

  async getPost(id: number): Promise<{ post: CommunityPost; comments: CommunityComment[] }> {
    const res = await fetch(`/api/community/posts/${id}`, { cache: 'no-store' });
    return jsonOrThrow(res);
  },

  async createPost(input: {
    title: string;
    body: string;
    category: string;
  }): Promise<CommunityPost> {
    const res = await fetch('/api/community/posts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    });
    const data = await jsonOrThrow(res);
    return data.post as CommunityPost;
  },

  async deletePost(id: number): Promise<void> {
    const res = await fetch(`/api/community/posts/${id}`, { method: 'DELETE' });
    await jsonOrThrow(res);
  },

  async votePost(id: number, value: number): Promise<{ score: number; my_vote: number }> {
    const res = await fetch(`/api/community/posts/${id}/vote`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value }),
    });
    return jsonOrThrow(res);
  },

  async addComment(
    postId: number,
    input: { body: string; parent_id?: number | null },
  ): Promise<CommunityComment> {
    const res = await fetch(`/api/community/posts/${postId}/comments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    });
    const data = await jsonOrThrow(res);
    return data.comment as CommunityComment;
  },

  async deleteComment(id: number): Promise<void> {
    const res = await fetch(`/api/community/comments/${id}`, { method: 'DELETE' });
    await jsonOrThrow(res);
  },

  async voteComment(id: number, value: number): Promise<{ score: number; my_vote: number }> {
    const res = await fetch(`/api/community/comments/${id}/vote`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value }),
    });
    return jsonOrThrow(res);
  },

  async getProfile(
    userSub: string,
  ): Promise<{ profile: CommunityProfile; posts: CommunityPost[] }> {
    const res = await fetch(`/api/community/profile/${encodeURIComponent(userSub)}`, {
      cache: 'no-store',
    });
    return jsonOrThrow(res);
  },

  async listMembers(opts: {
    sort?: MemberSort;
    q?: string | null;
    offset?: number;
  } = {}): Promise<{ members: CommunityMember[]; total?: number; has_more: boolean }> {
    const params = new URLSearchParams();
    if (opts.sort) params.set('sort', opts.sort);
    if (opts.q) params.set('q', opts.q);
    if (opts.offset) params.set('offset', String(opts.offset));
    const res = await fetch(`/api/community/members?${params.toString()}`, {
      cache: 'no-store',
    });
    return jsonOrThrow(res);
  },

  async updateBio(bio: string): Promise<CommunityProfile> {
    const res = await fetch('/api/community/profile', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bio }),
    });
    const data = await jsonOrThrow(res);
    return data.profile as CommunityProfile;
  },

  async follow(
    targetSub: string,
    follow: boolean,
  ): Promise<{ following: boolean; follower_count: number }> {
    const res = await fetch('/api/community/follow', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_sub: targetSub, follow }),
    });
    return jsonOrThrow(res);
  },

  async report(
    targetType: 'post' | 'comment',
    targetId: number,
    reason: string,
  ): Promise<{ reported: boolean; hidden: boolean }> {
    const res = await fetch('/api/community/report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_type: targetType, target_id: targetId, reason }),
    });
    return jsonOrThrow(res);
  },
};

/** Strip common Markdown tokens to a clean one-line-ish preview for the feed. */
export function toPlainPreview(md: string, max = 220): string {
  const text = md
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/^>\s?/gm, "")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^[-*+]\s+/gm, "")
    .replace(/(\*\*|__|\*|_|~~)/g, "")
    .replace(/\s+/g, " ")
    .trim();
  return text.length > max ? text.slice(0, max).trimEnd() + "…" : text;
}

/** Compact relative-time formatter ("3h", "2d", "just now"). */
export function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const secs = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (secs < 45) return 'just now';
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo ago`;
  return `${Math.floor(months / 12)}y ago`;
}
