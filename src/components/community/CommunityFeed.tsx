"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Flame, Sparkles, TrendingUp, PenSquare, Search, Loader2, Users } from "lucide-react";
import {
  communityApi,
  CATEGORIES,
  type CommunityPost,
  type SortMode,
  type FeedMode,
} from "@/lib/communityApi";
import { PostCard } from "@/components/community/PostCard";
import { CreatePostModal } from "@/components/community/CreatePostModal";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";

const SORTS: { id: SortMode; label: string; icon: typeof Flame }[] = [
  { id: "hot", label: "Hot", icon: Flame },
  { id: "new", label: "New", icon: Sparkles },
  { id: "top", label: "Top", icon: TrendingUp },
];

export function CommunityFeed() {
  const { user } = useAuth();
  const { toast } = useToast();
  const [posts, setPosts] = useState<CommunityPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState<SortMode>("hot");
  const [feed, setFeed] = useState<FeedMode>("all");
  const [category, setCategory] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);

  // Debounce the search box.
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 350);
    return () => clearTimeout(t);
  }, [search]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await communityApi.listPosts({
        sort,
        category,
        q: debouncedSearch || null,
        feed,
      });
      setPosts(data);
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to load community", "error");
    } finally {
      setLoading(false);
    }
  }, [sort, category, debouncedSearch, feed, toast]);

  useEffect(() => {
    load();
  }, [load]);

  const handleCreateClick = () => {
    if (!user) {
      toast("Sign in to create a post", "info");
      return;
    }
    setShowCreate(true);
  };

  return (
    <div className="mx-auto max-w-3xl px-4 pb-20 pt-24">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-start justify-between gap-4">
          <h1 className="font-cinzel text-4xl font-bold text-gradient">Community</h1>
          <Link
            href="/community/members"
            className="mt-1 inline-flex flex-shrink-0 items-center gap-1.5 rounded-full border border-white/10 px-3 py-1.5 text-sm text-gray-300 transition-colors hover:border-saffron/40 hover:text-saffron"
          >
            <Users size={15} />
            Members
          </Link>
        </div>
        <p className="mt-2 text-gray-400">
          Ask questions, share wisdom, and discuss the sacred texts with fellow seekers.
        </p>
      </div>

      {/* Search + Create */}
      <div className="mb-5 flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search
            size={18}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-500"
          />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search discussions…"
            className="w-full rounded-lg border border-white/10 bg-black/30 py-2.5 pl-10 pr-4 text-gray-100 outline-none transition-colors focus:border-saffron/60"
          />
        </div>
        <button onClick={handleCreateClick} className="btn-primary inline-flex items-center justify-center gap-2">
          <PenSquare size={18} />
          New Post
        </button>
      </div>

      {/* Feed scope: everyone vs people you follow */}
      <div className="mb-4 inline-flex rounded-lg border border-white/10 p-0.5">
        {(["all", "following"] as FeedMode[]).map((f) => (
          <button
            key={f}
            onClick={() => {
              if (f === "following" && !user) {
                toast("Sign in to see people you follow", "info");
                return;
              }
              setFeed(f);
            }}
            className={`rounded-md px-4 py-1.5 text-sm transition-colors ${
              feed === f ? "bg-saffron/15 text-saffron" : "text-gray-400 hover:text-gray-200"
            }`}
          >
            {f === "all" ? "All" : "Following"}
          </button>
        ))}
      </div>

      {/* Sort tabs */}
      <div className="mb-4 flex items-center gap-1 border-b border-white/10 pb-2">
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

      {/* Category filter */}
      <div className="mb-6 flex flex-wrap gap-2">
        <button
          onClick={() => setCategory(null)}
          className={`rounded-full border px-3 py-1 text-xs transition-colors ${
            category === null
              ? "border-saffron bg-saffron/10 text-saffron"
              : "border-white/10 text-gray-400 hover:border-saffron/40 hover:text-gray-200"
          }`}
        >
          All
        </button>
        {CATEGORIES.map((c) => (
          <button
            key={c.id}
            onClick={() => setCategory(c.id)}
            className={`rounded-full border px-3 py-1 text-xs transition-colors ${
              category === c.id
                ? "border-saffron bg-saffron/10 text-saffron"
                : "border-white/10 text-gray-400 hover:border-saffron/40 hover:text-gray-200"
            }`}
          >
            {c.emoji} {c.label}
          </button>
        ))}
      </div>

      {/* Feed */}
      {loading ? (
        <div className="flex justify-center py-16 text-saffron">
          <Loader2 className="animate-spin" size={28} />
        </div>
      ) : posts.length === 0 ? (
        <div className="card p-10 text-center">
          {feed === "following" ? (
            <p className="text-gray-400">
              No posts from people you follow yet. Explore <button onClick={() => setFeed("all")} className="text-saffron hover:underline">All</button> and follow members whose voices resonate.
            </p>
          ) : (
            <>
              <p className="text-gray-400">No discussions yet.</p>
              <button onClick={handleCreateClick} className="btn-primary mt-4 inline-flex items-center gap-2">
                <PenSquare size={18} />
                Start the first discussion
              </button>
            </>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {posts.map((post) => (
            <PostCard key={post.id} post={post} />
          ))}
        </div>
      )}

      <CreatePostModal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onCreated={(p) => setPosts((prev) => [p, ...prev])}
      />
    </div>
  );
}
