"use client";

import { useState } from "react";
import Link from "next/link";
import { MessageSquare } from "lucide-react";
import {
  communityApi,
  categoryMeta,
  timeAgo,
  toPlainPreview,
  type CommunityPost,
} from "@/lib/communityApi";
import { VoteControl } from "@/components/community/VoteControl";
import { AuthorBadge } from "@/components/community/AuthorBadge";
import { ReportButton } from "@/components/community/ReportButton";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";

export function PostCard({ post }: { post: CommunityPost }) {
  const { user } = useAuth();
  const { toast } = useToast();
  const [score, setScore] = useState(post.score);
  const [myVote, setMyVote] = useState(post.my_vote);
  const cat = categoryMeta(post.category);
  const isOwner = user?.sub === post.user_sub;

  const handleVote = async (value: number) => {
    if (!user) {
      toast("Sign in to vote", "info");
      return;
    }
    const prevScore = score;
    const prevVote = myVote;
    const next = myVote === value ? 0 : value;
    setMyVote(next);
    setScore(prevScore + (next - prevVote));
    try {
      const res = await communityApi.votePost(post.id, value);
      setScore(res.score);
      setMyVote(res.my_vote);
    } catch (e) {
      setScore(prevScore);
      setMyVote(prevVote);
      toast(e instanceof Error ? e.message : "Vote failed", "error");
    }
  };

  const preview = toPlainPreview(post.body);

  return (
    <article className={`card flex gap-3 p-4 ${post.is_bot ? "border-saffron/25" : ""}`}>
      <div className="pt-1">
        <VoteControl score={score} myVote={myVote} onVote={handleVote} />
      </div>

      <div className="min-w-0 flex-1">
        <div className="mb-1.5 flex flex-wrap items-center gap-2 text-xs text-gray-500">
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
            showAvatar={false}
          />
          <span>·</span>
          <span>{timeAgo(post.created_at)}</span>
        </div>

        <Link href={`/community/${post.id}`} className="group block">
          <h2 className="font-cinzel text-lg font-semibold text-gray-100 transition-colors group-hover:text-saffron">
            {post.title}
          </h2>
          {preview && (
            <p className="mt-1 line-clamp-3 text-sm text-gray-400">{preview}</p>
          )}
        </Link>

        <div className="mt-3 flex items-center gap-4 text-xs text-gray-500">
          <Link
            href={`/community/${post.id}`}
            className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-sm text-gray-400 transition-colors hover:bg-white/5 hover:text-gray-200"
          >
            <MessageSquare size={16} />
            {post.comment_count} {post.comment_count === 1 ? "comment" : "comments"}
          </Link>
          {!isOwner && <ReportButton targetType="post" targetId={post.id} compact />}
        </div>
      </div>
    </article>
  );
}
