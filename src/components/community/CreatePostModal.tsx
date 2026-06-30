"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import {
  communityApi,
  CATEGORIES,
  type CommunityPost,
} from "@/lib/communityApi";
import { RichTextEditor } from "@/components/community/RichTextEditor";
import { useToast } from "@/context/ToastContext";

interface CreatePostModalProps {
  open: boolean;
  onClose: () => void;
  onCreated: (post: CommunityPost) => void;
}

export function CreatePostModal({ open, onClose, onCreated }: CreatePostModalProps) {
  const { toast } = useToast();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [category, setCategory] = useState("discussion");
  const [submitting, setSubmitting] = useState(false);

  const reset = () => {
    setTitle("");
    setBody("");
    setCategory("discussion");
  };

  const handleSubmit = async () => {
    if (title.trim().length < 3) {
      toast("Title must be at least 3 characters", "error");
      return;
    }
    setSubmitting(true);
    try {
      const post = await communityApi.createPost({
        title: title.trim(),
        body: body.trim(),
        category,
      });
      toast("Post published", "success");
      reset();
      onCreated(post);
      onClose();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to publish", "error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[90] flex items-start justify-center overflow-y-auto bg-black/70 p-4 backdrop-blur-sm sm:items-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            className="card relative my-8 w-full max-w-2xl p-6"
            initial={{ opacity: 0, y: 20, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.97 }}
            transition={{ duration: 0.2 }}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={onClose}
              className="absolute right-4 top-4 text-gray-500 transition-colors hover:text-gray-200"
              aria-label="Close"
            >
              <X size={20} />
            </button>

            <h2 className="font-cinzel mb-5 text-2xl font-bold text-gradient">
              Start a discussion
            </h2>

            {/* Category */}
            <label className="mb-2 block text-xs uppercase tracking-wide text-gray-500">
              Category
            </label>
            <div className="mb-4 flex flex-wrap gap-2">
              {CATEGORIES.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => setCategory(c.id)}
                  className={`rounded-full border px-3 py-1 text-sm transition-colors ${
                    category === c.id
                      ? "border-saffron bg-saffron/10 text-saffron"
                      : "border-white/10 text-gray-400 hover:border-saffron/40 hover:text-gray-200"
                  }`}
                >
                  {c.emoji} {c.label}
                </button>
              ))}
            </div>

            {/* Title */}
            <label className="mb-2 block text-xs uppercase tracking-wide text-gray-500">
              Title
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={300}
              placeholder="An interesting question or insight…"
              className="mb-1 w-full rounded-lg border border-white/10 bg-black/30 px-4 py-2.5 text-gray-100 outline-none transition-colors focus:border-saffron/60"
            />
            <p className="mb-4 text-right text-xs text-gray-600">{title.length}/300</p>

            {/* Body */}
            <label className="mb-2 block text-xs uppercase tracking-wide text-gray-500">
              Details <span className="text-gray-600">(optional — Markdown & emoji supported)</span>
            </label>
            <RichTextEditor
              value={body}
              onChange={setBody}
              rows={7}
              maxLength={20000}
              placeholder="Share context, scripture references, your reflections — open it up for discussion. Use **bold**, *italics*, lists, quotes and emoji 🪔"
            />

            <div className="mt-5 flex justify-end gap-3">
              <button onClick={onClose} className="btn-secondary" disabled={submitting}>
                Cancel
              </button>
              <button onClick={handleSubmit} className="btn-primary" disabled={submitting}>
                {submitting ? "Publishing…" : "Publish"}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
