"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Loader2, Trash2 } from "lucide-react";
import {
  communityApi,
  categoryMeta,
  timeAgo,
  type CommunityPost,
  type CommunityComment,
} from "@/lib/communityApi";
import { VoteControl } from "@/components/community/VoteControl";
import { CommentSection } from "@/components/community/CommentSection";
import { Markdown } from "@/components/community/Markdown";
import { AuthorBadge } from "@/components/community/AuthorBadge";
import { FollowButton } from "@/components/community/FollowButton";
import { ReportButton } from "@/components/community/ReportButton";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";

export function PostDetail({ postId }: { postId: number }) {
  const router = useRouter();
  const { user } = useAuth();
  const { toast } = useToast();
  const [post, setPost] = useState<CommunityPost | null>(null);
  const [comments, setComments] = useState<CommunityComment[]>([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await communityApi.getPost(postId);
      setPost(data.post);
      setComments(data.comments);
    } catch {
      setNotFound(true);
    } finally {
      setLoading(false);
    }
  }, [postId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleVote = async (value: number) => {
    if (!post) return;
    if (!user) {
      toast("Sign in to vote", "info");
      return;
    }
    const prevScore = post.score;
    const prevVote = post.my_vote;
    const next = post.my_vote === value ? 0 : value;
    setPost({ ...post, my_vote: next, score: prevScore + (next - prevVote) });
    try {
      const res = await communityApi.votePost(post.id, value);
      setPost((p) => (p ? { ...p, score: res.score, my_vote: res.my_vote } : p));
    } catch (e) {
      setPost((p) => (p ? { ...p, score: prevScore, my_vote: prevVote } : p));
      toast(e instanceof Error ? e.message : "Vote failed", "error");
    }
  };

  const handleDelete = async () => {
    if (!post) return;
    if (!confirm("Delete this post? This cannot be undone.")) return;
    try {
      await communityApi.deletePost(post.id);
      toast("Post deleted", "success");
      router.push("/community");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to delete", "error");
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-24 text-saffron">
        <Loader2 className="animate-spin" size={28} />
      </div>
    );
  }

  if (notFound || !post) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-24 text-center">
        <h1 className="font-cinzel mb-4 text-2xl text-gray-200">Post not found</h1>
        <Link href="/community" className="btn-secondary">
          Back to Community
        </Link>
      </div>
    );
  }

  const cat = categoryMeta(post.category);
  const isOwner = user?.sub === post.user_sub;

  return (
    <div className="mx-auto max-w-3xl px-4 pb-20 pt-24">
      <Link
        href="/community"
        className="mb-6 inline-flex items-center gap-2 text-sm text-gray-400 transition-colors hover:text-white"
      >
        <ArrowLeft size={18} />
        Back to Community
      </Link>

      <article className={`card flex gap-4 p-6 ${post.is_bot ? "border-saffron/25" : ""}`}>
        <div className="pt-1">
          <VoteControl score={post.score} myVote={post.my_vote} onVote={handleVote} />
        </div>

        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-gray-500">
            <span className="inline-flex items-center gap-1 rounded-full border border-saffron/30 bg-saffron/5 px-2 py-0.5 text-saffron">
              <span>{cat.emoji}</span>
              {cat.label}
            </span>
            <span>·</span>
            <AuthorBadge
              userSub={post.user_sub}
              name={post.author_name}
              picture={post.author_picture}
              isBot={post.is_bot}
            />
            <span>·</span>
            <span>{timeAgo(post.created_at)}</span>
            {!isOwner && <FollowButton targetSub={post.user_sub} size="sm" />}
          </div>

          <h1 className="font-cinzel text-2xl font-bold text-gray-100">{post.title}</h1>

          {post.body && (
            <div className="mt-4">
              <Markdown>{post.body}</Markdown>
            </div>
          )}

          <div className="mt-5 flex items-center gap-4 border-t border-white/10 pt-3 text-xs text-gray-500">
            {isOwner ? (
              <button
                onClick={handleDelete}
                className="inline-flex items-center gap-1.5 transition-colors hover:text-red-400"
              >
                <Trash2 size={14} /> Delete post
              </button>
            ) : (
              <ReportButton targetType="post" targetId={post.id} />
            )}
          </div>
        </div>
      </article>

      <CommentSection postId={post.id} comments={comments} onChanged={setComments} />
    </div>
  );
}
