"use client";

import { useRef, useState } from "react";
import { Bold, Italic, List, Quote, Link2, Eye, Pencil } from "lucide-react";
import { EmojiPicker } from "@/components/community/EmojiPicker";
import { Markdown } from "@/components/community/Markdown";

interface RichTextEditorProps {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  rows?: number;
  disabled?: boolean;
  autoFocus?: boolean;
  maxLength?: number;
  compact?: boolean;
}

/**
 * Markdown editor with a formatting toolbar, emoji picker and live preview.
 * Used for both posts and comments so members get the full set of tools
 * everywhere — bold, italic, quotes, lists, links and emoji.
 */
export function RichTextEditor({
  value,
  onChange,
  placeholder,
  rows = 5,
  disabled = false,
  autoFocus = false,
  maxLength,
  compact = false,
}: RichTextEditorProps) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const [preview, setPreview] = useState(false);

  /** Wrap the current selection (or insert at cursor) with before/after tokens. */
  const surround = (before: string, after = before, placeholderText = "") => {
    const el = ref.current;
    if (!el) {
      onChange(value + before + placeholderText + after);
      return;
    }
    const start = el.selectionStart ?? value.length;
    const end = el.selectionEnd ?? value.length;
    const selected = value.slice(start, end) || placeholderText;
    const next = value.slice(0, start) + before + selected + after + value.slice(end);
    onChange(next);
    // Restore focus + selection around the inserted text.
    requestAnimationFrame(() => {
      el.focus();
      const pos = start + before.length;
      el.setSelectionRange(pos, pos + selected.length);
    });
  };

  /** Prefix the current line(s) — for lists and quotes. */
  const prefixLine = (token: string) => {
    const el = ref.current;
    if (!el) {
      onChange(value + (value && !value.endsWith("\n") ? "\n" : "") + token);
      return;
    }
    const start = el.selectionStart ?? value.length;
    const lineStart = value.lastIndexOf("\n", start - 1) + 1;
    const next = value.slice(0, lineStart) + token + value.slice(lineStart);
    onChange(next);
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(start + token.length, start + token.length);
    });
  };

  const insertAtCursor = (text: string) => {
    const el = ref.current;
    if (!el) {
      onChange(value + text);
      return;
    }
    const start = el.selectionStart ?? value.length;
    const end = el.selectionEnd ?? value.length;
    const next = value.slice(0, start) + text + value.slice(end);
    onChange(next);
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(start + text.length, start + text.length);
    });
  };

  const ToolbarBtn = ({
    onClick,
    label,
    children,
  }: {
    onClick: () => void;
    label: string;
    children: React.ReactNode;
  }) => (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      disabled={disabled || preview}
      className="rounded-md p-1.5 text-gray-400 transition-colors hover:bg-white/5 hover:text-saffron disabled:opacity-40"
    >
      {children}
    </button>
  );

  return (
    <div className="rounded-lg border border-white/10 bg-black/30 focus-within:border-saffron/60">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-0.5 border-b border-white/10 px-1.5 py-1">
        <ToolbarBtn onClick={() => surround("**", "**", "bold")} label="Bold">
          <Bold size={16} />
        </ToolbarBtn>
        <ToolbarBtn onClick={() => surround("*", "*", "italic")} label="Italic">
          <Italic size={16} />
        </ToolbarBtn>
        <ToolbarBtn onClick={() => prefixLine("- ")} label="Bullet list">
          <List size={16} />
        </ToolbarBtn>
        <ToolbarBtn onClick={() => prefixLine("> ")} label="Quote">
          <Quote size={16} />
        </ToolbarBtn>
        <ToolbarBtn onClick={() => surround("[", "](https://)", "link text")} label="Link">
          <Link2 size={16} />
        </ToolbarBtn>
        {!preview && <EmojiPicker onPick={insertAtCursor} />}
        <div className="ml-auto">
          <button
            type="button"
            onClick={() => setPreview((p) => !p)}
            className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-gray-400 transition-colors hover:bg-white/5 hover:text-saffron"
          >
            {preview ? <Pencil size={14} /> : <Eye size={14} />}
            {preview ? "Write" : "Preview"}
          </button>
        </div>
      </div>

      {/* Body */}
      {preview ? (
        <div className={`px-4 py-3 ${compact ? "min-h-[60px]" : "min-h-[120px]"}`}>
          {value.trim() ? (
            <Markdown>{value}</Markdown>
          ) : (
            <p className="text-sm text-gray-600">Nothing to preview yet.</p>
          )}
        </div>
      ) : (
        <textarea
          ref={ref}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={rows}
          disabled={disabled}
          autoFocus={autoFocus}
          maxLength={maxLength}
          placeholder={placeholder}
          className="w-full resize-y bg-transparent px-4 py-3 text-gray-100 outline-none placeholder:text-gray-600 disabled:opacity-60"
        />
      )}
    </div>
  );
}
