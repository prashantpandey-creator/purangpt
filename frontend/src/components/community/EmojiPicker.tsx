"use client";

import { useEffect, useRef, useState } from "react";
import { Smile } from "lucide-react";

const EMOJI_GROUPS: { name: string; emojis: string[] }[] = [
  {
    name: "Sacred",
    emojis: ["🪔", "🕉️", "🙏", "🧘", "🌸", "🪷", "📿", "🛕", "🔱", "🐚", "🌅", "✨", "🌟", "💫", "☀️", "🌙"],
  },
  {
    name: "Faces",
    emojis: ["😊", "😌", "🙂", "😇", "🥹", "😢", "😮", "😯", "🤔", "😅", "😂", "🥰", "😍", "😎", "😴", "🤗"],
  },
  {
    name: "Gestures",
    emojis: ["👍", "👎", "👏", "🙌", "🤝", "💪", "✌️", "🤲", "👐", "🫶", "❤️", "🧡", "💛", "💚", "💙", "💜"],
  },
  {
    name: "Nature",
    emojis: ["🌿", "🍃", "🌱", "🌳", "🔥", "💧", "🌊", "⛰️", "🏔️", "🦚", "🐘", "🐅", "🪶", "🌾", "🍂", "🌻"],
  },
  {
    name: "Symbols",
    emojis: ["✅", "❓", "❗", "💭", "💬", "📖", "📜", "🔆", "⚡", "🎯", "🧠", "♾️", "☮️", "⭐", "🏵️", "🎶"],
  },
];

export function EmojiPicker({ onPick }: { onPick: (emoji: string) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label="Insert emoji"
        className="rounded-md p-1.5 text-gray-400 transition-colors hover:bg-white/5 hover:text-saffron"
      >
        <Smile size={18} />
      </button>

      {open && (
        <div className="absolute bottom-full left-0 z-50 mb-2 max-h-72 w-72 overflow-y-auto rounded-xl border border-white/10 bg-[#171514] p-3 shadow-2xl">
          {EMOJI_GROUPS.map((group) => (
            <div key={group.name} className="mb-3 last:mb-0">
              <p className="mb-1 text-[10px] uppercase tracking-wider text-gray-500">{group.name}</p>
              <div className="grid grid-cols-8 gap-1">
                {group.emojis.map((emoji) => (
                  <button
                    key={emoji}
                    type="button"
                    onClick={() => {
                      onPick(emoji);
                      setOpen(false);
                    }}
                    className="rounded-md p-1 text-lg transition-colors hover:bg-saffron/10"
                  >
                    {emoji}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
