"use client";

import { useEffect, useState } from "react";
import { UserPlus, UserCheck } from "lucide-react";
import { communityApi } from "@/lib/communityApi";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";

/**
 * Open-graph follow toggle. Anyone may follow anyone — no approval needed.
 * If `initialFollowing` is omitted it's fetched lazily from the profile.
 */
export function FollowButton({
  targetSub,
  initialFollowing,
  onChange,
  size = "md",
}: {
  targetSub: string;
  initialFollowing?: boolean;
  onChange?: (following: boolean, followerCount: number) => void;
  size?: "sm" | "md";
}) {
  const { user } = useAuth();
  const { toast } = useToast();
  const [following, setFollowing] = useState(Boolean(initialFollowing));
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(initialFollowing !== undefined);

  useEffect(() => {
    if (initialFollowing !== undefined) {
      setFollowing(initialFollowing);
      setReady(true);
      return;
    }
    let alive = true;
    communityApi
      .getProfile(targetSub)
      .then((d) => {
        if (alive) {
          setFollowing(Boolean(d.profile.is_following));
          setReady(true);
        }
      })
      .catch(() => alive && setReady(true));
    return () => {
      alive = false;
    };
  }, [targetSub, initialFollowing]);

  // Hide the button on your own profile / content.
  if (user?.sub === targetSub) return null;

  const toggle = async () => {
    if (!user) {
      toast("Sign in to follow", "info");
      return;
    }
    const next = !following;
    setFollowing(next);
    setBusy(true);
    try {
      const res = await communityApi.follow(targetSub, next);
      setFollowing(res.following);
      onChange?.(res.following, res.follower_count);
    } catch (e) {
      setFollowing(!next);
      toast(e instanceof Error ? e.message : "Failed to update follow", "error");
    } finally {
      setBusy(false);
    }
  };

  const pad = size === "sm" ? "px-3 py-1 text-xs" : "px-4 py-1.5 text-sm";

  return (
    <button
      onClick={toggle}
      disabled={busy || !ready}
      className={
        following
          ? `inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/5 ${pad} font-medium text-gray-300 transition-colors hover:border-red-400/40 hover:text-red-300`
          : `inline-flex items-center gap-1.5 rounded-full ${pad} font-semibold btn-primary`
      }
    >
      {following ? <UserCheck size={14} /> : <UserPlus size={14} />}
      {following ? "Following" : "Follow"}
    </button>
  );
}
