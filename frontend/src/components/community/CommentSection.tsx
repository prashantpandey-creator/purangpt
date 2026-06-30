"use client";

import { useMemo, useState } from "react";
import { CornerDownRight, Trash2 } from "lucide-react";
import {
  communityApi,
  timeAgo,
  type CommunityComment,
} from "@/lib/communityApi";
import { VoteControl } from "@/components/community/VoteControl";
import { RichTextEditor } from "@/components/community/RichTextEditor";
import { Markdown } from "@/components/community/Markdown";
import { AuthorBadge } from "@/components/community/AuthorBadge";
import { ReportButton } from "@/components/community/ReportButton";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";

interface TreeNode extends CommunityComment {
  children: TreeNode[];
}

function buildTree(comments: CommunityComment[]): TreeNode[] {
  const map = new Map<number, TreeNode>();
  comments.forEach((c) => map.set(c.id, { ...c, children: [] }));
  const roots: TreeNode[] = [];
  map.forEach((node) => {
    if (node.parent_id != null && map.has(node.parent_id)) {
      map.get(node.parent_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  });
  return roots;
}

interface CommentSectionProps {
  postId: number;
  comments: CommunityComment[];
  onChanged: (comments: CommunityComment[]) => void;
}

export function CommentSection({ postId, comments, onChanged }: CommentSectionProps) {
  const { user } = useAuth();
  const { toast } = useToast();
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const tree = useMemo(() => buildTree(comments), [comments]);

  const handleTopLevel = async () => {
    if (!user) {
      toast("Sign in to comment", "info");
      return;
    }
    if (!text.trim()) return;
    setSubmitting(true);
    try {
      const c = await communityApi.addComment(postId, { body: text.trim() });
      onChanged([...comments, c]);
      setText("");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to comment", "error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="mt-8">
      <h3 className="font-cinzel mb-4 text-xl font-semibold text-gray-100">
        {comments.length} {comments.length === 1 ? "Comment" : "Comments"}
      </h3>

      {/* Top-level composer */}
      <div className="card mb-6 p-4">
        <RichTextEditor
          value={text}
          onChange={setText}
          rows={3}
          maxLength={10000}
          disabled={!user}
          placeholder={user ? "Add to the discussion… Markdown & emoji supported 🪔" : "Sign in to join the discussion"}
        />
        <div className="mt-3 flex justify-end">
          <button
            onClick={handleTopLevel}
            disabled={submitting || !text.trim() || !user}
            className="btn-primary"
          >
            {submitting ? "Posting…" : "Comment"}
          </button>
        </div>
      </div>

      <div className="space-y-4">
        {tree.length === 0 && (
          <p className="text-sm text-gray-500">No comments yet. Be the first to share.</p>
        )}
        {tree.map((node) => (
          <CommentNode
            key={node.id}
            node={node}
            postId={postId}
            depth={0}
            comments={comments}
            onChanged={onChanged}
          />
        ))}
      </div>
    </section>
  );
}

function CommentNode({
  node,
  postId,
  depth,
  comments,
  onChanged,
}: {
  node: TreeNode;
  postId: number;
  depth: number;
  comments: CommunityComment[];
  onChanged: (comments: CommunityComment[]) => void;
}) {
  const { user } = useAuth();
  const { toast } = useToast();
  const [replying, setReplying] = useState(false);
  const [replyText, setReplyText] = useState("");
  const [busy, setBusy] = useState(false);
  const [score, setScore] = useState(node.score);
  const [myVote, setMyVote] = useState(node.my_vote);

  const isOwner = user?.sub === node.user_sub;

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
      const res = await communityApi.voteComment(node.id, value);
      setScore(res.score);
      setMyVote(res.my_vote);
    } catch (e) {
      setScore(prevScore);
      setMyVote(prevVote);
      toast(e instanceof Error ? e.message : "Vote failed", "error");
    }
  };

  const handleReply = async () => {
    if (!replyText.trim()) return;
    setBusy(true);
    try {
      const c = await communityApi.addComment(postId, {
        body: replyText.trim(),
        parent_id: node.id,
      });
      onChanged([...comments, c]);
      setReplyText("");
      setReplying(false);
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to reply", "error");
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm("Delete this comment?")) return;
    try {
      await communityApi.deleteComment(node.id);
      onChanged(
        comments.map((c) =>
          c.id === node.id
            ? { ...c, is_deleted: true, body: "[deleted]", author_name: "[deleted]" }
            : c,
        ),
      );
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to delete", "error");
    }
  };

  return (
    <div className={depth > 0 ? "border-l border-white/10 pl-4" : ""}>
      <div className="flex gap-3">
        <div className="pt-0.5">
          <VoteControl
            score={score}
            myVote={myVote}
            onVote={handleVote}
            size={16}
          />
        </div>
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex items-center gap-2 text-xs text-gray-500">
            <AuthorBadge
              userSub={node.user_sub}
              name={node.author_name}
              picture={node.author_picture}
              isBot={node.is_bot}
              size={18}
            />
            <span>·</span>
            <span>{timeAgo(node.created_at)}</span>
          </div>

          {node.is_deleted || node.is_hidden ? (
            <p className="text-sm italic text-gray-500">{node.body}</p>
          ) : (
            <Markdown className="text-sm">{node.body}</Markdown>
          )}

          <div className="mt-1.5 flex items-center gap-3 text-xs text-gray-500">
            {!node.is_deleted && !node.is_hidden && (
              <button
                onClick={() => {
                  if (!user) {
                    toast("Sign in to reply", "info");
                    return;
                  }
                  setReplying((r) => !r);
                }}
                className="inline-flex items-center gap-1 transition-colors hover:text-saffron"
              >
                <CornerDownRight size={13} /> Reply
              </button>
            )}
            {isOwner && !node.is_deleted && !node.is_hidden && (
              <button
                onClick={handleDelete}
                className="inline-flex items-center gap-1 transition-colors hover:text-red-400"
              >
                <Trash2 size={13} /> Delete
              </button>
            )}
            {!isOwner && !node.is_deleted && !node.is_hidden && (
              <ReportButton targetType="comment" targetId={node.id} compact />
            )}
          </div>

          {replying && (
            <div className="mt-3">
              <RichTextEditor
                value={replyText}
                onChange={setReplyText}
                rows={2}
                compact
                autoFocus
                maxLength={10000}
                placeholder="Write a reply… 🪔"
              />
              <div className="mt-2 flex justify-end gap-2">
                <button
                  onClick={() => setReplying(false)}
                  className="rounded-md px-3 py-1 text-xs text-gray-400 hover:text-gray-200"
                >
                  Cancel
                </button>
                <button
                  onClick={handleReply}
                  disabled={busy || !replyText.trim()}
                  className="btn-primary !px-3 !py-1 !text-xs"
                >
                  {busy ? "Replying…" : "Reply"}
                </button>
              </div>
            </div>
          )}

          {node.children.length > 0 && (
            <div className="mt-3 space-y-3">
              {node.children.map((child) => (
                <CommentNode
                  key={child.id}
                  node={child}
                  postId={postId}
                  depth={depth + 1}
                  comments={comments}
                  onChanged={onChanged}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
