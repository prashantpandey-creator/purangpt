"use client";

import { ArrowBigUp, ArrowBigDown } from "lucide-react";

interface VoteControlProps {
  score: number;
  myVote: number; // -1 | 0 | 1
  onVote: (value: number) => void;
  orientation?: "vertical" | "horizontal";
  size?: number;
  disabled?: boolean;
}

/** Reddit-style up/down vote with optimistic highlight. */
export function VoteControl({
  score,
  myVote,
  onVote,
  orientation = "vertical",
  size = 22,
  disabled = false,
}: VoteControlProps) {
  const up = myVote === 1;
  const down = myVote === -1;

  return (
    <div
      className={`flex items-center ${
        orientation === "vertical" ? "flex-col" : "flex-row gap-1"
      } select-none`}
    >
      <button
        type="button"
        aria-label="Upvote"
        disabled={disabled}
        onClick={() => onVote(1)}
        className={`rounded-md p-1 transition-colors hover:bg-saffron/10 disabled:opacity-40 ${
          up ? "text-saffron drop-shadow-[0_0_6px_rgba(232,182,63,0.55)]" : "text-gray-500 hover:text-saffron"
        }`}
      >
        <ArrowBigUp size={size} fill={up ? "currentColor" : "none"} />
      </button>
      <span
        className={`text-sm font-semibold tabular-nums ${
          up ? "text-saffron" : down ? "text-sky-400" : "text-gray-300"
        }`}
      >
        {score}
      </span>
      <button
        type="button"
        aria-label="Downvote"
        disabled={disabled}
        onClick={() => onVote(-1)}
        className={`rounded-md p-1 transition-colors hover:bg-sky-500/10 disabled:opacity-40 ${
          down ? "text-sky-400 drop-shadow-[0_0_6px_rgba(56,189,248,0.5)]" : "text-gray-500 hover:text-sky-400"
        }`}
      >
        <ArrowBigDown size={size} fill={down ? "currentColor" : "none"} />
      </button>
    </div>
  );
}
