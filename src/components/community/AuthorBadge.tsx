"use client";

import Link from "next/link";
import { Sparkles } from "lucide-react";

/** Avatar + name linking to the member's profile, with an Aurom bot badge. */
export function AuthorBadge({
  userSub,
  name,
  picture,
  isBot,
  size = 20,
  showAvatar = true,
}: {
  userSub: string;
  name: string;
  picture?: string | null;
  isBot?: boolean;
  size?: number;
  showAvatar?: boolean;
}) {
  const deleted = name === "[deleted]" || name === "[removed]";
  const inner = (
    <span className="inline-flex items-center gap-1.5">
      {showAvatar && (
        <span
          className="inline-flex items-center justify-center overflow-hidden rounded-full bg-gradient-to-br from-[#e8b63f] to-[#b8861f] text-[10px] font-bold text-[#0a0a0a]"
          style={{ width: size, height: size }}
        >
          {picture ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={picture} alt="" className="h-full w-full object-cover" />
          ) : (
            (name?.[0] ?? "?").toUpperCase()
          )}
        </span>
      )}
      <span className={isBot ? "font-medium text-saffron" : "font-medium text-gray-300"}>
        {name || "Seeker"}
      </span>
      {isBot && (
        <span className="inline-flex items-center gap-0.5 rounded-full border border-saffron/40 bg-saffron/10 px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-saffron">
          <Sparkles size={9} /> Bot
        </span>
      )}
    </span>
  );

  if (deleted) return inner;

  return (
    <Link
      href={`/community/u/${encodeURIComponent(userSub)}`}
      className="transition-colors hover:text-saffron"
      onClick={(e) => e.stopPropagation()}
    >
      {inner}
    </Link>
  );
}
