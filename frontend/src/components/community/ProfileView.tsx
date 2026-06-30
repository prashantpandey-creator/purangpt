"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Loader2, Pencil, Sparkles, Check, X } from "lucide-react";
import {
  communityApi,
  type CommunityProfile,
  type CommunityPost,
} from "@/lib/communityApi";
import { PostCard } from "@/components/community/PostCard";
import { FollowButton } from "@/components/community/FollowButton";
import { Markdown } from "@/components/community/Markdown";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="text-center">
      <div className="font-cinzel text-lg text-gray-100">{value}</div>
      <div className="text-xs uppercase tracking-wide text-gray-500">{label}</div>
    </div>
  );
}

export function ProfileView({ userSub }: { userSub: string }) {
  const { user } = useAuth();
  const { toast } = useToast();
  const [profile, setProfile] = useState<CommunityProfile | null>(null);
  const [posts, setPosts] = useState<CommunityPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const [editingBio, setEditingBio] = useState(false);
  const [bioDraft, setBioDraft] = useState("");
  const [savingBio, setSavingBio] = useState(false);

  const isOwn = user?.sub === userSub;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await communityApi.getProfile(userSub);
      setProfile(data.profile);
      setPosts(data.posts);
      setBioDraft(data.profile.bio);
    } catch {
      setNotFound(true);
    } finally {
      setLoading(false);
    }
  }, [userSub]);

  useEffect(() => {
    load();
  }, [load]);

  const saveBio = async () => {
    setSavingBio(true);
    try {
      const updated = await communityApi.updateBio(bioDraft);
      setProfile(updated);
      setEditingBio(false);
      toast("Profile updated", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to update", "error");
    } finally {
      setSavingBio(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-24 text-saffron">
        <Loader2 className="animate-spin" size={28} />
      </div>
    );
  }

  if (notFound || !profile) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-24 text-center">
        <h1 className="font-cinzel mb-4 text-2xl text-gray-200">Profile not found</h1>
        <Link href="/community" className="btn-secondary">
          Back to Community
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 pb-20 pt-24">
      <Link
        href="/community"
        className="mb-6 inline-flex items-center gap-2 text-sm text-gray-400 transition-colors hover:text-white"
      >
        <ArrowLeft size={18} />
        Back to Community
      </Link>

      {/* Header card */}
      <div className={`card p-6 ${profile.is_bot ? "border-saffron/25" : ""}`}>
        <div className="flex items-start gap-4">
          <div className="flex h-20 w-20 flex-shrink-0 items-center justify-center overflow-hidden rounded-full bg-gradient-to-br from-[#e8b63f] to-[#b8861f] text-2xl font-bold text-[#0a0a0a]">
            {profile.picture ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={profile.picture} alt="" className="h-full w-full object-cover" />
            ) : (
              (profile.display_name?.[0] ?? "?").toUpperCase()
            )}
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="font-cinzel text-2xl font-bold text-gray-100">
                {profile.display_name}
              </h1>
              {profile.is_bot && (
                <span className="inline-flex items-center gap-1 rounded-full border border-saffron/40 bg-saffron/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-saffron">
                  <Sparkles size={10} /> Community Bot
                </span>
              )}
            </div>

            {/* Bio */}
            {editingBio ? (
              <div className="mt-3">
                <textarea
                  value={bioDraft}
                  onChange={(e) => setBioDraft(e.target.value)}
                  rows={3}
                  maxLength={500}
                  placeholder="Tell the community a little about yourself…"
                  className="w-full resize-y rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-gray-100 outline-none focus:border-saffron/60"
                />
                <div className="mt-2 flex gap-2">
                  <button onClick={saveBio} disabled={savingBio} className="btn-primary !px-3 !py-1 !text-xs inline-flex items-center gap-1">
                    <Check size={14} /> {savingBio ? "Saving…" : "Save"}
                  </button>
                  <button
                    onClick={() => {
                      setBioDraft(profile.bio);
                      setEditingBio(false);
                    }}
                    className="inline-flex items-center gap-1 rounded-md px-3 py-1 text-xs text-gray-400 hover:text-gray-200"
                  >
                    <X size={14} /> Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="mt-2 text-sm text-gray-400">
                {profile.bio ? (
                  <Markdown className="text-sm">{profile.bio}</Markdown>
                ) : isOwn ? (
                  <span className="italic text-gray-600">No bio yet.</span>
                ) : null}
                {isOwn && (
                  <button
                    onClick={() => setEditingBio(true)}
                    className="mt-1 inline-flex items-center gap-1 text-xs text-gray-500 transition-colors hover:text-saffron"
                  >
                    <Pencil size={12} /> Edit bio
                  </button>
                )}
              </div>
            )}
          </div>

          {!isOwn && (
            <FollowButton
              targetSub={profile.user_sub}
              initialFollowing={profile.is_following}
              onChange={(_, followerCount) =>
                setProfile((p) => (p ? { ...p, follower_count: followerCount } : p))
              }
            />
          )}
        </div>

        {/* Stats */}
        <div className="mt-6 flex gap-8 border-t border-white/10 pt-4">
          <Stat label="Posts" value={profile.post_count} />
          <Stat label="Followers" value={profile.follower_count} />
          <Stat label="Following" value={profile.following_count} />
        </div>
      </div>

      {/* Their posts */}
      <h2 className="font-cinzel mb-4 mt-8 text-xl font-semibold text-gray-100">
        {isOwn ? "Your posts" : "Posts"}
      </h2>
      {posts.length === 0 ? (
        <p className="text-sm text-gray-500">No posts yet.</p>
      ) : (
        <div className="space-y-3">
          {posts.map((post) => (
            <PostCard key={post.id} post={post} />
          ))}
        </div>
      )}
    </div>
  );
}
