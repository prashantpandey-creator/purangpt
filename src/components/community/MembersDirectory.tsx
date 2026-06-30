"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Activity, Users, Sparkles, Search, Loader2, ArrowLeft } from "lucide-react";
import {
  communityApi,
  timeAgo,
  type CommunityMember,
  type MemberSort,
} from "@/lib/communityApi";
import { FollowButton } from "@/components/community/FollowButton";
import { useToast } from "@/context/ToastContext";

const SORTS: { id: MemberSort; label: string; icon: typeof Activity }[] = [
  { id: "active", label: "Most Active", icon: Activity },
  { id: "popular", label: "Most Followed", icon: Users },
  { id: "new", label: "Newest", icon: Sparkles },
];

function MemberCard({ m }: { m: CommunityMember }) {
  const href = `/community/u/${encodeURIComponent(m.user_sub)}`;
  return (
    <div className="card flex flex-col gap-3 p-4">
      <div className="flex items-start gap-3">
        <Link href={href} className="flex-shrink-0">
          <span className="flex h-12 w-12 items-center justify-center overflow-hidden rounded-full bg-gradient-to-br from-[#e8b63f] to-[#b8861f] text-lg font-bold text-[#0a0a0a]">
            {m.picture ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={m.picture} alt="" className="h-full w-full object-cover" />
            ) : (
              (m.display_name?.[0] ?? "?").toUpperCase()
            )}
          </span>
        </Link>
        <div className="min-w-0 flex-1">
          <Link
            href={href}
            className="flex items-center gap-1.5 font-medium text-gray-200 transition-colors hover:text-saffron"
          >
            <span className="truncate">{m.display_name || "Seeker"}</span>
            {m.is_bot && (
              <span className="inline-flex flex-shrink-0 items-center gap-0.5 rounded-full border border-saffron/40 bg-saffron/10 px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-saffron">
                <Sparkles size={9} /> Bot
              </span>
            )}
          </Link>
          <p className="mt-0.5 text-xs text-gray-500">joined {timeAgo(m.created_at)}</p>
        </div>
      </div>

      {m.bio && (
        <p className="line-clamp-2 text-sm text-gray-400">{m.bio}</p>
      )}

      <div className="mt-auto flex items-center justify-between pt-1">
        <div className="flex gap-4 text-xs text-gray-500">
          <span>
            <span className="font-semibold text-gray-300">{m.follower_count}</span> followers
          </span>
          <span>
            <span className="font-semibold text-gray-300">{m.post_count}</span> posts
          </span>
        </div>
        <FollowButton targetSub={m.user_sub} initialFollowing={m.is_following} size="sm" />
      </div>
    </div>
  );
}

export function MembersDirectory() {
  const { toast } = useToast();
  const [members, setMembers] = useState<CommunityMember[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [sort, setSort] = useState<MemberSort>("active");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  // Debounce the search box.
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 350);
    return () => clearTimeout(t);
  }, [search]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await communityApi.listMembers({ sort, q: debouncedSearch || null });
      setMembers(data.members);
      setTotal(data.total ?? data.members.length);
      setHasMore(data.has_more);
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to load members", "error");
    } finally {
      setLoading(false);
    }
  }, [sort, debouncedSearch, toast]);

  useEffect(() => {
    load();
  }, [load]);

  const loadMore = async () => {
    setLoadingMore(true);
    try {
      const data = await communityApi.listMembers({
        sort,
        q: debouncedSearch || null,
        offset: members.length,
      });
      setMembers((prev) => [...prev, ...data.members]);
      setHasMore(data.has_more);
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to load more", "error");
    } finally {
      setLoadingMore(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl px-4 pb-20 pt-24">
      {/* Header */}
      <div className="mb-6">
        <Link
          href="/community"
          className="mb-3 inline-flex items-center gap-1.5 text-sm text-gray-400 transition-colors hover:text-saffron"
        >
          <ArrowLeft size={15} /> Back to Community
        </Link>
        <h1 className="font-cinzel text-4xl font-bold text-gradient">The Sangha</h1>
        <p className="mt-2 text-gray-400">
          {total !== null ? (
            <>
              <span className="text-gray-200">{total.toLocaleString()}</span> seeker
              {total === 1 ? "" : "s"} have joined the community. Find and follow voices that resonate.
            </>
          ) : (
            "Find and follow fellow seekers in the community."
          )}
        </p>
      </div>

      {/* Search */}
      <div className="mb-5">
        <div className="relative">
          <Search
            size={18}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-500"
          />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search members by name…"
            className="w-full rounded-lg border border-white/10 bg-black/30 py-2.5 pl-10 pr-4 text-gray-100 outline-none transition-colors focus:border-saffron/60"
          />
        </div>
      </div>

      {/* Sort tabs */}
      <div className="mb-6 flex items-center gap-1 border-b border-white/10 pb-2">
        {SORTS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setSort(id)}
            className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors ${
              sort === id
                ? "bg-saffron/10 text-saffron"
                : "text-gray-400 hover:bg-white/5 hover:text-gray-200"
            }`}
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </div>

      {/* Grid */}
      {loading ? (
        <div className="flex justify-center py-16 text-saffron">
          <Loader2 className="animate-spin" size={28} />
        </div>
      ) : members.length === 0 ? (
        <div className="card p-10 text-center">
          <p className="text-gray-400">
            {debouncedSearch ? "No members match your search." : "No members yet."}
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {members.map((m) => (
              <MemberCard key={m.user_sub} m={m} />
            ))}
          </div>

          {hasMore && (
            <div className="mt-6 flex justify-center">
              <button
                onClick={loadMore}
                disabled={loadingMore}
                className="btn-secondary inline-flex items-center gap-2"
              >
                {loadingMore && <Loader2 className="animate-spin" size={16} />}
                {loadingMore ? "Loading…" : "Load more"}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
