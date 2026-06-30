"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, ArrowRight, Loader2, RefreshCw } from "lucide-react";

interface QueryGeneratorProps {
  onQueryGenerated: (query: string) => void;
}

export function QueryGenerator({ onQueryGenerated }: QueryGeneratorProps) {
  const [input, setInput] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [formulatedQuery, setFormulatedQuery] = useState("");
  const [error, setError] = useState("");

  const handleGenerate = async () => {
    if (!input.trim()) return;
    setIsGenerating(true);
    setError("");

    try {
      const response = await fetch("/api/generate-query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: input }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || "Failed to generate query");
      }

      const data = await response.json();
      setFormulatedQuery(data.formulatedQuery);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleStartResearch = () => {
    if (formulatedQuery) {
      onQueryGenerated(formulatedQuery);
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto space-y-6">
      <div className="text-center space-y-3">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-2xl bg-[#1e1e1e] border border-[#353534]">
          <Sparkles className="w-4 h-4 text-[#a78bfa]" />
          <span className="text-xs uppercase tracking-widest text-[#dbc2b0]" style={{ fontFamily: "var(--font-geist, sans-serif)" }}>
            Deep Research Formulation
          </span>
        </div>
        <h2 className="text-3xl font-bold text-[#e5e2e1]" style={{ fontFamily: "var(--font-marcellus, serif)" }}>
          What are you trying to explore?
        </h2>
        <p className="text-[#94a3b8] text-lg max-w-xl mx-auto" style={{ fontFamily: "var(--font-inter, sans-serif)" }}>
          Describe your research topic in your own words. Our AI will formulate it into a precise, scholarly query designed to extract the most comprehensive insights from the sacred texts.
        </p>
      </div>

      <div className="bg-[#1e1e1e] rounded-2xl p-6 border border-[#353534] shadow-lg">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g., I want to know about the different stages of meditation mentioned by Patanjali and how they compare to Shiva's teachings."
          className="w-full h-32 bg-[#000000] text-[#e5e2e1] placeholder-[#554336] p-4 rounded-2xl border border-[#353534] focus:outline-none focus:border-[#a78bfa]/50 resize-none mb-4 text-lg"
          style={{ fontFamily: "var(--font-inter, sans-serif)" }}
        />

        <div className="flex justify-end">
          <button
            onClick={handleGenerate}
            disabled={!input.trim() || isGenerating}
            className="flex items-center gap-2 px-6 py-2.5 bg-[#a78bfa] text-[#000000] rounded-2xl font-medium hover:bg-[#ffb77a] transition-colors disabled:opacity-50"
          >
            {isGenerating ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}
            Formulate Query
          </button>
        </div>

        {error && (
          <p className="text-[#ffb4ab] mt-4 text-sm">{error}</p>
        )}

        <AnimatePresence>
          {formulatedQuery && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mt-6 pt-6 border-t border-[#353534]"
            >
              <h3 className="text-[#94a3b8] text-sm uppercase tracking-widest mb-3" style={{ fontFamily: "var(--font-geist, sans-serif)" }}>
                Golden Query
              </h3>
              <textarea
                value={formulatedQuery}
                onChange={(e) => setFormulatedQuery(e.target.value)}
                className="w-full min-h-[100px] bg-[#000000] text-[#f0cd80] p-4 rounded-2xl border border-[#a78bfa]/30 focus:outline-none focus:border-[#a78bfa] resize-none mb-4 text-lg leading-relaxed shadow-[0_0_15px_rgba(232,182,63,0.05)]"
                style={{ fontFamily: "var(--font-inter, sans-serif)" }}
              />
              
              <div className="flex justify-end">
                <button
                  onClick={handleStartResearch}
                  className="flex items-center gap-2 px-8 py-3 border border-[#a78bfa] text-[#a78bfa] rounded-2xl font-medium hover:bg-[#a78bfa]/10 transition-colors"
                >
                  Commence Deep Research
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
